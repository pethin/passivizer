"""
Allomorph - Interactive Visualizer & Frequency Analyzer
Uses Polars and Altair to model, analyze, and render interactive frequency
response curves for all Master Voices across source bass instruments.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path
import numpy as np
import polars as pl
import altair as alt

alt.data_transformers.disable_max_rows()

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
DOCS_DIR = REPO_ROOT / "docs"
RESPONSES_DIR = DOCS_DIR / "frequency_responses"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import (
    VOICES,
    SCALES,
    INSTRUMENTS,
    FREQS,
    load_instrument,
    load_all_instruments,
    get_source_pickup,
    resolve_pickup_coils,
    resolve_voice_coils,
    resolve_voice_pickups,
    compute_effective_position,
    numpy_pickup_acoustic_response,
    numpy_pickup_macro_aperture,
    resolve_pickup_electrical_deconvolution,
    is_voice_matching_source,
    get_instrument_string,
    get_voice_string,
    compute_differential_string_transfer,
    compute_differential_longitudinal_transfer,
    compute_voice_prefilter_firs,
    synthesize_minimum_phase_fir,
    MEAN_BASS_F0,
    resolve_scale_range,
)
from simulate_circuits import (
    CIRCUITS_DIR,
    parse_netlist,
    compute_circuit_transfer_functions,
    compute_differential_circuit_transfer_functions,
    apply_magnet_properties_to_model,
)

NUM_POINTS = 600
F_MIN = 20.0
F_MAX = 20000.0

log_freqs = [F_MIN * (F_MAX / F_MIN) ** (i / (NUM_POINTS - 1)) for i in range(NUM_POINTS)]

def build_voice_dataframe(voice_id, cfg, instrument="30in", src_scale=None, mode="difference", include_mode_col=False):
    """
    Calculates magnitude frequency response in dB for a voice using NumPy vector math and Polars.
    mode="output": Absolute acoustic aperture + loaded SPICE circuit frequency response of the target voice.
    mode="difference": Regularized differential transfer function (H_target / H_source) applied to the source instrument.
    """
    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    tgt_scale = cfg.get("scale", "34in")
    tgt = SCALES[tgt_scale]
    tgt_speeds = tgt["speeds"]

    freqs = np.asarray(log_freqs, dtype=np.float64)
    pickups = resolve_voice_pickups(cfg)
    cir_rel = cfg.get("circuit", f"circuits/{voice_id}.cir")
    cir_path = REPO_ROOT / cir_rel
    if not cir_path.exists():
        cir_path = CIRCUITS_DIR / f"{voice_id}.cir"

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
        if cir_path.exists():
            model = parse_netlist(cir_path)
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
            tgt_scale_range = resolve_scale_range(tgt if tgt_scale in SCALES else tgt_scale)
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
                weight_fac = 1.0 if (cir_path.exists() and len(circuit_curves) > 1) else p_weight

                ac = numpy_pickup_acoustic_response(f_bins, p["coils"], scale_length_m=tgt_scale_range) * (weight_fac * p_pol)
                fir_ac = synthesize_minimum_phase_fir(ac, num_taps=2048, normalize=False)
                tau_i = (pos_max - positions[i]) / c_mean if len(pickups) > 1 else 0.0
                delay_samples = int(round(tau_i * 48000.0))
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

        src_cir_rel = src_pickup.get("circuit")
        if not src_cir_rel and is_passive:
            src_cir_rel = "circuits/sources/source_standard_p.cir"
        src_cir_path = (REPO_ROOT / src_cir_rel) if src_cir_rel else None

        if src_cir_path and src_cir_path.exists() and cir_path.exists():
            model = parse_netlist(cir_path)
            apply_magnet_properties_to_model(model, cfg)
            src_model = parse_netlist(src_cir_path)
            apply_magnet_properties_to_model(src_model, src_pickup)
            circuit_curves = compute_differential_circuit_transfer_functions(model, src_model, freqs=FREQS)
        elif cir_path.exists():
            model = parse_netlist(cir_path)
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

    if cfg.get("hpf") and cfg.get("hpf") >= 80.0:
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

def append_spec_panel(html_path: Path, panel_html: str):
    """Appends an informational HTML spec/directive panel before </body>."""
    content = html_path.read_text(encoding="utf-8")
    if "</body>" in content:
        content = content.replace("</body>", f"{panel_html}\n</body>")
        html_path.write_text(content, encoding="utf-8")

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

def generate_universal_targets_chart(target_path: Path = None) -> Path:
    """
    Renders the Mode 1 Universal Target Voicings chart (Block 2):
    Evaluates all 22 target voices relative to Canonical Intermediate (34" @ 93.5mm datum).
    Includes the 3 Dynamic Feel Tiers specification panel (Clean, Dynamic, Hot Rod).
    """
    if target_path is None:
        target_path = RESPONSES_DIR / "universal_targets.html"
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    master_df = build_universal_targets_dataframe()
    voice_selection = alt.selection_point(fields=["voice_name"], bind="legend")

    chart = (
        alt.Chart(master_df)
        .mark_line(strokeWidth=2.2)
        .encode(
            x=alt.X(
                "frequency:Q",
                scale=alt.Scale(type="log", domain=[20, 20000]),
                title="Frequency (Hz)",
                axis=alt.Axis(
                    values=[20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
                    grid=True,
                    gridDash=[3, 3],
                    gridColor="#333333"
                )
            ),
            y=alt.Y(
                "magnitude_db:Q",
                scale=alt.Scale(domain=[-30, 15]),
                title="Voicing Magnitude relative to Intermediate (dB)",
                axis=alt.Axis(grid=True, gridDash=[3, 3], gridColor="#333333")
            ),
            color=alt.Color(
                "voice_name:N",
                title="Universal Target Voice (Click to isolate)",
                scale=alt.Scale(scheme="tableau20")
            ),
            opacity=alt.condition(voice_selection, alt.value(1.0), alt.value(0.12)),
            strokeWidth=alt.condition(voice_selection, alt.value(2.8), alt.value(1.0)),
            tooltip=[
                alt.Tooltip("voice_name:N", title="Pickup Configuration"),
                alt.Tooltip("topology:N", title="Topology"),
                alt.Tooltip("description:N", title="Circuit / Acoustic Description"),
                alt.Tooltip("frequency:Q", title="Frequency (Hz)", format=".1f"),
                alt.Tooltip("magnitude_db:Q", title="Magnitude (dB)", format="+.1f")
            ]
        )
        .add_params(voice_selection)
        .properties(
            title=alt.TitleParams(
                text="Allomorph Master Voices: Universal Target Voicings (Block 2)",
                subtitle="Target Passive Acoustic Apertures & SPICE Loaded RLC Resonances relative to Canonical Intermediate Baseline (34\" @ 93.5mm)",
                fontSize=16,
                subtitleFontSize=12,
                anchor="start"
            ),
            width=740,
            height=480
        )
        .configure_view(strokeWidth=0)
        .configure_legend(orient="right", labelLimit=320)
        .interactive()
    )

    chart.save(str(target_path))

    spec_panel = """
<style>
  body {
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 12px 16px;
    margin: 0;
    overflow-x: hidden;
    box-sizing: border-box;
  }
  #vis {
    display: flex;
    justify-content: center;
    width: 100%;
    overflow-x: hidden;
  }
  .tiers-container { max-width: 1060px; margin: 14px auto 0 auto; display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .tier-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 6px; }
  .tier-header { display: flex; align-items: center; justify-content: space-between; }
  .tier-title { font-size: 13px; font-weight: 700; color: #f0f6fc; }
  .tier-badge { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase; }
  .badge-clean { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #38bdf8; }
  .badge-dynamic, .badge-standard { background: rgba(74, 222, 128, 0.15); color: #4ade80; border: 1px solid #4ade80; }
  .badge-hotrod { background: rgba(248, 113, 113, 0.15); color: #f87171; border: 1px solid #f87171; }
  .tier-desc { font-size: 11px; color: #8b949e; line-height: 1.4; }
  .tier-formula { font-family: monospace; font-size: 11px; color: #58a6ff; background: #0d1117; padding: 4px 6px; border-radius: 4px; margin-top: 4px; }
</style>
<div class="tiers-container">
  <div class="tier-card">
    <div class="tier-header">
      <span class="tier-title">01 Studio Clean</span>
      <span class="tier-badge badge-clean">cln_</span>
    </div>
    <div class="tier-desc">0% Saturation / Maximum Headroom. Pure linear RLC resonance response with zero magnetic compression. Ideal for pristine DI and clean funk.</div>
    <div class="tier-formula">&alpha; = 0.00 | V_sat = 10.0V</div>
  </div>
  <div class="tier-card">
    <div class="tier-header">
      <span class="tier-title">02 Standard Dynamic</span>
      <span class="tier-badge badge-standard">std_</span>
    </div>
    <div class="tier-desc">Standard Give & Bloom. 100% nominal target dynamic modeling: magnetic string drag damping, 2f0 orbit bloom, dynamic inductance sag (&lambda;_L), and soft-knee compression.</div>
    <div class="tier-formula">&alpha; = &alpha;_tgt | V_sat = V_tgt</div>
  </div>
  <div class="tier-card">
    <div class="tier-header">
      <span class="tier-title">03 Hot Rod</span>
      <span class="tier-badge badge-hotrod">hot_</span>
    </div>
    <div class="tier-desc">175% Overwound Pre-Conditioner. Saturated attack give, compressed low-mids, and elevated harmonic punch to drive downstream Darkglass engines.</div>
    <div class="tier-formula">&alpha; = 1.75 &times; &alpha;_tgt | V_sat / 1.35</div>
  </div>
</div>
"""
    append_spec_panel(target_path, spec_panel)
    print(f"Saved Universal Target Voicings visualization: {target_path}")
    return target_path

def build_frontend_deconvolutions_dataframe() -> pl.DataFrame:
    """
    Calculates magnitude frequency responses for all 33 Frontend Deconvolutions:
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

            cir_rel = p_cfg.get("circuit")
            can_path = REPO_ROOT / "circuits" / "canonical_intermediate.cir"
            if cir_rel and (REPO_ROOT / cir_rel).exists() and can_path.exists():
                can_model = parse_netlist(can_path)
                src_model = parse_netlist(REPO_ROOT / cir_rel)
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

def build_instrument_frontend_dataframe(inst: dict) -> pl.DataFrame:
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

        cir_rel = p_cfg.get("circuit")
        can_path = REPO_ROOT / "circuits" / "canonical_intermediate.cir"
        if cir_rel and (REPO_ROOT / cir_rel).exists() and can_path.exists():
            can_model = parse_netlist(can_path)
            src_model = parse_netlist(REPO_ROOT / cir_rel)
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

def generate_instrument_frontend_chart(inst: dict, target_path: Path = None) -> Path:
    """
    Renders the Frontend Deconvolutions chart (Block 1) for a single source instrument.
    Allows users to click any pickup switch position in the legend to isolate that specific pickup key.
    """
    inst_id = inst.get("id", "instrument")
    inst_name = inst.get("name", inst_id)
    if target_path is None:
        target_path = RESPONSES_DIR / f"{inst_id}_frontend.html"
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    df = build_instrument_frontend_dataframe(inst)
    pickup_selection = alt.selection_point(fields=["pickup_name"], bind="legend")

    rule_df = pl.DataFrame({"frequency": [20.0, 20000.0], "magnitude_db": [0.0, 0.0]})
    baseline = (
        alt.Chart(rule_df)
        .mark_line(color="#8b949e", strokeDash=[6, 4], strokeWidth=1.5)
        .encode(x="frequency:Q", y="magnitude_db:Q")
    )

    lines = (
        alt.Chart(df)
        .mark_line(strokeWidth=2.2)
        .encode(
            x=alt.X(
                "frequency:Q",
                scale=alt.Scale(type="log", domain=[20, 20000]),
                title="Frequency (Hz)",
                axis=alt.Axis(
                    values=[20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
                    grid=True,
                    gridDash=[3, 3],
                    gridColor="#333333"
                )
            ),
            y=alt.Y(
                "magnitude_db:Q",
                scale=alt.Scale(domain=[-8, 12]),
                title="Frontend Deconvolution Gain (dB)",
                axis=alt.Axis(
                    values=[-8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12],
                    grid=True,
                    gridDash=[3, 3],
                    gridColor="#333333"
                )
            ),
            color=alt.Color(
                "pickup_name:N",
                title="Pickup Switch Position (Click to isolate)",
                scale=alt.Scale(scheme="category10")
            ),
            tooltip=[
                alt.Tooltip("pickup_name:N", title="Pickup Switch Position"),
                alt.Tooltip("position_mm:Q", title="Bridge Distance (mm)", format=".1f"),
                alt.Tooltip("frequency:Q", title="Frequency (Hz)", format=".1f"),
                alt.Tooltip("magnitude_db:Q", title="Gain / Cut (dB)", format="+.1f")
            ],
            opacity=alt.condition(pickup_selection, alt.value(0.96), alt.value(0.12)),
            strokeWidth=alt.condition(pickup_selection, alt.value(3.0), alt.value(1.2))
        )
    )

    chart = (
        alt.layer(lines, baseline)
        .add_params(pickup_selection)
        .properties(
            title=alt.TitleParams(
                text=f"Allomorph Frontend Deconvolutions: {inst_name} (Block 1)",
                subtitle="Inverting Physical Pickup Aperture Sinc & RLC Impedance to Canonical Intermediate Baseline (0.00 dB Target)",
                fontSize=16,
                subtitleFontSize=12,
                anchor="start"
            ),
            width=740,
            height=480
        )
        .configure_view(strokeWidth=0)
        .configure_legend(orient="right", labelLimit=320)
        .interactive()
    )

    chart.save(str(target_path))

    panel = """
<style>
  body {
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 12px 16px;
    margin: 0;
    overflow-x: hidden;
    box-sizing: border-box;
  }
  #vis {
    display: flex;
    justify-content: center;
    width: 100%;
    overflow-x: hidden;
  }
  .info-container {
    max-width: 1060px;
    margin: 14px auto 0 auto;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px;
    font-size: 12px;
    color: #8b949e;
    line-height: 1.5;
  }
  .info-title { color: #f0f6fc; font-weight: 700; margin-bottom: 4px; }
  .highlight { color: #58a6ff; font-weight: 600; }
</style>
<div class="info-container">
  <div class="info-title">Block 1 Operational Directives:</div>
  <div>1. <span class="highlight">Knobs Wide Open (100%):</span> Source bass volume and tone knobs must be wide open (100%) so that passive pot loading matches the deconvolution netlist exactly.</div>
  <div>2. <span class="highlight">Strictly Positive Initial Polarity:</span> All FIRs enforce strictly positive initial polarity (&sum; h[:16] &gt; 0) to ensure zero phase cancellation when blended in parallel with DI.</div>
  <div>3. <span class="highlight">Zero-Latency Causal Synthesis:</span> 2048-tap minimum-phase causal FIRs run on Darkglass Anagram Block 1 with 0% DSP overhead and zero perceptible latency.</div>
</div>
"""
    content = target_path.read_text(encoding="utf-8")
    content = content.replace("</body>", f"{panel}</body>")
    target_path.write_text(content, encoding="utf-8")
    print(f"Saved Frontend Deconvolution chart for {inst_name}: {target_path}")
    return target_path

def generate_frontend_deconvolutions_chart(target_path: Path = None) -> Path:
    """
    Renders the Mode 2 Frontend Deconvolutions master page (Block 1).
    Provides an instrument selector linking to each source instrument's dedicated frontend chart,
    allowing users to click and isolate individual pickup keys/positions.
    """
    if target_path is None:
        target_path = RESPONSES_DIR / "frontend_deconvolutions.html"
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    all_insts = load_all_instruments()
    inst_items = []
    for iid, icfg in sorted(all_insts.items()):
        if iid == "canonical_intermediate":
            continue
        iname = icfg.get("name", iid)
        inst_chart_file = target_path.parent / f"{iid}_frontend.html"
        generate_instrument_frontend_chart(icfg, target_path=inst_chart_file)
        inst_items.append({"id": iid, "name": iname, "url": f"{iid}_frontend.html"})

    default_item = inst_items[0] if inst_items else {"id": "30in_emg_mmtw", "url": "30in_emg_mmtw_frontend.html"}
    options_html = "\n".join([f'        <option value="{item["url"]}">{item["name"]}</option>' for item in inst_items])
    tabs_html = "\n".join([f'      <button class="inst-tab-btn{" active" if item["id"] == default_item["id"] else ""}" data-url="{item["url"]}" onclick="switchInstrument(\'{item["url"]}\', this)">{item["name"]}</button>' for item in inst_items])

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Allomorph Master Voices: Frontend Deconvolutions (Block 1)</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --accent: #38bdf8;
      --text: #f0f6fc;
      --text-muted: #8b949e;
      --tag-bg: #21262d;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg) !important;
      color: #c9d1d9 !important;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      padding: 12px 16px;
      margin: 0;
      overflow-x: hidden;
    }}
    .header-card {{
      max-width: 1060px;
      margin: 0 auto 12px auto;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .header-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .header-title {{
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .inst-picker-select {{
      background: var(--tag-bg);
      border: 1px solid var(--border);
      color: var(--text);
      font-size: 12px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 6px;
      outline: none;
      cursor: pointer;
    }}
    .inst-picker-select:focus {{
      border-color: var(--accent);
    }}
    .inst-tabs-wrap {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      border-top: 1px solid var(--border);
      padding-top: 10px;
    }}
    .inst-tab-btn {{
      background: var(--tag-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 600;
      padding: 5px 10px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    .inst-tab-btn:hover {{
      background: #30363d;
      color: var(--text);
    }}
    .inst-tab-btn.active {{
      background: rgba(56, 189, 248, 0.16);
      color: #38bdf8;
      border-color: #38bdf8;
    }}
    .chart-frame-wrap {{
      max-width: 1060px;
      margin: 0 auto;
      display: flex;
      justify-content: center;
    }}
    .chart-frame {{
      width: 100%;
      height: 720px;
      border: none;
      border-radius: 8px;
      background: var(--bg);
    }}
    #pickup-sublevel {{ display: none; }}
  </style>
  <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/vega@6"></script>
  <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/vega-lite@6.4.1"></script>
  <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/vega-embed@7"></script>
</head>
<body>
  <div class="header-card">
    <div class="header-row">
      <div class="header-title">
        <span>Frontend Deconvolutions (Block 1) — Per-Instrument Pickup Key Selector</span>
      </div>
      <div>
        <select id="inst-select" class="inst-picker-select" onchange="switchInstrument(this.value)">
{options_html}
        </select>
      </div>
    </div>
    <div class="inst-tabs-wrap">
{tabs_html}
    </div>
  </div>

  <div id="pickup-sublevel"></div>

  <div class="chart-frame-wrap">
    <iframe id="frontend-frame" class="chart-frame" src="{default_item['url']}" title="Per-Instrument Frontend Deconvolutions Chart"></iframe>
  </div>

  <script>
    // vegaEmbed reference for embedded and sub-frame charts
    if (typeof vegaEmbed !== 'undefined') {{
      window.vegaEmbed = vegaEmbed;
    }}
    function switchInstrument(url, btnEl) {{
      const frame = document.getElementById('frontend-frame');
      if (frame) frame.src = url;
      const sel = document.getElementById('inst-select');
      if (sel) sel.value = url;
      document.querySelectorAll('.inst-tab-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.getAttribute('data-url') === url);
      }});
    }}
  </script>
</body>
</html>
"""
    target_path.write_text(html_content, encoding="utf-8")
    print(f"Saved Frontend Deconvolutions master page: {target_path}")
    return target_path

def build_composite_instrument_dataframe(inst: dict) -> pl.DataFrame:
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
    target_dfs = {}
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
    can_path = REPO_ROOT / "circuits" / "canonical_intermediate.cir"
    can_model = parse_netlist(can_path) if can_path.exists() else None

    for p_key, p_cfg in sorted(pickups.items()):
        p_name = p_cfg.get("name", p_key)
        coils = resolve_pickup_coils(p_cfg, inst)
        h_src_ac = numpy_pickup_acoustic_response(freqs, coils, scale_length_m=scale_range)
        h_src_norm = h_src_ac / max(h_src_ac[0], 1e-9)
        h_aperture_deconv = (h_can_norm * h_src_norm) / (h_src_norm**2 + 0.01)

        cir_rel = p_cfg.get("circuit")
        if cir_rel and (REPO_ROOT / cir_rel).exists() and can_model:
            src_model = parse_netlist(REPO_ROOT / cir_rel)
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

def generate_composite_instrument_chart(instrument="30in", out_html=None) -> Path:
    """
    Renders the Signal Flow Inspector chart:
      1. Source Bass Input (Entering Block 1)
      2. Block 1 Deconvolution (Inverse Filter)
      3. Canonical Intermediate (0 dB Neutral Baseline)
      4. Block 2 Target Voicing (Universal Target Profile)
      5. Target Voice Output (Authentic Target Voice)
    Illustrates: Bass Input -deconvolution-> Canonical Intermediate Baseline -voicing-> Target Output.
    """
    inst = load_instrument(instrument) if not isinstance(instrument, dict) else instrument
    inst_id = inst.get("id", "custom_instrument")
    inst_name = inst.get("name", inst_id)

    if out_html is None:
        target_path = RESPONSES_DIR / f"{inst_id}.html"
    else:
        p = Path(out_html)
        if p.is_dir() or (not p.suffix and not p.exists()):
            target_path = p / f"{inst_id}.html"
        else:
            target_path = p
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    master_df = build_composite_instrument_dataframe(inst)
    voice_names = master_df["voice_name"].unique().sort().to_list()
    default_voice = voice_names[0] if voice_names else ""

    pickup_names = master_df["pickup_name"].unique().sort().to_list()
    default_pickup = pickup_names[0] if pickup_names else ""

    voice_select = alt.selection_point(
        fields=["voice_name"],
        bind=alt.binding_select(
            options=voice_names,
            name="Target Voicing (Block 2): "
        ),
        value=default_voice
    )

    stage_selection = alt.selection_point(fields=["stage"], bind="legend")

    stage_order = [
        "1. Source Bass Input",
        "2. Block 1 Deconvolution",
        "3. Canonical Intermediate (0 dB)",
        "4. Block 2 Target Voicing",
        "5. Target Voice Output"
    ]
    color_scale = alt.Scale(
        domain=stage_order,
        range=["#38bdf8", "#26a69a", "#8b949e", "#ff7043", "#ffd54f"]
    )
    dash_scale = alt.Scale(
        domain=stage_order,
        range=[[0], [3, 3], [6, 4], [8, 4], [0]]
    )

    base_chart = (
        alt.Chart(master_df)
        .mark_line()
        .encode(
            x=alt.X(
                "frequency:Q",
                scale=alt.Scale(type="log", domain=[20, 20000]),
                title="Frequency (Hz)",
                axis=alt.Axis(
                    values=[20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
                    grid=True,
                    gridDash=[3, 3],
                    gridColor="#333333"
                )
            ),
            y=alt.Y(
                "magnitude_db:Q",
                scale=alt.Scale(domain=[-30, 24]),
                title="Magnitude / Gain (dB)",
                axis=alt.Axis(
                    values=[-24, -18, -12, -6, 0, 6, 12, 18, 24],
                    grid=True,
                    gridDash=[3, 3],
                    gridColor="#333333"
                )
            ),
            color=alt.Color(
                "stage:O",
                scale=color_scale,
                sort=stage_order,
                title="Signal Flow Stage (Click to isolate)"
            ),
            strokeDash=alt.StrokeDash(
                "stage:O",
                scale=dash_scale,
                sort=stage_order,
                title="Signal Flow Stage (Click to isolate)"
            ),
            opacity=alt.condition(stage_selection, alt.value(0.96), alt.value(0.12)),
            strokeWidth=alt.StrokeWidth(
                "stage:O",
                scale=alt.Scale(domain=stage_order, range=[2.2, 1.8, 1.5, 1.8, 3.2]),
                sort=stage_order,
                legend=None
            ),
            tooltip=[
                alt.Tooltip("stage:O", title="Signal Stage"),
                alt.Tooltip("pickup_name:N", title="Source Pickup"),
                alt.Tooltip("voice_name:N", title="Target Voicing"),
                alt.Tooltip("frequency:Q", title="Frequency (Hz)", format=".1f"),
                alt.Tooltip("magnitude_db:Q", title="Magnitude (dB)", format="+.1f")
            ]
        )
    )

    if len(pickup_names) > 1:
        pickup_select = alt.selection_point(
            fields=["pickup_name"],
            bind=alt.binding_select(
                options=pickup_names,
                name="Source Pickup (Block 1): "
            ),
            value=default_pickup
        )
        chart = (
            base_chart
            .add_params(voice_select, pickup_select, stage_selection)
            .transform_filter(voice_select)
            .transform_filter(pickup_select)
        )
    else:
        chart = (
            base_chart
            .add_params(voice_select, stage_selection)
            .transform_filter(voice_select)
        )

    chart = (
        chart.properties(
            title=alt.TitleParams(
                text=f"Allomorph Master Voices: Signal Flow Inspector ({inst_name})",
                subtitle="Signal Flow: Source Bass Input ➔ [Block 1 Deconvolution] ➔ Canonical Intermediate (0 dB) ➔ [Block 2 Voicing] ➔ Target Output",
                fontSize=16,
                subtitleFontSize=12,
                anchor="start"
            ),
            width=740,
            height=480
        )
        .configure_view(strokeWidth=0)
        .configure_legend(orient="right", labelLimit=320)
        .interactive()
    )

    chart.save(str(target_path))

    spec_panel = f"""
<style>
  body {{
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 12px 16px;
    margin: 0;
    overflow-x: hidden;
    box-sizing: border-box;
  }}
  #vis {{
    display: flex;
    justify-content: center;
    width: 100%;
    overflow-x: hidden;
  }}
  .composite-banner {{
    max-width: 1060px;
    margin: 14px auto 0 auto;
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    font-size: 11px;
  }}
  .comp-item {{ display: flex; flex-direction: column; gap: 4px; }}
  .comp-title {{ font-weight: 700; display: flex; align-items: center; gap: 6px; }}
  .dot-cyan {{ width: 8px; height: 8px; border-radius: 50%; background: #38bdf8; display: inline-block; }}
  .dot-teal {{ width: 8px; height: 8px; border-radius: 50%; background: #26a69a; display: inline-block; }}
  .dot-gray {{ width: 8px; height: 8px; border-radius: 50%; background: #8b949e; display: inline-block; }}
  .dot-orange {{ width: 8px; height: 8px; border-radius: 50%; background: #ff7043; display: inline-block; }}
  .dot-gold {{ width: 8px; height: 8px; border-radius: 50%; background: #ffd54f; display: inline-block; }}
  .comp-desc {{ color: #8b949e; line-height: 1.4; }}
</style>
<div class="composite-banner">
  <div class="comp-item">
    <div class="comp-title"><span class="dot-cyan"></span> 1. Source Bass Input</div>
    <div class="comp-desc">Cyan curve: Physical acoustic aperture and RLC loading of the selected source pickup entering Block 1.</div>
  </div>
  <div class="comp-item">
    <div class="comp-title"><span class="dot-teal"></span> 2. Block 1 Deconvolution</div>
    <div class="comp-desc">Dotted Teal curve: 2048-tap FIR deconvolution filter neutralizing pickup placement and electrical impedance.</div>
  </div>
  <div class="comp-item">
    <div class="comp-title"><span class="dot-gray"></span> 3. Canonical Intermediate (0 dB)</div>
    <div class="comp-desc">Dashed Gray line: Standardized neutral baseline achieved when Source Input passes through Block 1.</div>
  </div>
  <div class="comp-item">
    <div class="comp-title"><span class="dot-orange"></span> 4. Block 2 Target Voicing</div>
    <div class="comp-desc">Dashed Orange curve: Universal target acoustic aperture & SPICE netlist shaping applied by Block 2 NAM.</div>
  </div>
  <div class="comp-item">
    <div class="comp-title"><span class="dot-gold"></span> 5. Target Voice Output</div>
    <div class="comp-desc">Solid Gold curve: Authentic target acoustic voice produced at output (Canonical Baseline + Voicing).</div>
  </div>
</div>
"""
    append_spec_panel(target_path, spec_panel)
    print(f"Saved Signal Flow Inspector chart: {target_path}")
    return target_path

def format_instrument_meta(inst):
    """Formats an instrument dictionary into metadata suitable for the portal."""
    inst_id = inst.get("id", "custom")
    inst_name = inst.get("name", inst_id)
    scale_in = inst.get("scale_length_in", 34.0)
    scale_m = inst.get("scale_length_m", scale_in * 0.0254)
    speeds = inst.get("string_wave_speeds", [])
    speeds_str = ", ".join(f"{s:.1f} m/s" for s in speeds) if speeds else "N/A"

    pickups = inst.get("pickups", {})
    parts = []
    for pid, pcfg in pickups.items():
        if pcfg.get("type") == "composite":
            continue
        pname = pcfg.get("name", pid)
        pos_m = pcfg.get("position_from_bridge_m")
        if pos_m:
            pos_mm = pos_m * 1000.0
            parts.append(f"{pname} (@ {pos_mm:.1f}mm)")
        else:
            parts.append(pname)
    pickups_summary = " | ".join(parts) if parts else "Standard Pickups"

    return {
        "id": inst_id,
        "name": inst_name,
        "scale_in": scale_in,
        "scale_m": round(scale_m, 4),
        "speeds_str": speeds_str,
        "pickups_summary": pickups_summary,
        "default_pickup": inst.get("default_pickup", "default"),
    }

def build_portal_html(instruments_meta, default_id, base_url_prefix="./"):
    """Constructs a responsive, dark-mode portal HTML string with 3-way Architecture C signal flow navigation."""
    meta_json = json.dumps(instruments_meta, indent=2)

    buttons_html = []
    for inst_id, meta in instruments_meta.items():
        is_active = " active" if inst_id == default_id else ""
        buttons_html.append(
            f'<button class="tab-btn{is_active}" data-id="{inst_id}" onclick="selectInstrument(\'{inst_id}\')">'
            f'<span>{meta["name"]}</span>'
            f'</button>'
        )
    tabs_markup = "\n    ".join(buttons_html)

    default_meta = instruments_meta.get(default_id, next(iter(instruments_meta.values())))
    default_standalone_url = f"{base_url_prefix}{default_id}.html"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Allomorph | Two-Stage Frequency Response Suite</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --card-hover: #1c2128;
      --border: #30363d;
      --accent: #38bdf8;
      --accent-hover: #0ea5e9;
      --accent-subtle: rgba(56, 189, 248, 0.12);
      --text: #f0f6fc;
      --text-muted: #8b949e;
      --tag-bg: #21262d;
      --btn-active: #1f6feb;
      --teal: #26a69a;
      --orange: #ff7043;
      --gold: #ffd54f;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{
      max-width: 1280px;
      margin: 0 auto;
    }}
    .header {{
      margin-bottom: 16px;
    }}
    .header h1 {{
      font-size: 24px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .header .badge {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      background: var(--accent-subtle);
      color: var(--accent);
      border: 1px solid var(--accent);
      padding: 2px 8px;
      border-radius: 12px;
    }}
    .header .subtitle {{
      font-size: 14px;
      color: var(--text-muted);
      margin-top: 6px;
    }}
    .flow-pipeline-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 18px;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      overflow-x: auto;
    }}
    .flow-step {{
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 150px;
    }}
    .flow-step-num {{
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      font-weight: 700;
    }}
    .flow-step-title {{
      font-size: 13px;
      font-weight: 700;
      color: var(--text);
    }}
    .flow-step-desc {{
      font-size: 11px;
      color: var(--text-muted);
      line-height: 1.3;
    }}
    .flow-step.flow-active .flow-step-num {{
      color: var(--accent);
    }}
    .flow-arrow {{
      color: var(--border);
      font-size: 18px;
      font-weight: 700;
      padding: 0 4px;
    }}
    .primary-nav-bar {{
      display: flex;
      gap: 10px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }}
    .primary-nav-btn {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 10px 18px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s ease;
    }}
    .primary-nav-btn:hover {{
      background: var(--tag-bg);
      color: var(--text);
      border-color: #8b949e;
    }}
    .primary-nav-btn.active {{
      background: var(--btn-active);
      border-color: #388bfd;
      color: #ffffff;
      box-shadow: 0 0 12px rgba(31, 111, 235, 0.4);
    }}
    .inspector-subcontrols {{
      display: block;
    }}
    .tabs-container {{
      margin-bottom: 14px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .tab-btn {{
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .tab-btn:hover {{
      background-color: var(--tag-bg);
      color: var(--text);
      border-color: #8b949e;
    }}
    .tab-btn.active {{
      background-color: #238636;
      border-color: #2ea043;
      color: #ffffff;
      box-shadow: 0 0 8px rgba(46, 160, 67, 0.4);
    }}
    .view-mode-bar {{
      margin-bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 16px;
    }}
    .mode-toggle-group {{
      display: inline-flex;
      background-color: var(--tag-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 3px;
      gap: 4px;
      flex-wrap: wrap;
    }}
    .mode-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 6px 14px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }}
    .mode-btn:hover {{
      color: var(--text);
      background-color: rgba(255, 255, 255, 0.05);
    }}
    .mode-btn.active {{
      background-color: var(--btn-active);
      color: #ffffff;
      box-shadow: 0 0 8px rgba(31, 111, 235, 0.4);
    }}
    .mode-hint {{
      font-size: 12px;
      color: var(--text-muted);
      font-style: italic;
    }}
    .meta-panel {{
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 20px;
      margin-bottom: 20px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)) auto;
      gap: 16px;
      align-items: center;
    }}
    .meta-item .label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-muted);
      font-weight: 600;
    }}
    .meta-item .value {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      margin-top: 2px;
    }}
    .open-standalone-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background-color: var(--tag-bg);
      border: 1px solid var(--border);
      color: var(--accent);
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.15s ease;
      white-space: nowrap;
    }}
    .open-standalone-btn:hover {{
      background-color: #30363d;
      color: #ffffff;
      border-color: var(--accent);
    }}
    .chart-card {{
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }}
    iframe {{
      width: 100%;
      min-height: 720px;
      height: 760px;
      border: none;
      display: block;
      background-color: #0d1117;
      overflow: hidden;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Allomorph Frequency Response Suite <span class="badge">Architecture C</span> <span class="badge">Two-Stage Signal Flow</span></h1>
      <div class="subtitle">Universal 2-Stage Acoustic Aperture Deconvolution & SPICE Digital Twins for Darkglass Anagram & Neural Amp Modeler.</div>
    </div>

    <div class="flow-pipeline-card">
      <div class="flow-step">
        <div class="flow-step-num">Step 1</div>
        <div class="flow-step-title">Source Bass</div>
        <div class="flow-step-desc">Physical pickups & scale (Knobs wide open 100%)</div>
      </div>
      <div class="flow-arrow">&rarr;</div>
      <div class="flow-step flow-active">
        <div class="flow-step-num">Block 1</div>
        <div class="flow-step-title">Frontend IR</div>
        <div class="flow-step-desc">2048-tap causal minimum-phase FIR</div>
      </div>
      <div class="flow-arrow">&rarr;</div>
      <div class="flow-step">
        <div class="flow-step-num">Datum</div>
        <div class="flow-step-title">Canonical Intermediate</div>
        <div class="flow-step-desc">34" @ 93.5mm median (0.00 dB baseline)</div>
      </div>
      <div class="flow-arrow">&rarr;</div>
      <div class="flow-step flow-active">
        <div class="flow-step-num">Block 2</div>
        <div class="flow-step-title">Universal Target NAM</div>
        <div class="flow-step-desc">A2-Lite Preamp (Clean / Dynamic / Hot Rod)</div>
      </div>
      <div class="flow-arrow">&rarr;</div>
      <div class="flow-step">
        <div class="flow-step-num">Output</div>
        <div class="flow-step-title">Target Acoustic Voice</div>
        <div class="flow-step-desc">Exact tone: Block 1 &times; Block 2 = Acoustic Twin</div>
      </div>
    </div>

    <div class="primary-nav-bar" role="tablist">
      <button class="primary-nav-btn active" id="pnav-targets" onclick="selectPrimaryView('targets')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>
        <span>Universal Targets (Block 2)</span>
      </button>
      <button class="primary-nav-btn" id="pnav-frontends" onclick="selectPrimaryView('frontends')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
        <span>Frontend Deconvolutions (Block 1)</span>
      </button>
      <button class="primary-nav-btn" id="pnav-inspector" onclick="selectPrimaryView('inspector')">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg>
        <span>Signal Flow Inspector (End-to-End)</span>
      </button>
    </div>

    <div class="inspector-subcontrols" id="inspector-subcontrols" style="display: none;">
      <div class="tabs-container" id="tabs">
      {tabs_markup}
      </div>
    </div>

    <div class="meta-panel">
      <div class="meta-item">
        <div class="label" id="meta-label-primary">Active Stage</div>
        <div class="value" id="meta-name">Universal Targets (Block 2)</div>
      </div>
      <div class="meta-item">
        <div class="label" id="meta-label-secondary">Reference / Datum</div>
        <div class="value" id="meta-scale">Canonical Intermediate: 34" @ 93.5mm median</div>
      </div>
      <div class="meta-item">
        <div class="label" id="meta-label-tertiary">Pickup & Circuit</div>
        <div class="value" id="meta-pickups">All 22 Universal Targets across 3 Dynamic Feel Tiers</div>
      </div>
      <div class="meta-item">
        <div class="label">Response View Mode</div>
        <div class="value" id="meta-view-mode">Universal Targets (Block 2)</div>
      </div>
      <div>
        <a id="standalone-link" class="open-standalone-btn" href="{base_url_prefix}universal_targets.html" target="_blank">
          Open Standalone Chart ↗
        </a>
      </div>
    </div>

    <div class="chart-card">
      <iframe id="chart-frame" src="{base_url_prefix}universal_targets.html" title="Interactive Vega Frequency Response Chart"></iframe>
    </div>
  </div>

  <script>
    const instruments = {meta_json};
    const baseUrlPrefix = "{base_url_prefix}";
    let currentPrimaryView = "targets"; // 'targets', 'frontends', 'inspector'
    let currentId = "{default_id}";

    function updateView() {{
      const pnavTargets = document.getElementById('pnav-targets');
      const pnavFrontends = document.getElementById('pnav-frontends');
      const pnavInspector = document.getElementById('pnav-inspector');
      const subcontrols = document.getElementById('inspector-subcontrols');
      const frame = document.getElementById('chart-frame');
      const standaloneLink = document.getElementById('standalone-link');
      const metaName = document.getElementById('meta-name');
      const metaScale = document.getElementById('meta-scale');
      const metaPickups = document.getElementById('meta-pickups');
      const metaViewMode = document.getElementById('meta-view-mode');

      pnavTargets.classList.toggle('active', currentPrimaryView === 'targets');
      pnavFrontends.classList.toggle('active', currentPrimaryView === 'frontends');
      pnavInspector.classList.toggle('active', currentPrimaryView === 'inspector');

      if (currentPrimaryView === 'targets') {{
        subcontrols.style.display = 'none';
        const url = `${{baseUrlPrefix}}universal_targets.html`;
        frame.src = url;
        standaloneLink.href = url;
        metaName.textContent = 'Universal Target Voicings (Block 2)';
        metaScale.textContent = 'Canonical Intermediate: 34" @ 93.5mm median';
        metaPickups.textContent = '22 Target Profiles across 3 Dynamic Feel Tiers (Clean, Dynamic, Hot Rod)';
        metaViewMode.textContent = 'Universal Target Profiles';
        if (window.history.replaceState) window.history.replaceState(null, null, '#targets');
        return;
      }}

      if (currentPrimaryView === 'frontends') {{
        subcontrols.style.display = 'none';
        const url = `${{baseUrlPrefix}}frontend_deconvolutions.html`;
        frame.src = url;
        standaloneLink.href = url;
        metaName.textContent = 'Frontend Deconvolutions (Block 1)';
        metaScale.textContent = '32 Physical Switch Positions across 11 Source Basses';
        metaPickups.textContent = '2048-tap causal minimum-phase FIRs with strictly positive initial polarity';
        metaViewMode.textContent = 'Frontend Deconvolution IRs';
        if (window.history.replaceState) window.history.replaceState(null, null, '#frontends');
        return;
      }}

      // Inspector Mode
      subcontrols.style.display = 'block';
      const inst = instruments[currentId] || Object.values(instruments)[0];

      document.querySelectorAll('.tab-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.dataset.id === currentId);
      }});

      const chartUrl = `${{baseUrlPrefix}}${{currentId}}.html`;
      frame.src = chartUrl;
      standaloneLink.href = chartUrl;
      metaName.textContent = inst.name;
      metaScale.textContent = `${{inst.scale_in}}" scale (${{inst.scale_m}} m) | ${{inst.speeds_str}}`;
      metaPickups.textContent = inst.pickups_summary;
      metaViewMode.textContent = 'End-to-End Signal Flow';

      if (window.history.replaceState) {{
        window.history.replaceState(null, null, `#${{currentId}}`);
      }}
      setTimeout(resizeIframe, 150);
      setTimeout(resizeIframe, 450);
    }}

    function resizeIframe() {{
      const frame = document.getElementById('chart-frame');
      if (!frame) return;
      try {{
        const doc = frame.contentDocument || frame.contentWindow.document;
        if (doc && doc.body) {{
          const h = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight);
          if (h > 250) {{
            frame.style.height = (h + 16) + 'px';
          }}
        }}
      }} catch (err) {{}}
    }}

    function selectPrimaryView(view) {{
      currentPrimaryView = view;
      updateView();
    }}

    function selectInstrument(id) {{
      if (!instruments[id]) return;
      currentId = id;
      currentPrimaryView = 'inspector';
      updateView();
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      const frame = document.getElementById('chart-frame');
      if (frame) {{
        frame.addEventListener('load', () => {{
          resizeIframe();
          setTimeout(resizeIframe, 150);
          setTimeout(resizeIframe, 450);
        }});
      }}
      window.addEventListener('resize', resizeIframe);

      const hash = window.location.hash.replace('#', '');
      if (hash === 'targets') {{
        currentPrimaryView = 'targets';
      }} else if (hash === 'frontends') {{
        currentPrimaryView = 'frontends';
      }} else if (hash) {{
        const hashId = hash.split(':')[0];
        if (instruments[hashId]) {{
          currentId = hashId;
          currentPrimaryView = 'inspector';
        }}
      }}
      updateView();
    }});
  </script>
</body>
</html>
"""
    return html

def generate_portal_pages(output_dir=None, default_id=None):
    """
    Builds the interactive index portal:
    1. docs/frequency_responses/index.html (relative links './{id}.html')
    2. docs/frequency_responses.html (relative links './frequency_responses/{id}.html')
    """
    out_dir = Path(output_dir) if output_dir else RESPONSES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    all_insts = load_all_instruments()

    active_meta = {}
    for inst_id, inst_cfg in all_insts.items():
        if inst_id == "canonical_intermediate":
            continue
        chart_file = out_dir / f"{inst_id}.html"
        if chart_file.exists() or not any(out_dir.glob("*.html")):
            active_meta[inst_id] = format_instrument_meta(inst_cfg)

    if not active_meta:
        for inst_id, inst_cfg in all_insts.items():
            if inst_id == "canonical_intermediate":
                continue
            active_meta[inst_id] = format_instrument_meta(inst_cfg)

    def_id = default_id if (default_id and default_id in active_meta) else next(iter(active_meta))

    # 1. Write docs/frequency_responses/index.html
    index_html = build_portal_html(active_meta, default_id=def_id, base_url_prefix="./")
    index_path = out_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    print(f"Saved interactive portal: {index_path}")

    # 2. Write docs/frequency_responses.html at root of docs/ (only if target directory is default RESPONSES_DIR)
    if out_dir.resolve() == RESPONSES_DIR.resolve():
        root_portal_html = build_portal_html(active_meta, default_id=def_id, base_url_prefix="./frequency_responses/")
        root_portal_path = DOCS_DIR / "frequency_responses.html"
        root_portal_path.write_text(root_portal_html, encoding="utf-8")
        print(f"Saved master portal: {root_portal_path}")

def render_chart_to_file(
    master_df: pl.DataFrame,
    target_path: Path,
    chart_title: str,
    chart_subtitle: str,
    y_title: str,
    y_domain: list,
    mode: str = "unified",
):
    """Renders a Polars master dataframe into an interactive Altair chart HTML file."""
    voice_selection = alt.selection_point(fields=["voice_name"], bind="legend")
    if mode == "output":
        params = [voice_selection]
        filters = []
    elif mode == "difference":
        params = [voice_selection]
        filters = []
    else:  # unified
        mode_selection = alt.selection_point(
            fields=["mode"],
            bind=alt.binding_radio(
                options=["Input/Output Difference", "Output Voice"],
                name="Display Mode: "
            ),
            value="Input/Output Difference",
        )
        params = [mode_selection, voice_selection]
        filters = [mode_selection]

    chart = (
        alt.Chart(master_df)
        .mark_line(strokeWidth=2.2)
        .encode(
            x=alt.X(
                "frequency:Q",
                scale=alt.Scale(type="log", domain=[20, 20000]),
                title="Frequency (Hz)",
                axis=alt.Axis(
                    values=[20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
                    grid=True,
                    gridDash=[3, 3],
                    gridColor="#333333"
                )
            ),
            y=alt.Y(
                "magnitude_db:Q",
                scale=alt.Scale(domain=y_domain),
                title=y_title,
                axis=alt.Axis(grid=True, gridDash=[3, 3], gridColor="#333333")
            ),
            color=alt.Color(
                "voice_name:N",
                title="Allomorph Pickup Profile (Click to isolate)",
                scale=alt.Scale(scheme="tableau20")
            ),
            opacity=alt.condition(voice_selection, alt.value(1.0), alt.value(0.12)),
            strokeWidth=alt.condition(voice_selection, alt.value(2.8), alt.value(1.0)),
            tooltip=[
                alt.Tooltip("voice_name:N", title="Pickup Configuration"),
                alt.Tooltip("topology:N", title="Topology"),
                alt.Tooltip("description:N", title="Circuit / Acoustic Description"),
                alt.Tooltip("frequency:Q", title="Frequency (Hz)", format=".1f"),
                alt.Tooltip("magnitude_db:Q", title="Magnitude (dB)", format="+.1f")
            ]
        )
    )

    for f in filters:
        chart = chart.transform_filter(f)
    for p in params:
        chart = chart.add_params(p)

    chart = chart.properties(
        title=alt.TitleParams(
            text=chart_title,
            subtitle=chart_subtitle,
            fontSize=16,
            subtitleFontSize=12,
            anchor="start"
        ),
        width=740,
        height=480
    ).configure_view(strokeWidth=0).configure_legend(orient="right", labelLimit=320).interactive()

    chart.save(str(target_path))
    print(f"Saved interactive Altair visualization: {target_path}")
    return target_path

def generate_interactive_chart(instrument="30in", out_html=None, mode="composite"):
    """
    Calculates voice responses and renders an interactive Altair chart.
    mode:
      - 'composite': 3-curve overlay (Frontend IR + Backend Voicing = Composite Result).
      - 'unified': embeds both Output Voice and Input/Output Difference curves with interactive radio buttons.
      - 'output': standalone chart strictly plotting the 12 target Output Voice curves.
      - 'difference': standalone chart strictly plotting the Input/Output Difference curves for this instrument.
      - 'targets': standalone chart strictly plotting the Universal Target curves.
      - 'frontends': standalone chart strictly plotting the Frontend Deconvolution curves.
    """
    if mode == "targets":
        return generate_universal_targets_chart(target_path=out_html)
    elif mode == "frontends":
        return generate_frontend_deconvolutions_chart(target_path=out_html)

    inst = load_instrument(instrument) if not isinstance(instrument, dict) else instrument
    inst_id = inst.get("id", "custom_instrument")
    inst_name = inst.get("name", inst_id)

    if out_html is None:
        target_path = RESPONSES_DIR / f"{inst_id}.html"
    else:
        p = Path(out_html)
        if p.is_dir() or (not p.suffix and not p.exists()):
            target_path = p / f"{inst_id}.html"
        else:
            target_path = p

    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "composite":
        return generate_composite_instrument_chart(inst, out_html=target_path)

    print(f"Computing voice frequency responses (mode={mode}, instrument={inst_name})...")
    if mode == "output":
        dfs = [build_voice_dataframe(vid, cfg, instrument=inst, mode="output") for vid, cfg in VOICES.items()]
        master_df = pl.concat(dfs)
        chart_title = "Allomorph Master Voices: Output Voice Frequency Responses"
        chart_subtitle = f"Target Passive Acoustic Apertures & SPICE Loaded RLC Resonances (Reference: {inst_name})"
        y_title = "Normalized Output Magnitude (dB)"
        y_domain = [-30, 10]
    elif mode == "difference":
        dfs = [build_voice_dataframe(vid, cfg, instrument=inst, mode="difference") for vid, cfg in VOICES.items()]
        master_df = pl.concat(dfs)
        chart_title = "Allomorph Master Voices: Input/Output Differential Transfer Functions"
        chart_subtitle = f"Source: {inst_name} -> Target: 34\" Standard & 37\" Multi-Scale Datums (Δ Transfer Filter)"
        y_title = "Differential Transfer Magnitude (dB)"
        y_domain = [-28, 15]
    else:  # mode == "unified"
        dfs_out = [build_voice_dataframe(vid, cfg, instrument=inst, mode="output", include_mode_col=True) for vid, cfg in VOICES.items()]
        dfs_diff = [build_voice_dataframe(vid, cfg, instrument=inst, mode="difference", include_mode_col=True) for vid, cfg in VOICES.items()]
        master_df = pl.concat(dfs_diff + dfs_out)
        chart_title = "Allomorph Master Voices: Acoustic & Electrical Response Curves"
        chart_subtitle = f"Interactive View ({inst_name}) — Switch between Input/Output Difference and Output Voice"
        y_title = "Normalized Magnitude / Differential Gain (dB)"
        y_domain = [-30, 15]

    print("Rendering interactive chart using Altair...")
    return render_chart_to_file(master_df, target_path, chart_title, chart_subtitle, y_title, y_domain, mode=mode)

def generate_all_charts(output_dir=None):
    """Generates standalone Altair interactive charts for all configured instruments and Architecture C master views."""
    out_dir = Path(output_dir) if output_dir else RESPONSES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    all_insts = load_all_instruments()

    # 1. Mode 1: Universal Target Voicings (Block 2)
    print("Generating Universal Target Voicings (Block 2)...")
    generate_universal_targets_chart(out_dir / "universal_targets.html")

    # 2. Mode 2: Frontend Deconvolutions (Block 1)
    print("Generating Frontend Deconvolutions (Block 1)...")
    generate_frontend_deconvolutions_chart(out_dir / "frontend_deconvolutions.html")

    generated = {}
    for inst_id, inst_cfg in all_insts.items():
        if inst_id == "canonical_intermediate":
            continue
        inst_name = inst_cfg.get("name", inst_id)

        # Signal Flow Inspector (End-to-End: Bass Input -> Deconv -> Canonical (0 dB) -> Voicing -> Target Output)
        print(f"Generating Signal Flow Inspector for {inst_name}...")
        out_composite_file = out_dir / f"{inst_id}.html"
        generate_composite_instrument_chart(inst_cfg, out_html=out_composite_file)
        generated[inst_id] = out_composite_file

    generate_portal_pages(output_dir=out_dir)
    return generated

def main():
    parser = argparse.ArgumentParser(description="Generate interactive Altair visualization of Allomorph voices.")
    parser.add_argument(
        "--instrument", "-i",
        default="all",
        help="Source instrument configuration (ID, alias like 30in, 32in, path to .toml, or 'all' to generate all)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["composite", "unified", "output", "difference", "targets", "frontends"],
        default="composite",
        help="Chart mode: 'composite' (3-curve overlay), 'unified', 'output', 'difference', 'targets', or 'frontends'"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build interactive charts for all configured instruments"
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output HTML file or directory path (default: docs/frequency_responses/<instrument_id>.html)"
    )
    args = parser.parse_args()

    if args.all or (isinstance(args.instrument, str) and args.instrument.lower() == "all"):
        generate_all_charts(output_dir=args.out)
    else:
        inst = load_instrument(args.instrument)
        target_file = generate_interactive_chart(instrument=inst, out_html=args.out, mode=args.mode)
        if args.out is None or (Path(args.out).resolve() == RESPONSES_DIR.resolve()):
            generate_portal_pages(output_dir=RESPONSES_DIR, default_id=inst.get("id"))

if __name__ == "__main__":
    main()


