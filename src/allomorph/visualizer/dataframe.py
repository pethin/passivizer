"""
Allomorph Visualizer - Frequency Response Modeling and DataFrame Generation
Calculates magnitude frequency responses for target voicings, frontend deconvolutions,
and composite signal flow stages using Polars and NumPy.
"""

from typing import Any

import numpy as np
import polars as pl

from allomorph.circuit import (
    apply_magnet_properties_to_model,
    compute_circuit_transfer_functions,
    compute_differential_circuit_transfer_functions,
    load_circuit,
)
from allomorph.config import (
    SCALES,
    VOICES,
    AllomorphBaseModel,
    compute_effective_position,
    get_source_pickup,
    get_voice_string,
    load_all_instruments,
    load_instrument,
    resolve_pickup_coils,
    resolve_scale_range,
    resolve_voice_pickups,
)
from allomorph.dsp import (
    FREQS,
    synthesize_minimum_phase_fir,
)
from allomorph.physics import (
    MEAN_BASS_F0,
    compute_differential_longitudinal_transfer,
    compute_differential_string_transfer,
    compute_voice_prefilter_firs,
    is_voice_matching_source,
    numpy_pickup_acoustic_response,
    resolve_pickup_electrical_deconvolution,
)

NUM_POINTS = 600
F_MIN = 20.0
F_MAX = 20000.0

log_freqs = [F_MIN * (F_MAX / F_MIN) ** (i / (NUM_POINTS - 1)) for i in range(NUM_POINTS)]


