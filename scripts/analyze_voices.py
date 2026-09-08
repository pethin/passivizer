"""
Passivizer - Interactive Visualizer & Frequency Analyzer
Uses Polars and Altair to model, analyze, and render interactive frequency
response curves for all 10 Master Voices (30" / 32" EMG -> 34" / 37" Multi-Scale).
"""

import argparse
import math
import os
import sys
from pathlib import Path
import numpy as np
import polars as pl
import altair as alt

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import (
    VOICES,
    SCALES,
    load_instrument,
    get_source_pickup,
    resolve_pickup_coils,
    resolve_voice_coils,
    resolve_voice_pickups,
    compute_effective_position,
    numpy_pickup_acoustic_response,
)

NUM_POINTS = 600
F_MIN = 20.0
F_MAX = 20000.0

log_freqs = [F_MIN * (F_MAX / F_MIN) ** (i / (NUM_POINTS - 1)) for i in range(NUM_POINTS)]

def build_voice_dataframe(voice_id, cfg, instrument="30in", src_scale=None):
    """Calculates magnitude frequency response in dB for a voice using NumPy vector math and Polars."""
    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    tgt_scale = cfg.get("scale", "34in")
    tgt = SCALES[tgt_scale]
    tgt_speeds = tgt["speeds"]

    src_speeds = inst.get("string_wave_speeds")
    if not src_speeds:
        l_m = inst.get("scale_length_m", inst.get("scale_length_in", 34.0) * 0.0254)
        src_speeds = [2.0 * l_m * f0 for f0 in [41.203, 55.0, 73.416, 97.999]]

    src_pickup = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_pickup, inst)
    tgt_coils = resolve_voice_coils(cfg)

    src_pos_eff = compute_effective_position(src_coils)
    tgt_pos_eff = compute_effective_position(tgt_coils)

    freqs = np.asarray(log_freqs, dtype=np.float64)

    # 1. Source Pickup Acoustic Response
    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, src_speeds)

    # 2. Target Composite Acoustic + Electrical Pickup Superposition
    pickups = resolve_voice_pickups(cfg)
    fc_hpf = cfg.get("hpf")
    h_tgt_total = np.zeros_like(freqs)

    for p in pickups:
        p_coils = p["coils"]
        p_weight = p.get("weight", 1.0)
        p_pol = p.get("polarity", 1.0)
        fr_p = p["fr"]
        Q_p = p["Q"]

        # Pickup-specific acoustic sensing across all strings
        h_ac = numpy_pickup_acoustic_response(freqs, p_coils, tgt_speeds)

        # Pickup-specific electrical RLC resonance
        h_el = 1.0 / np.sqrt((1.0 - (freqs / fr_p) ** 2) ** 2 + (1.0 / Q_p ** 2) * (freqs / fr_p) ** 2)

        p_resp = h_ac * h_el * (p_weight * p_pol)
        h_tgt_total += p_resp

    # Apply optional high-pass filter (e.g. Rickenbacker 4.7nF)
    if fc_hpf:
        h_tgt_total = h_tgt_total * (freqs / np.sqrt(freqs ** 2 + fc_hpf ** 2))

    # 3. Acoustic/Electrical Transfer from Source to Target
    h_transfer = (h_tgt_total * h_src_acoustic) / (h_src_acoustic ** 2 + 0.001)

    # 4. Macro Position Displacement Tilt (1.5 dB/inch)
    delta_in = (tgt_pos_eff - src_pos_eff) / 0.0254
    tilt_db = delta_in * 1.5
    g_low = 10.0 ** (tilt_db / 20.0)
    g_hi = 10.0 ** (-tilt_db / 20.0)
    h_low_tilt = np.sqrt((g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2))
    h_hi_tilt = np.sqrt((1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2))

    # 5. Scale Tension Filter
    src_scale_in = inst.get("scale_length_in", 34.0)
    if tgt_scale == "multiscale":
        sub_gain = 10.0 ** (1.5 / 20.0)
        h_sub = np.sqrt((sub_gain ** 2 + (freqs / 75.0) ** 2) / (1.0 + (freqs / 75.0) ** 2))
        a_clank = 10.0 ** (3.5 / 40.0)
        x_clank = freqs / 3200.0
        h_clank = np.sqrt(
            ((1.0 - x_clank ** 2) ** 2 + (a_clank * x_clank / 1.5) ** 2) /
            ((1.0 - x_clank ** 2) ** 2 + (x_clank / (a_clank * 1.5)) ** 2)
        )
        h_tension = h_sub * h_clank
    elif tgt_scale == "34in" and src_scale_in != 34.0:
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = np.sqrt((1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2))
    else:
        h_tension = np.ones_like(freqs)

    mag_raw = h_transfer * (h_low_tilt * h_hi_tilt) * h_tension
    max_val = np.max(mag_raw)
    mag_norm = mag_raw / max_val if max_val > 0 else mag_raw
    mag_db = 20.0 * np.log10(np.clip(mag_norm, 1e-5, 1.0)) + cfg["gain_db"]

    return pl.DataFrame({
        "frequency": log_freqs,
        "magnitude_db": mag_db.tolist(),
        "voice_id": voice_id,
        "voice_name": cfg.get("name", voice_id),
        "topology": cfg.get("topology", "Passive Pickup"),
        "description": cfg.get("description", ""),
    })

