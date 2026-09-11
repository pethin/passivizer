"""
Allomorph - Minimum-Phase FIR Filter Synthesis & Pre-filtering Engine
Synthesizes causal minimum-phase FIR pre-filters modeling compound spatial acoustics,
scale-length wave-speed conversions, and transducer deconvolution.
"""

from pathlib import Path
import numpy as np

from allomorph.dsp import NUM_TAPS, FREQS, synthesize_minimum_phase_fir
from allomorph.config import (
    REPO_ROOT,
    SCALES,
    VOICES,
    load_instrument,
    get_source_pickup,
    get_instrument_string,
    resolve_pickup_coils,
    resolve_voice_pickups,
    resolve_voice_coils,
    compute_effective_position,
)
from allomorph.physics.strings import (
    get_voice_string,
    compute_differential_string_transfer,
    compute_differential_longitudinal_transfer,
    resolve_scale_range,
    MEAN_BASS_F0,
)
from allomorph.physics.aperture import (
    compute_body_microphonic_coupling,
    compute_saddle_boundary_coupling,
    is_voice_matching_source,
    numpy_pickup_acoustic_response,
    numpy_pickup_macro_aperture,
)
from allomorph.physics.deconvolution import resolve_pickup_electrical_deconvolution_np


def compute_voice_prefilter_firs(
    voice_id: str,
    instrument="30in",
    src_scale=None,
    num_taps: int = NUM_TAPS,
    src_pickup_key: str = None,
) -> list:
    """
    Computes acoustic pre-filter FIRs for each pickup in a target voice configuration using NumPy.
    For single-pickup voices, returns a list with 1 FIR: [fir].
    For multi-pickup voices (e.g. Jazz pair, P/J, P/MM), returns a list of FIRs:
    [fir_pickup_0, fir_pickup_1, ...], enabling independent channel excitation in SPICE.
    """
    cfg = VOICES[voice_id]
    if cfg.get("no_eq", False) or cfg.get("preserve_aperture", False):
        impulse = [1.0] + [0.0] * (num_taps - 1)
        return [impulse]

    target_scale_key = cfg.get("scale", "34in")
    tgt = SCALES[target_scale_key]

    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    src_scale_range = resolve_scale_range(inst)
    tgt_scale_range = resolve_scale_range(tgt if target_scale_key in SCALES else target_scale_key)
    src_scale_m = (src_scale_range[0] + src_scale_range[1]) / 2.0
    tgt_scale_m = (tgt_scale_range[0] + tgt_scale_range[1]) / 2.0
    src_scale_in = src_scale_m / 0.0254
    tgt_scale_in = tgt_scale_m / 0.0254

    if src_pickup_key and src_pickup_key != "auto":
        pickups = inst.get("pickups", {})
        if src_pickup_key not in pickups:
            raise KeyError(
                f"Pickup '{src_pickup_key}' not found on instrument '{inst.get('id', 'unknown')}'. "
                f"Available pickups: {list(pickups.keys())}"
            )
        src_pickup = pickups[src_pickup_key].copy()
        src_pickup["id"] = src_pickup_key
    else:
        src_pickup = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_pickup, inst)
    src_pos_eff = compute_effective_position(src_coils)

    freqs = np.asarray(FREQS, dtype=np.float64)

    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, scale_length_m=src_scale_range)

    src_string = get_instrument_string(inst)
    tgt_string = get_voice_string(cfg)

    sensor_type = cfg.get("sensor_type", "magnetic")
    pickups = resolve_voice_pickups(cfg)
    is_identity = (sensor_type not in ["bridge_force", "direct"]) and is_voice_matching_source(
        inst, voice_id, cfg
    )

    # Scale-Length Tension & Body Bloom Filter
    if is_identity:
        h_tension = np.ones_like(freqs)
    elif target_scale_key == "upright":
        delta_bloom = float(tgt_string.get("bloom_db", 2.8)) - float(src_string.get("bloom_db", 0.0))
        g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
        h_bloom = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        h_tension = h_bloom
    elif src_scale_in < tgt_scale_in - 0.2:
        snap_db = min(3.5, 1.8 * (tgt_scale_in - src_scale_in) / 4.0)
        g_snap = 10.0 ** (snap_db / 20.0)
        h_tension = np.sqrt(
            (1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2)
        )
    else:
        h_tension = np.ones_like(freqs)

    tgt_circ = cfg.get("circuit")
    if isinstance(tgt_circ, dict):
        has_multichannel_circuit = bool(len(pickups) > 1)
    elif isinstance(tgt_circ, (str, Path)):
        cir_path = REPO_ROOT / tgt_circ
        has_multichannel_circuit = bool(cir_path.exists() and len(pickups) > 1)
    else:
        has_multichannel_circuit = False

    src_components = (
        src_pickup.get("components", []) if src_pickup.get("type") == "composite" else []
    )
    use_branch_matching = len(src_components) == len(pickups) and len(pickups) > 1

    has_src_circuit = bool(src_pickup.get("circuit"))
    is_passive = inst.get("electronics") == "passive"
    h_elec_inv = (
        np.ones_like(freqs)
        if (is_identity or is_passive or has_src_circuit)
        else resolve_pickup_electrical_deconvolution_np(freqs, src_pickup, inst)
    )

    positions = [compute_effective_position(p["coils"]) for p in pickups]
    pos_max = max(positions) if positions else 0.0
    c_mean = 2.0 * tgt_scale_m * MEAN_BASS_F0
    raw_firs = []
    for i, p in enumerate(pickups):
        p_coils = p["coils"]
        tgt_pos_eff = positions[i]

        if use_branch_matching:
            comp_sub_id = src_components[i]["pickup"]
            comp_sub_p = inst["pickups"][comp_sub_id]
            b_src_coils = resolve_pickup_coils(comp_sub_p, inst)
            b_src_pos_eff = compute_effective_position(b_src_coils)
            b_src_acoustic = numpy_pickup_acoustic_response(
                freqs, b_src_coils, scale_length_m=src_scale_range
            )
        else:
            b_src_coils = src_coils
            b_src_pos_eff = src_pos_eff
            b_src_acoustic = h_src_acoustic

        if sensor_type == "bridge_force":
            eps = 0.08
            h_decomb_raw = b_src_acoustic / (b_src_acoustic ** 2 + eps)
            mid_mask = (freqs >= 100.0) & (freqs <= 1000.0)
            h_decomb_raw = h_decomb_raw / np.median(h_decomb_raw[mid_mask])

            c_mean_src = 2.0 * src_scale_m * MEAN_BASS_F0
            pos_eff = max(b_src_pos_eff, 0.035)
            f_peak_src = c_mean_src / pos_eff
            f_taper_start = min(f_peak_src, 2500.0)
            f_taper_end = min(1.8 * f_taper_start, 4500.0)
            t = np.clip((freqs - f_taper_start) / (f_taper_end - f_taper_start), 0.0, 1.0)
            w = 0.5 * (1.0 + np.cos(np.pi * t))
            h_decomb = w * h_decomb_raw + (1.0 - w) * 1.0

            is_flatwound = "flat" in src_string.get("type", "")
            f_damp = 4200.0 if is_flatwound else 3600.0
            h_damp = 1.0 / np.sqrt((1.0 - (freqs / f_damp) ** 2) ** 2 + 2.0 * (freqs / f_damp) ** 2)

            g_sub = 0.15
            h_sub = np.sqrt((g_sub ** 2 * 32.0 ** 2 + freqs ** 2) / (32.0 ** 2 + freqs ** 2))

            h_acoustic_transfer = h_decomb * h_damp * h_sub

            h_tilt = np.sqrt((1.0 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 70.0) ** 2))
            h_tilt = h_tilt / np.max(h_tilt)
        elif is_identity:
            h_acoustic_transfer = np.ones_like(freqs)
            h_tilt = np.ones_like(freqs)
        else:
            if sensor_type == "direct":
                h_tgt_acoustic = np.ones_like(freqs)
            else:
                h_tgt_acoustic = numpy_pickup_acoustic_response(
                    freqs, p_coils, scale_length_m=tgt_scale_range
                )
            h_src_macro = numpy_pickup_macro_aperture(
                freqs, b_src_coils, scale_length_m=src_scale_range
            )
            eps = 0.01
            h_quotient = (h_tgt_acoustic * h_src_macro) / (h_src_macro ** 2 + eps ** 2)
            q_db = 20.0 * np.log10(np.maximum(h_quotient, 1e-6))
            g_max_db = 12.0 if sensor_type == "direct" else 8.0
            g_min_db = -14.0
            q_soft_db = np.where(
                q_db > 0.0,
                g_max_db * np.tanh(q_db / g_max_db),
                g_min_db * np.tanh(q_db / g_min_db),
            )
            h_acoustic_transfer = 10.0 ** (q_soft_db / 20.0)

            if sensor_type == "direct":
                h_tilt = np.ones_like(freqs)
            else:
                eta_tgt = tgt_pos_eff / tgt_scale_m
                eta_src = b_src_pos_eff / src_scale_m
                delta_in = (eta_tgt - eta_src) * 34.0
                tilt_db = delta_in * 1.5
                g_low = 10.0 ** (tilt_db / 20.0)
                g_hi = 10.0 ** (-tilt_db / 20.0)
                h_low_tilt = np.sqrt(
                    (g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2)
                )
                h_hi_tilt = np.sqrt(
                    (1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2)
                )
                h_tilt = h_low_tilt * h_hi_tilt

        p_weight = 1.0 if has_multichannel_circuit else p.get("weight", 1.0)
        p_pol = p.get("polarity", 1.0)
        scale_fac = abs(p_weight * p_pol)

        if (
            sensor_type != "bridge_force"
            and cfg.get("target_string")
            and cfg.get("target_string") != "roundwound_nickel_standard"
        ):
            h_str_diff = compute_differential_string_transfer(freqs, src_string, tgt_string)
            h_long_diff = compute_differential_longitudinal_transfer(
                freqs, src_string, tgt_string, scale_length_inches=src_scale_in
            )
        else:
            h_str_diff = np.ones_like(freqs)
            h_long_diff = np.ones_like(freqs)

        h_scale_tension = np.ones_like(freqs) if is_identity else h_tension
        h_body = (
            np.ones_like(freqs)
            if is_identity
            else compute_body_microphonic_coupling(freqs, src_pickup, cfg, inst=inst)
        )

        if is_identity or sensor_type == "bridge_force":
            h_saddle_diff = np.ones_like(freqs)
        else:
            h_saddle_tgt = compute_saddle_boundary_coupling(freqs, tgt_pos_eff, tgt_scale_m)
            h_saddle_src = compute_saddle_boundary_coupling(freqs, b_src_pos_eff, src_scale_m)
            h_saddle_diff = np.minimum(h_saddle_tgt / np.maximum(h_saddle_src, 1e-6), 1.0)

        prefilter_curve = (
            scale_fac
            * h_acoustic_transfer
            * h_elec_inv
            * h_tilt
            * h_scale_tension
            * h_str_diff
            * h_long_diff
            * h_body
            * h_saddle_diff
        )
        fir_raw = synthesize_minimum_phase_fir(prefilter_curve, num_taps=num_taps, normalize=False)

        if is_identity:
            tau_i = 0.0
        elif use_branch_matching:
            src_positions = [
                compute_effective_position(
                    resolve_pickup_coils(inst["pickups"][c["pickup"]], inst)
                )
                for c in src_components
            ]
            src_pos_max = max(src_positions) if src_positions else 0.0
            src_c_mean = 2.0 * src_scale_m * MEAN_BASS_F0
            tau_src_i = (
                (src_pos_max - src_positions[i]) / src_c_mean if i < len(src_positions) else 0.0
            )
            tau_tgt_i = (pos_max - positions[i]) / c_mean
            tau_i = max(0.0, tau_tgt_i - tau_src_i)
        elif len(pickups) > 1:
            tau_i = (pos_max - positions[i]) / c_mean
        else:
            tau_i = 0.0

        if tau_i > 0.0:
            delay_samples = int(round(tau_i * 48000.0))
            if 0 < delay_samples < num_taps:
                fir_raw = [0.0] * delay_samples + fir_raw[: num_taps - delay_samples]

        raw_firs.append(fir_raw)

    global_peak = max(max(abs(x) for x in fir) for fir in raw_firs)
    if global_peak > 0:
        return [[(x / global_peak) * 0.99 for x in fir] for fir in raw_firs]
    return raw_firs