def build_voice_dataframe(
    voice_id: str,
    cfg: dict[str, Any] | AllomorphBaseModel,
    instrument: str | dict[str, Any] | AllomorphBaseModel = "30in",
    src_scale: str | dict[str, Any] | AllomorphBaseModel | None = None,
    mode: str = "difference",
    include_mode_col: bool = False,
) -> pl.DataFrame:
    """
    Calculates magnitude frequency response in dB for a voice using NumPy vector math and Polars.
    mode="output": Absolute acoustic aperture + loaded SPICE circuit frequency response of the target voice.
    mode="difference": Regularized differential transfer function (H_target / H_source) applied to the source instrument.
    """
    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, (dict, AllomorphBaseModel)) else inst_selector

    tgt_scale = cfg.get("scale", "34in")
    _ = SCALES[tgt_scale]

    freqs = np.asarray(log_freqs, dtype=np.float64)
    pickups = resolve_voice_pickups(cfg)
    tgt_circuit = cfg.get("circuit")

    sensor_type = cfg.get("sensor_type", "magnetic")
    tgt_string = get_voice_string(cfg)
    is_passive = (inst.get("electronics") == "passive")
    is_spatial_match = (mode != "output") and is_voice_matching_source(inst, voice_id, cfg)

    if sensor_type == "direct" and mode == "output":
        data = {
            "frequency": log_freqs,
            "magnitude_db": [0.0] * len(log_freqs),
            "voice_id": voice_id,
            "voice_name": cfg.get("name", voice_id),
            "topology": cfg.get("topology", "Source Direct"),
            "description": cfg.get("description", ""),
        }
        if include_mode_col:
            data["mode"] = "Output Voice"
        return pl.DataFrame(data)

    if cfg.get("no_eq", False) or (mode == "difference" and voice_id == "16_active_character" and not is_passive):
        data = {
            "frequency": log_freqs,
            "magnitude_db": [0.0] * len(log_freqs),
            "voice_id": voice_id,
            "voice_name": cfg.get("name", voice_id),
            "topology": cfg.get("topology", "Active Dynamic Twin"),
            "description": cfg.get("description", ""),
        }
        if include_mode_col:
            data["mode"] = "Output Voice" if mode == "output" else "Input/Output Difference"
        return pl.DataFrame(data)

    if mode == "output":
        # 1. Output Voice: Target acoustic aperture + loaded SPICE circuit + string + body bloom
        if tgt_circuit:
            model = load_circuit(tgt_circuit)
            apply_magnet_properties_to_model(model, cfg)
            circuit_curves = compute_circuit_transfer_functions(model, freqs=FREQS)
        else:
            fc_hpf = cfg.get("hpf")
            circuit_curves = []
            f_lin = np.asarray(FREQS, dtype=np.float64)
            for p in pickups:
                fr_p = p.get("fr", cfg.get("fr", 3000.0))
                Q_p = p.get("Q", cfg.get("Q", 1.5))
                h_el = 1.0 / np.sqrt((1.0 - (f_lin / fr_p) ** 2) ** 2 + (1.0 / Q_p ** 2) * (f_lin / fr_p) ** 2)
                if fc_hpf:
                    h_el = h_el * (f_lin / np.sqrt(f_lin ** 2 + fc_hpf ** 2))
                circuit_curves.append(h_el.tolist())

        if sensor_type == "bridge_force":
            f_lin = freqs
            is_flatwound = "flat" in tgt_string.get("type", "")
            f_damp = 4200.0 if is_flatwound else 3600.0
            h_damp = 1.0 / np.sqrt((1.0 - (f_lin / f_damp) ** 2) ** 2 + 2.0 * (f_lin / f_damp) ** 2)
            g_sub = 0.15
            h_sub = np.sqrt((g_sub ** 2 * 32.0 ** 2 + f_lin ** 2) / (32.0 ** 2 + f_lin ** 2))
            h_tilt_raw = np.sqrt((1.0 + (f_lin / 250.0) ** 2) / (1.0 + (f_lin / 70.0) ** 2))
            h_tilt = h_tilt_raw / np.max(h_tilt_raw)
            c_curve = circuit_curves[0] if circuit_curves else [1.0] * len(FREQS)
            branch = np.interp(freqs, FREQS, np.asarray(c_curve, dtype=np.float64)) * h_damp * h_sub * h_tilt
            h_tgt_total = branch
        elif sensor_type == "direct":
            c_curve = circuit_curves[0] if circuit_curves else [1.0] * len(FREQS)
            h_tgt_total = np.interp(freqs, FREQS, np.asarray(c_curve, dtype=np.float64))
        else:
            tgt_scale_range = resolve_scale_range(tgt_scale)
            tgt_scale_m = (tgt_scale_range[0] + tgt_scale_range[1]) / 2.0
            positions = [compute_effective_position(p["coils"]) for p in pickups]
            pos_max = max(positions) if positions else 0.0
            c_mean = 2.0 * tgt_scale_m * MEAN_BASS_F0

            N = 8192
            f_bins = np.fft.rfftfreq(N, 1.0 / 48000.0)
            H_channels = []
            peaks = []

            for i, p in enumerate(pickups):
                c_curve = circuit_curves[i] if i < len(circuit_curves) else [1.0] * len(FREQS)
                p_weight = p.get("weight", 1.0)
                p_pol = p.get("polarity", 1.0)
                weight_fac = 1.0 if (tgt_circuit and len(circuit_curves) > 1) else p_weight

                ac = numpy_pickup_acoustic_response(f_bins, p["coils"], scale_length_m=tgt_scale_range) * (weight_fac * p_pol)
                fir_ac = synthesize_minimum_phase_fir(ac, num_taps=2048, normalize=False)
                tau_i = (pos_max - positions[i]) / c_mean if len(pickups) > 1 else 0.0
                delay_samples = round(tau_i * 48000.0)
                if 0 < delay_samples < 2048:
                    fir_ac = [0.0] * delay_samples + fir_ac[:2048 - delay_samples]
                peaks.append(int(np.argmax(np.abs(fir_ac))))

                fir_circ = synthesize_minimum_phase_fir(c_curve, num_taps=2048, normalize=False)
                H_channels.append(np.fft.rfft(fir_ac, N) * np.fft.rfft(fir_circ, N))

            H_channels = np.array(H_channels)
            delta_samples = max(peaks) - min(peaks) if len(peaks) > 1 else 0

            if len(H_channels) > 1 and delta_samples > 0:
                P_coherent = np.abs(np.sum(H_channels, axis=0)) ** 2
                P_incoherent = np.sum(np.abs(H_channels) ** 2, axis=0)
                delta_tau = delta_samples / 48000.0
                f_notch = 1.0 / (2.0 * delta_tau)
                f_start = f_notch
                f_end = 1.7 * f_notch
                t = np.clip((f_bins - f_start) / (f_end - f_start), 0.0, 1.0)
                gamma = 0.88 * 0.5 * (1.0 + np.cos(np.pi * t))
                mag_spectrum = np.sqrt(gamma * P_coherent + (1.0 - gamma) * P_incoherent)
            elif len(H_channels) > 1:
                mag_spectrum = np.abs(np.sum(H_channels, axis=0))
            else:
                mag_spectrum = np.abs(H_channels[0])

            h_tgt_total = np.interp(freqs, f_bins, mag_spectrum)

        # Tension / Bloom for target instrument
        if tgt_scale == "upright":
            delta_bloom = float(tgt_string.get("bloom_db", 2.8))
            g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
            h_tension = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        else:
            h_tension = np.ones_like(freqs)

        # String voicing for target instrument (relative to standard nickel roundwound)
        if sensor_type != "bridge_force" and cfg.get("target_string") and cfg.get("target_string") != "roundwound_nickel_standard":
            std_str = {"bloom_db": 0.0, "damping_factor": 1.0, "type": "roundwound_nickel", "k_long": 0.20}
            scale_in = 37.0 if tgt_scale in ["multiscale", "37in"] else (35.0 if tgt_scale == "multiscale_super" else 34.0)
            h_str = compute_differential_string_transfer(freqs, std_str, tgt_string)
            h_long = compute_differential_longitudinal_transfer(freqs, std_str, tgt_string, scale_length_inches=scale_in)
        else:
            h_str = np.ones_like(freqs)
            h_long = np.ones_like(freqs)

        mag_raw = h_tgt_total * h_tension * h_str * h_long

    else:
        # 2. Input/Output Difference: H_diff = H_target / H_source
        src_pickup = get_source_pickup(inst, voice_id)
        src_circuit = src_pickup.get("circuit")

        if not src_circuit and is_passive:
            raise ValueError(
                f"Passive instrument '{inst.get('id', 'unknown')}' pickup '{src_pickup.get('id', 'unknown')}' "
                f"does not define a '[circuit]' block. Passive source pickups require an explicit "
                f"circuit model for differential deconvolution."
            )

        if src_circuit and tgt_circuit:
            model = load_circuit(tgt_circuit)
            apply_magnet_properties_to_model(model, cfg)
            src_model = load_circuit(src_circuit)
            apply_magnet_properties_to_model(src_model, src_pickup)
            circuit_curves = compute_differential_circuit_transfer_functions(
                model, src_model, freqs=FREQS
            )
        elif tgt_circuit:
            model = load_circuit(tgt_circuit)
            apply_magnet_properties_to_model(model, cfg)
            circuit_curves = compute_circuit_transfer_functions(model, freqs=FREQS)
        else:
            fc_hpf = cfg.get("hpf")
            circuit_curves = []
            f_lin = np.asarray(FREQS, dtype=np.float64)
            for p in pickups:
                fr_p = p.get("fr", cfg.get("fr", 3000.0))
                Q_p = p.get("Q", cfg.get("Q", 1.5))
                h_el = 1.0 / np.sqrt((1.0 - (f_lin / fr_p) ** 2) ** 2 + (1.0 / Q_p ** 2) * (f_lin / fr_p) ** 2)
                if fc_hpf:
                    h_el = h_el * (f_lin / np.sqrt(f_lin ** 2 + fc_hpf ** 2))
                circuit_curves.append(h_el.tolist())

        # Multi-rate FFT evaluation matching native circuit simulator synthesis exactly
        prefilter_firs = compute_voice_prefilter_firs(voice_id, instrument=inst, num_taps=2048)
        N = 8192
        f_bins = np.fft.rfftfreq(N, 1.0 / 48000.0)
        H_channels = []
        for i in range(len(prefilter_firs)):
            pf = np.array(prefilter_firs[i], dtype=np.float32)
            cf = np.array(synthesize_minimum_phase_fir(circuit_curves[i], num_taps=2048, normalize=False), dtype=np.float32)
            H_channels.append(np.fft.rfft(pf, N) * np.fft.rfft(cf, N))

        H_channels = np.array(H_channels)
        peaks = [int(np.argmax(np.abs(fir))) for fir in prefilter_firs]
        delta_samples = max(peaks) - min(peaks) if len(peaks) > 1 else 0
        has_spatial_delay = (len(prefilter_firs) > 1 and delta_samples > 0)

        if has_spatial_delay:
            # Acoustic inter-pickup spatial coherence decay:
            # Multi-string wave dispersion across the 4 strings naturally bounds the fundamental
            # acoustic mid-scoop to an authentic ~11-12 dB depth (gamma_max ≈ 0.88) rather than an
            # artificial single-frequency infinite notch.
            # Dynamically derive transition window from actual impulse peak delay:
            P_coherent = np.abs(np.sum(H_channels, axis=0)) ** 2
            P_incoherent = np.sum(np.abs(H_channels) ** 2, axis=0)
            delta_tau = delta_samples / 48000.0
            f_notch = 1.0 / (2.0 * delta_tau)
            f_start = f_notch
            f_end = 1.7 * f_notch
            t = np.clip((f_bins - f_start) / (f_end - f_start), 0.0, 1.0)
            gamma = 0.88 * 0.5 * (1.0 + np.cos(np.pi * t))
            mag_spectrum = np.sqrt(gamma * P_coherent + (1.0 - gamma) * P_incoherent)
        elif len(H_channels) > 1:
            mag_spectrum = np.abs(np.sum(H_channels, axis=0))
        else:
            mag_spectrum = np.abs(H_channels[0])

        mag_raw = np.interp(freqs, f_bins, mag_spectrum)

    hpf_val = cfg.get("hpf")
    if hpf_val is not None and float(hpf_val) >= 80.0:
        ref_idx = np.argmin(np.abs(freqs - 1000.0))
    elif cfg.get("sensor_type") == "bridge_force":
        ref_idx = np.argmin(np.abs(freqs - 100.0))
    else:
        ref_idx = 0

    ref_val = mag_raw[ref_idx]
    mag_norm = mag_raw / ref_val if ref_val > 0 else mag_raw
    is_circuit_match = bool(circuit_curves and len(circuit_curves) > 0 and np.allclose(circuit_curves[0], 1.0, rtol=1e-3))
    is_full_identity = is_spatial_match and (is_circuit_match if mode == "difference" else True)
    gain_offset = 0.0 if is_full_identity else cfg.get("gain_db", 0.0)
    mag_db = 20.0 * np.log10(np.clip(mag_norm, 1e-5, 20.0)) + gain_offset

    data = {
        "frequency": log_freqs,
        "magnitude_db": mag_db.tolist(),
        "voice_id": voice_id,
        "voice_name": cfg.get("name", voice_id),
        "topology": cfg.get("topology", "Passive Pickup"),
        "description": cfg.get("description", ""),
    }
    if include_mode_col:
        data["mode"] = "Output Voice" if mode == "output" else "Input/Output Difference"

    return pl.DataFrame(data)


