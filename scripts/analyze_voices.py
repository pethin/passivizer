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
import polars as pl
import altair as alt

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import VOICES, SCALES, polars_aperture, polars_position

NUM_POINTS = 600
F_MIN = 20.0
F_MAX = 20000.0

log_freqs = [F_MIN * (F_MAX / F_MIN) ** (i / (NUM_POINTS - 1)) for i in range(NUM_POINTS)]

def build_voice_dataframe(voice_id, cfg, src_scale="30in"):
    """Calculates magnitude frequency response in dB for a voice using Polars."""
    src = SCALES[src_scale]
    tgt_scale = cfg.get("scale", "34in")
    tgt = SCALES[tgt_scale]

    df = pl.DataFrame({"frequency": log_freqs})
    f_col = pl.col("frequency")

    # Determine physical source pickup geometry
    if src_scale == "32in" and "src_32" in cfg:
        src_w = cfg["src_32"]["w"]
        src_d = cfg["src_32"]["d"]
        src_pos_m = cfg["src_32"]["pos"]
    else:
        src_w = src.get("w_in", 1.50)
        src_d = src.get("d_in", 0.75)
        src_pos_m = src.get("pickup_from_bridge_m", 0.0775)

    # 1. Aperture Transfer via Polars
    h_src_ap = polars_aperture(f_col, src_w, src_d, src["speeds"])
    h_tgt_ap = polars_aperture(f_col, cfg["w"], cfg["d"], tgt["speeds"])
    h_ap_transfer = (h_tgt_ap * h_src_ap) / (h_src_ap.pow(2) + 0.001)

    # 2. Position Transfer via Polars
    h_src_pos = polars_position(f_col, src_pos_m, src["speeds"])
    h_tgt_pos = polars_position(f_col, cfg["pos_34"], tgt["speeds"])
    h_pos_transfer = (h_tgt_pos * h_src_pos) / (h_src_pos.pow(2) + 0.002)

    # 3. Macro Position Displacement Tilt (1.5 dB/inch)
    delta_in = (cfg["pos_34"] - src_pos_m) / 0.0254
    tilt_db = delta_in * 1.5
    g_low = 10.0 ** (tilt_db / 20.0)
    g_hi = 10.0 ** (-tilt_db / 20.0)
    h_low_tilt = ((g_low ** 2 + (f_col / 250.0).pow(2)) / (1.0 + (f_col / 250.0).pow(2))).sqrt()
    h_hi_tilt = ((1.0 + g_hi ** 2 * (f_col / 2200.0).pow(2)) / (1.0 + (f_col / 2200.0).pow(2))).sqrt()

    # 4. Scale Tension Filter
    if tgt_scale == "multiscale":
        sub_gain = 10.0 ** (1.5 / 20.0)
        h_sub = ((sub_gain ** 2 + (f_col / 75.0).pow(2)) / (1.0 + (f_col / 75.0).pow(2))).sqrt()
        a_clank = 10.0 ** (3.5 / 40.0)
        x_clank = f_col / 3200.0
        h_clank = (((1.0 - x_clank.pow(2)).pow(2) + (a_clank * x_clank / 1.5).pow(2)) /
                   ((1.0 - x_clank.pow(2)).pow(2) + (x_clank / (a_clank * 1.5)).pow(2))).sqrt()
        h_tension = h_sub * h_clank
    elif tgt_scale == "34in" and src_scale != "34in":
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = ((1.0 + g_snap ** 2 * (f_col / 2800.0).pow(2)) / (1.0 + (f_col / 2800.0).pow(2))).sqrt()
    else:
        h_tension = pl.lit(1.0)

    # 5. Electrical RLC Resonance
    fr, Q = cfg["fr"], cfg["Q"]
    h_elec = 1.0 / (((1.0 - (f_col / fr).pow(2)).pow(2) + (1.0 / Q ** 2) * (f_col / fr).pow(2))).sqrt()

    if "hpf" in cfg:
        fc_hpf = cfg["hpf"]
        h_elec = h_elec * (f_col / (f_col.pow(2) + fc_hpf ** 2).sqrt())

    df = df.with_columns(
        (h_ap_transfer * h_pos_transfer * (h_low_tilt * h_hi_tilt) * h_tension * h_elec).alias("mag_raw")
    )

    max_val = df["mag_raw"].max()
    df = df.with_columns(
        (df["mag_raw"] / max_val).alias("mag_norm")
    ).with_columns(
        (20.0 * (pl.col("mag_norm").clip(1e-5, 1.0)).log10() + cfg["gain_db"]).alias("magnitude_db"),
        pl.lit(voice_id).alias("voice_id"),
        pl.lit(cfg.get("name", voice_id)).alias("voice_name"),
        pl.lit(cfg.get("topology", "Passive Pickup")).alias("topology"),
        pl.lit(cfg.get("description", "")).alias("description")
    ).select(["frequency", "magnitude_db", "voice_id", "voice_name", "topology", "description"])

    return df

def generate_interactive_chart(source_scale="30in", out_html="docs/frequency_responses.html"):
    print(f"Computing voice frequency responses using Polars (Source: {source_scale})...")
    dfs = [build_voice_dataframe(vid, cfg, src_scale=source_scale) for vid, cfg in VOICES.items()]
    master_df = pl.concat(dfs)

    print("Rendering interactive chart using Altair...")
    selection = alt.selection_point(fields=["voice_name"], bind="legend")

    scale_title = "30\" EMG MM (77.5 mm bridge)" if source_scale == "30in" else "32\" P/MM (Reverse PX + MMTWX)"
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
                subtitle=f"Source: {scale_title} -> Target: 34\" Standard & 37\" Multi-Scale Datums",
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
    parser.add_argument("--source-scale", choices=["30in", "32in"], default="30in", help="Physical source scale")
    parser.add_argument("--out", default="docs/frequency_responses.html", help="Output HTML file path")
    args = parser.parse_args()

    generate_interactive_chart(source_scale=args.source_scale, out_html=args.out)

if __name__ == "__main__":
    main()