def compute_aperture_prefilter_fir(
    voice_id: str, instrument="30in", src_scale=None, num_taps: int = NUM_TAPS
) -> list:
    """
    Computes a single composite acoustic pre-filter FIR using NumPy.
    Retained for backward compatibility. For multi-pickup independent channels,
    use compute_voice_prefilter_firs().
    """
    cfg = VOICES[voice_id]
    pickups = resolve_voice_pickups(cfg)
    if len(pickups) == 1:
        firs = compute_voice_prefilter_firs(
            voice_id, instrument=instrument, src_scale=src_scale, num_taps=num_taps
        )
        return firs[0]

    target_scale_key = cfg.get("scale", "34in")
    tgt = SCALES[target_scale_key]

    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    src_scale_range = resolve_scale_range(inst)
    tgt_scale_range = resolve_scale_range(tgt if target_scale_key in SCALES else target_scale_key)
    src_scale_m = (src_scale_range[0] + src_scale_range[1]) / 2.0
    tgt_scale_m = (tgt_scale_range[0] + tgt_scale_range[1]) / 2.0
    src_scale_in = src_scale_m / 0.0254
    tgt_scale_in = tgt_scale_m / 0.0254

    src_pickup = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_pickup, inst)
    tgt_coils = resolve_voice_coils(cfg)

    src_pos_eff = compute_effective_position(src_coils)
    tgt_pos_eff = compute_effective_position(tgt_coils)

    freqs = np.asarray(FREQS, dtype=np.float64)

    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, scale_length_m=src_scale_range)

    src_string = get_instrument_string(inst)
    tgt_string = get_voice_string(cfg)

    sensor_type = cfg.get("sensor_type", "magnetic")
    is_identity = (sensor_type != "bridge_force") and is_voice_matching_source(inst, voice_id, cfg)
    if sensor_type == "bridge_force":
        eps = 0.08
        h_decomb_raw = h_src_acoustic / (h_src_acoustic ** 2 + eps)
        mid_mask = (freqs >= 100.0) & (freqs <= 1000.0)
        h_decomb_raw = h_decomb_raw / np.median(h_decomb_raw[mid_mask])

        c_mean_src = 2.0 * src_scale_m * MEAN_BASS_F0
        pos_eff = max(src_pos_eff, 0.035)
        f_peak_src = c_mean_src / pos_eff
        f_taper_start = min(f_peak_src, 2500.0)
        f_taper_end = min(1.8 * f_taper_start, 4500.0)
        t = np.clip((freqs - f_taper_start) / (f_taper_end - f_taper_start), 0.0, 1.0)
        w = 0.5 * (1.0 + np.cos(np.pi * t))
        h_decomb = w * h_decomb_raw + (1.0 - w) * 1.0

        is_flatwound = "flat" in src_string.get("type", "")
        f_damp = 4200.0 if is_flatwound else 3600.0
        h_damp = 1.0 / np.sqrt((1.0 - (freqs / f_damp) ** 2) ** 2 + 2.0 * (freqs / f_damp) ** 2)

        g_sub = 0.15
        h_sub = np.sqrt((g_sub ** 2 * 32.0 ** 2 + freqs ** 2) / (32.0 ** 2 + freqs ** 2))

        h_acoustic_transfer = h_decomb * h_damp * h_sub

        h_tilt = np.sqrt((1.0 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 70.0) ** 2))
        h_tilt = h_tilt / np.max(h_tilt)
    elif is_identity:
        h_acoustic_transfer = np.ones_like(freqs)
        h_tilt = np.ones_like(freqs)
    else:
        h_tgt_acoustic = numpy_pickup_acoustic_response(
            freqs, tgt_coils, scale_length_m=tgt_scale_range
        )
        h_src_macro = numpy_pickup_macro_aperture(freqs, src_coils, scale_length_m=src_scale_range)
        eps = 0.01
        h_quotient = (h_tgt_acoustic * h_src_macro) / (h_src_macro ** 2 + eps ** 2)
        q_db = 20.0 * np.log10(np.maximum(h_quotient, 1e-6))
        g_max_db = 8.0
        g_min_db = -14.0
        q_soft_db = np.where(
            q_db > 0.0,
            g_max_db * np.tanh(q_db / g_max_db),
            g_min_db * np.tanh(q_db / g_min_db),
        )
        h_acoustic_transfer = 10.0 ** (q_soft_db / 20.0)
        eta_tgt = tgt_pos_eff / tgt_scale_m
        eta_src = src_pos_eff / src_scale_m
        delta_in = (eta_tgt - eta_src) * 34.0
        tilt_db = delta_in * 1.5
        g_low = 10.0 ** (tilt_db / 20.0)
        g_hi = 10.0 ** (-tilt_db / 20.0)
        h_low_tilt = np.sqrt((g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2))
        h_hi_tilt = np.sqrt((1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2))
        h_tilt = h_low_tilt * h_hi_tilt

    if is_identity:
        h_tension = np.ones_like(freqs)
    elif target_scale_key == "upright":
        delta_bloom = float(tgt_string.get("bloom_db", 2.8)) - float(src_string.get("bloom_db", 0.0))
        g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
        h_bloom = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        h_tension = h_bloom
    elif src_scale_in < tgt_scale_in - 0.2:
        snap_db = min(3.5, 1.8 * (tgt_scale_in - src_scale_in) / 4.0)
        g_snap = 10.0 ** (snap_db / 20.0)
        h_tension = np.sqrt(
            (1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2)
        )
    else:
        h_tension = np.ones_like(freqs)

    if (
        sensor_type != "bridge_force"
        and cfg.get("target_string")
        and cfg.get("target_string") != "roundwound_nickel_standard"
    ):
        h_str_diff = compute_differential_string_transfer(freqs, src_string, tgt_string)
        h_long_diff = compute_differential_longitudinal_transfer(
            freqs, src_string, tgt_string, scale_length_inches=src_scale_in
        )
    else:
        h_str_diff = np.ones_like(freqs)
        h_long_diff = np.ones_like(freqs)

    has_src_circuit = bool(src_pickup.get("circuit"))
    is_passive = inst.get("electronics") == "passive"
    h_elec_inv = (
        np.ones_like(freqs)
        if (is_identity or is_passive or has_src_circuit)
        else resolve_pickup_electrical_deconvolution_np(freqs, src_pickup, inst)
    )

    h_body = (
        np.ones_like(freqs)
        if is_identity
        else compute_body_microphonic_coupling(freqs, src_pickup, cfg, inst=inst)
    )

    if is_identity or sensor_type == "bridge_force":
        h_saddle_diff = np.ones_like(freqs)
    else:
        h_saddle_tgt = compute_saddle_boundary_coupling(freqs, tgt_pos_eff, tgt_scale_m)
        h_saddle_src = compute_saddle_boundary_coupling(freqs, src_pos_eff, src_scale_m)
        h_saddle_diff = np.minimum(h_saddle_tgt / np.maximum(h_saddle_src, 1e-6), 1.0)

    prefilter_curve = (
        h_acoustic_transfer
        * h_elec_inv
        * h_tilt
        * h_tension
        * h_str_diff
        * h_long_diff
        * h_body
        * h_saddle_diff
    )
    max_val = np.max(prefilter_curve)
    resp_norm = prefilter_curve / max_val if max_val > 0 else prefilter_curve

    return synthesize_minimum_phase_fir(resp_norm, num_taps=num_taps)