def compute_canonical_intermediate_response(freqs: np.ndarray) -> np.ndarray:
    """
    Evaluates the Canonical Intermediate baseline acoustic aperture and flat active buffer.
    Scale length: 34.0", Single 0.75" magnetic slit @ 93.5mm datum from bridge.
    Circuit: Flat unity-gain active buffer (H = 1.0).
    """
    can_coils = [{"strings": ["all"], "position_from_bridge_m": 0.0935, "aperture_width_in": 0.75, "weight": 1.0}]
    h_can_ac = numpy_pickup_acoustic_response(freqs, can_coils, scale_length_m=(0.8636, 0.8636))
    return h_can_ac / max(h_can_ac[0], 1e-9)


def build_universal_targets_dataframe() -> pl.DataFrame:
    """
    Calculates magnitude frequency responses for all 22 Universal Target Voicings relative to
    the Canonical Intermediate baseline: H_backend = H_target / H_canonical.
    """
    freqs = np.asarray(log_freqs, dtype=np.float64)
    h_can_norm = compute_canonical_intermediate_response(freqs)
    db_can = 20.0 * np.log10(np.clip(h_can_norm, 1e-5, 20.0))

    rows = []
    for vid, cfg in sorted(VOICES.items()):
        if vid == "00_canonical_intermediate":
            continue
        if cfg.get("sensor_type") == "direct" or cfg.get("preserve_aperture", False):
            # Direct studio DI target and aperture-preserving active buffers maintain flat 0.00 dB baseline
            db_backend = np.zeros_like(freqs)
        else:
            vdf = build_voice_dataframe(vid, cfg, mode="output")
            db_tgt = np.asarray(vdf["magnitude_db"])
            db_backend = db_tgt - db_can

        vname = cfg.get("name", vid)
        topo = cfg.get("topology", "Target Pickup")
        fr = cfg.get("fr", 0.0)
        q = cfg.get("Q", 0.0)
        desc = cfg.get("description", "")

        for f, m in zip(log_freqs, db_backend):
            rows.append({
                "frequency": float(f),
                "magnitude_db": float(m),
                "voice_id": vid,
                "voice_name": vname,
                "topology": topo,
                "fr": float(fr),
                "Q": float(q),
                "description": desc,
            })
    return pl.DataFrame(rows)