def generate_interactive_chart(instrument="30in", out_html="docs/frequency_responses.html", source_scale=None):
    inst_selector = source_scale if source_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector
    inst_name = inst.get("name", inst.get("id", "Custom Bass"))

    print(f"Computing voice frequency responses using Polars (Source Instrument: {inst_name})...")
    dfs = [build_voice_dataframe(vid, cfg, instrument=inst) for vid, cfg in VOICES.items()]
    master_df = pl.concat(dfs)

    print("Rendering interactive chart using Altair...")
    selection = alt.selection_point(fields=["voice_name"], bind="legend")

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
                scale=alt.Scale(domain=[-28, 10]),
                title="Normalized Magnitude (dB)",
                axis=alt.Axis(grid=True, gridDash=[3, 3], gridColor="#333333")
            ),
            color=alt.Color(
                "voice_name:N",
                title="Passivizer Pickup Profile (Click to isolate)",
                scale=alt.Scale(scheme="tableau20")
            ),
            opacity=alt.condition(selection, alt.value(1.0), alt.value(0.12)),
            strokeWidth=alt.condition(selection, alt.value(2.8), alt.value(1.0)),
            tooltip=[
                alt.Tooltip("voice_name:N", title="Pickup Configuration"),
                alt.Tooltip("topology:N", title="Topology"),
                alt.Tooltip("description:N", title="Circuit / Acoustic Description"),
                alt.Tooltip("frequency:Q", title="Frequency (Hz)", format=".1f"),
                alt.Tooltip("magnitude_db:Q", title="Magnitude (dB)", format="+.1f")
            ]
        )
        .add_params(selection)
        .properties(
            title=alt.TitleParams(
                text="Passivizer Master Voices: Acoustic & Electrical Response Curves",
                subtitle=f"Source: {inst_name} -> Target: 34\" Standard & 37\" Multi-Scale Datums",
                fontSize=16,
                subtitleFontSize=12,
                anchor="start"
            ),
            width=920,
            height=520
        )
        .configure_view(strokeWidth=0)
        .interactive()
    )

    os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
    chart.save(out_html)
    print(f"Saved interactive Altair visualization: {out_html}")

def main():
    parser = argparse.ArgumentParser(description="Generate interactive Altair visualization of Passivizer voices.")
    parser.add_argument(
        "--instrument", "-i",
        default="30in",
        help="Source instrument configuration (ID, path to .toml, or alias like 30in, 32in)"
    )
    parser.add_argument(
        "--source-scale",
        dest="instrument",
        help="Legacy alias for --instrument (e.g. 30in, 32in)"
    )
    parser.add_argument("--out", default="docs/frequency_responses.html", help="Output HTML file path")
    args = parser.parse_args()

    generate_interactive_chart(instrument=args.instrument, out_html=args.out)

if __name__ == "__main__":
    main()