def build_frontend_deconvolutions_dataframe() -> pl.DataFrame:
    """
    Calculates magnitude frequency responses for all Frontend Deconvolutions:
    H_frontend = H_canonical / H_source.
    Demonstrates how each physical instrument and pickup switch position equalizes up/down
    to the 0.00 dB Canonical Intermediate baseline.
    """
    freqs = np.asarray(log_freqs, dtype=np.float64)
    h_can_norm = compute_canonical_intermediate_response(freqs)

    all_insts = load_all_instruments()
    rows = []
    for inst_id, inst in sorted(all_insts.items()):
        if inst_id == "canonical_intermediate":
            continue
        inst_name = inst.get("name", inst_id)
        scale_range = resolve_scale_range(inst)
        scale_in = inst.get("scale_length_in", 34.0)
        pickups = inst.get("pickups", {})

        for p_key, p_cfg in sorted(pickups.items()):
            p_name = p_cfg.get("name", p_key)
            pos_m = p_cfg.get("position_from_bridge_m", 0.0)
            coils = resolve_pickup_coils(p_cfg, inst)
            h_src_ac = numpy_pickup_acoustic_response(freqs, coils, scale_length_m=scale_range)
            h_src_norm = h_src_ac / max(h_src_ac[0], 1e-9)

            h_aperture_deconv = (h_can_norm * h_src_norm) / (h_src_norm**2 + 0.01)

            can_circuit = VOICES.get("00_canonical_intermediate", {}).get("circuit")
            cir_circuit = p_cfg.get("circuit")
            if cir_circuit and can_circuit:
                can_model = load_circuit(can_circuit)
                src_model = load_circuit(cir_circuit)
                diff_curves = compute_differential_circuit_transfer_functions(can_model, src_model, freqs=FREQS)
                h_c_front = np.interp(freqs, FREQS, np.asarray(diff_curves[0], dtype=np.float64))
                h_front = h_aperture_deconv * h_c_front
            else:
                h_c_front = resolve_pickup_electrical_deconvolution(freqs, p_cfg, inst, q_target=0.707)
                h_front = h_aperture_deconv * h_c_front

            db_front = 20.0 * np.log10(np.clip(h_front, 1e-4, 10.0))
            label = f"{inst_name} - {p_name}"

            for f, m in zip(log_freqs, db_front):
                rows.append({
                    "frequency": float(f),
                    "magnitude_db": float(m),
                    "instrument_id": inst_id,
                    "instrument_name": inst_name,
                    "pickup_key": p_key,
                    "pickup_name": p_name,
                    "label": label,
                    "scale_in": float(scale_in),
                    "position_mm": float(pos_m * 1000.0),
                })
    return pl.DataFrame(rows)


def build_instrument_frontend_dataframe(inst: dict[str, Any] | AllomorphBaseModel) -> pl.DataFrame:
    """
    Calculates magnitude frequency responses for all pickup switch positions of a source instrument:
    H_frontend = H_canonical / H_source.
    """
    freqs = np.asarray(log_freqs, dtype=np.float64)
    h_can_norm = compute_canonical_intermediate_response(freqs)

    inst_id = inst.get("id", "instrument")
    inst_name = inst.get("name", inst_id)
    scale_range = resolve_scale_range(inst)
    scale_in = inst.get("scale_length_in", 34.0)
    pickups = inst.get("pickups", {})

    rows = []
    for p_key, p_cfg in sorted(pickups.items()):
        p_name = p_cfg.get("name", p_key)
        pos_m = p_cfg.get("position_from_bridge_m", 0.0)
        coils = resolve_pickup_coils(p_cfg, inst)
        h_src_ac = numpy_pickup_acoustic_response(freqs, coils, scale_length_m=scale_range)
        h_src_norm = h_src_ac / max(h_src_ac[0], 1e-9)

        h_aperture_deconv = (h_can_norm * h_src_norm) / (h_src_norm**2 + 0.01)

        can_circuit = VOICES.get("00_canonical_intermediate", {}).get("circuit")
        cir_circuit = p_cfg.get("circuit")
        if cir_circuit and can_circuit:
            can_model = load_circuit(can_circuit)
            src_model = load_circuit(cir_circuit)
            diff_curves = compute_differential_circuit_transfer_functions(can_model, src_model, freqs=FREQS)
            h_c_front = np.interp(freqs, FREQS, np.asarray(diff_curves[0], dtype=np.float64))
            h_front = h_aperture_deconv * h_c_front
        else:
            h_c_front = resolve_pickup_electrical_deconvolution(freqs, p_cfg, inst, q_target=0.707)
            h_front = h_aperture_deconv * h_c_front

        db_front = 20.0 * np.log10(np.clip(h_front, 1e-4, 10.0))

        for f, m in zip(log_freqs, db_front):
            rows.append({
                "frequency": float(f),
                "magnitude_db": float(m),
                "instrument_id": inst_id,
                "instrument_name": inst_name,
                "pickup_key": p_key,
                "pickup_name": p_name,
                "scale_in": float(scale_in),
                "position_mm": float(pos_m * 1000.0) if pos_m else 0.0,
            })
    return pl.DataFrame(rows)


def build_composite_instrument_dataframe(inst: dict[str, Any] | AllomorphBaseModel) -> pl.DataFrame:
    """
    Calculates the 5-stage physical signal flow progression for a source instrument:
      1. Source Bass Input: Physical response of the source pickup entering Block 1.
      2. Block 1 Deconvolution: 2048-tap FIR inverse filter neutralizing source aperture and RLC impedance.
      3. Canonical Intermediate (0 dB): Standardized neutral baseline datum achieved after Block 1.
      4. Block 2 Target Voicing: Universal target model transfer function.
      5. Target Voice Output: Authentic acoustic target voice produced after Block 2.
    Illustrates: Bass Input -deconvolution-> Canonical Intermediate Baseline -voicing-> Target Output.
    """
    freqs = np.asarray(log_freqs, dtype=np.float64)
    h_can_norm = compute_canonical_intermediate_response(freqs)
    db_can = 20.0 * np.log10(np.clip(h_can_norm, 1e-5, 20.0))

    scale_range = resolve_scale_range(inst)
    pickups = inst.get("pickups", {})
    if not pickups:
        p_default_key = inst.get("default_pickup", "pickup")
        pickups = {p_default_key: {"name": p_default_key}}

    # Precompute target voice responses once
    target_dfs: dict[str, tuple[str, np.ndarray | None]] = {}
    for vid, cfg in sorted(VOICES.items()):
        if vid == "00_canonical_intermediate":
            continue
        vname = cfg.get("name", vid)
        if cfg.get("sensor_type") == "direct":
            target_dfs[vid] = (vname, None)
        else:
            vdf = build_voice_dataframe(vid, cfg, mode="output")
            target_dfs[vid] = (vname, np.asarray(vdf["magnitude_db"], dtype=np.float64))

    rows = []
    can_circuit = VOICES.get("00_canonical_intermediate", {}).get("circuit")
    can_model = load_circuit(can_circuit) if can_circuit else None

    for p_key, p_cfg in sorted(pickups.items()):
        p_name = p_cfg.get("name", p_key)
        coils = resolve_pickup_coils(p_cfg, inst)
        h_src_ac = numpy_pickup_acoustic_response(freqs, coils, scale_length_m=scale_range)
        h_src_norm = h_src_ac / max(h_src_ac[0], 1e-9)
        h_aperture_deconv = (h_can_norm * h_src_norm) / (h_src_norm**2 + 0.01)

        cir_circuit = p_cfg.get("circuit")
        if cir_circuit and can_model:
            src_model = load_circuit(cir_circuit)
            diff_curves = compute_differential_circuit_transfer_functions(can_model, src_model, freqs=FREQS)
            h_c_front = np.interp(freqs, FREQS, np.asarray(diff_curves[0], dtype=np.float64))
            h_front = h_aperture_deconv * h_c_front
        else:
            h_c_front = resolve_pickup_electrical_deconvolution(freqs, p_cfg, inst, q_target=0.707)
            h_front = h_aperture_deconv * h_c_front

        db_front = 20.0 * np.log10(np.clip(h_front, 1e-4, 10.0))
        # Bass Input entering Block 1 (which deconvolution inverts to reach 0 dB)
        db_src = -db_front
        db_ci = np.zeros_like(db_front)

        for vid, (vname, db_tgt) in target_dfs.items():
            if db_tgt is None:  # Source Direct
                db_back = -db_front
                db_out = np.zeros_like(db_front)
            else:
                db_back = db_tgt - db_can
                db_out = db_tgt

            for f, m in zip(log_freqs, db_src):
                rows.append({"frequency": float(f), "magnitude_db": float(m), "stage": "1. Source Bass Input", "voice_name": vname, "pickup_name": p_name})
            for f, m in zip(log_freqs, db_front):
                rows.append({"frequency": float(f), "magnitude_db": float(m), "stage": "2. Block 1 Deconvolution", "voice_name": vname, "pickup_name": p_name})
            for f, m in zip(log_freqs, db_ci):
                rows.append({"frequency": float(f), "magnitude_db": float(m), "stage": "3. Canonical Intermediate (0 dB)", "voice_name": vname, "pickup_name": p_name})
            for f, m in zip(log_freqs, db_back):
                rows.append({"frequency": float(f), "magnitude_db": float(m), "stage": "4. Block 2 Target Voicing", "voice_name": vname, "pickup_name": p_name})
            for f, m in zip(log_freqs, db_out):
                rows.append({"frequency": float(f), "magnitude_db": float(m), "stage": "5. Target Voice Output", "voice_name": vname, "pickup_name": p_name})

    return pl.DataFrame(rows)
