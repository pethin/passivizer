"""
Passivizer - Interactive Visualizer & Frequency Analyzer
Uses Polars and Altair to model, analyze, and render interactive frequency
response curves for all 10 Master Voices (30" EMG MM -> 34" / 37" Multi-Scale).
"""

import math
import os
import polars as pl
import altair as alt

# --- CONFIGURATION ---
NUM_POINTS = 600
F_MIN = 20.0
F_MAX = 20000.0

# Generate logarithmically spaced frequency points using standard library & Polars
log_freqs = [F_MIN * (F_MAX / F_MIN) ** (i / (NUM_POINTS - 1)) for i in range(NUM_POINTS)]

# 30" Source Wave Speeds
SPEEDS_30IN = [62.79, 83.82, 111.89, 149.35]
SRC_POS_M = 0.0775  # 77.5 mm from bridge
SRC_W_IN = 1.50     # Dual-coil MM aperture
SRC_D_IN = 0.75     # Dual-coil spacing

# Master 10 Profiles
PROFILES = [
    {
        "id": "01_j_jazz_atelier_pair", "name": "01. J-Jazz Atelier Z Pair",
        "genre": "J-Jazz / Anisong Slap", "pos": 0.0880, "w": 0.75, "d": 0.0,
        "fr": 3900.0, "Q": 1.3, "gain_db": -0.5, "scale": "34in"
    },
    {
        "id": "02_jaco_fusion_bridge", "name": "02. Jaco Fusion Bridge Solo",
        "genre": "J-Fusion / Soloing Bark", "pos": 0.0406, "w": 0.75, "d": 0.0,
        "fr": 3200.0, "Q": 1.6, "gain_db": -2.5, "scale": "34in"
    },
    {
        "id": "03_jrock_modern_p", "name": "03. J-Rock Modern P (8CBP)",
        "genre": "J-Rock / Anisong Pick", "pos": 0.1250, "w": 1.00, "d": 0.0,
        "fr": 2200.0, "Q": 1.8, "gain_db": +1.5, "scale": "34in"
    },
    {
        "id": "04_vintage_62_alnico_p", "name": "04. Vintage '62 Alnico P",
        "genre": "Classic Rock / Pop / Blues", "pos": 0.1250, "w": 1.00, "d": 0.0,
        "fr": 2800.0, "Q": 1.4, "gain_db": +0.5, "scale": "34in"
    },
    {
        "id": "05_motown_neo_soul_dub", "name": "05. Motown / Neo-Soul Dub",
        "genre": "Neo-Soul / Reggae / Dub", "pos": 0.1250, "w": 1.00, "d": 0.0,
        "fr": 450.0, "Q": 0.9, "gain_db": -1.0, "scale": "34in"
    },
    {
        "id": "06_studio_workhorse_pj", "name": "06. Studio Workhorse P/J",
        "genre": "Everyday Rock / Studio Pop", "pos": 0.0880, "w": 0.88, "d": 0.0,
        "fr": 3600.0, "Q": 1.4, "gain_db": +0.8, "scale": "34in"
    },
    {
        "id": "07_jmetal_prog_stingray", "name": "07. J-Metal Prog StingRay",
        "genre": "J-Metal / Prog / Djent", "pos": 0.0660, "w": 1.50, "d": 0.75,
        "fr": 3500.0, "Q": 1.5, "gain_db": 0.0, "scale": "34in"
    },
    {
        "id": "08_prog_rick_clank", "name": "08. Prog Rickenbacker Clank",
        "genre": "Prog Rock Pick Grind", "pos": 0.0406, "w": 1.10, "d": 0.0,
        "fr": 2200.0, "Q": 2.2, "gain_db": -1.5, "scale": "34in", "hpf": 150.0
    },
    {
        "id": "09_power_trio_bulldozer", "name": "09. Power-Trio Bulldozer",
        "genre": "Hard Rock / Metal Solos", "pos": 0.0950, "w": 1.25, "d": 0.75,
        "fr": 2000.0, "Q": 2.2, "gain_db": +5.8, "scale": "34in"
    },
    {
        "id": "10_stoner_doom_mudbucker", "name": "10. Stoner Doom Mudbucker",
        "genre": "Stoner / Doom / Sludge", "pos": 0.0950, "w": 1.50, "d": 0.75,
        "fr": 1200.0, "Q": 1.6, "gain_db": +6.2, "scale": "34in"
    },
    {
        "id": "07_dingwall_ng_multiscale", "name": "11. Dingwall NG Multi-Scale",
        "genre": "34\"-37\" Modern Metal Clank", "pos": 0.0480, "w": 1.25, "d": 0.75,
        "fr": 3400.0, "Q": 1.7, "gain_db": +1.0, "scale": "multiscale"
    }
]

# --- POLARS COMPUTATION HELPERS ---
def polars_calc_aperture(freq_expr, w_in, d_in, speeds):
    """Computes multi-string aperture sinc + dual-coil comb using Polars expressions."""
    w_m = w_in * 0.0254
    d_m = d_in * 0.0254
    acc = pl.lit(0.0)
    
    for v in speeds:
        # sinc(f * w / v) = sin(pi * f * w / v) / (pi * f * w / v)
        arg_w = freq_expr * (math.pi * w_m / v)
        sinc_val = (
            pl.when(freq_expr == 0)
            .then(1.0)
            .otherwise(arg_w.sin() / arg_w)
        ).abs() + 0.05
        
        if d_in > 0:
            arg_d = freq_expr * (math.pi * d_m / v)
            comb_val = arg_d.cos().abs() + 0.05
        else:
            comb_val = pl.lit(1.0)
            
        acc = acc + (sinc_val * comb_val)
        
    return acc / len(speeds)

def polars_calc_position(freq_expr, pos_m, speeds):
    """Computes spatial standing wave envelope using Polars expressions."""
    acc = pl.lit(0.0)
    for v in speeds:
        arg_pos = freq_expr * (2.0 * math.pi * pos_m / v)
        acc = acc + (arg_pos.sin().abs() + 0.15)
    return acc / len(speeds)

def build_voice_dataframe(profile):
    """Calculates magnitude frequency response in dB for a voice using Polars."""
    df = pl.DataFrame({"frequency": log_freqs})
    f_col = pl.col("frequency")
    
    # 1. Aperture Transfer
    h_src_ap = polars_calc_aperture(f_col, SRC_W_IN, SRC_D_IN, SPEEDS_30IN)
    h_tgt_ap = polars_calc_aperture(f_col, profile["w"], profile["d"], SPEEDS_30IN)
    h_ap_transfer = (h_tgt_ap * h_src_ap) / (h_src_ap.pow(2) + 0.001)
    
    # 2. Position Transfer
    h_src_pos = polars_calc_position(f_col, SRC_POS_M, SPEEDS_30IN)
    h_tgt_pos = polars_calc_position(f_col, profile["pos"], SPEEDS_30IN)
    h_pos_transfer = (h_tgt_pos * h_src_pos) / (h_src_pos.pow(2) + 0.002)
    
    # 3. Macro Position Tilt (1.5 dB/inch)
    delta_in = (profile["pos"] - SRC_POS_M) / 0.0254
    tilt_db = delta_in * 1.5
    g_low = 10.0 ** (tilt_db / 20.0)
    g_hi = 10.0 ** (-tilt_db / 20.0)
    h_low_tilt = ((g_low ** 2 + (f_col / 250.0).pow(2)) / (1.0 + (f_col / 250.0).pow(2))).sqrt()
    h_hi_tilt = ((1.0 + g_hi ** 2 * (f_col / 2200.0).pow(2)) / (1.0 + (f_col / 2200.0).pow(2))).sqrt()
    
    # 4. Scale Tension Filter
    if profile.get("scale") == "multiscale":
        sub_gain = 10.0 ** (1.5 / 20.0)
        h_sub = ((sub_gain ** 2 + (f_col / 75.0).pow(2)) / (1.0 + (f_col / 75.0).pow(2))).sqrt()
        # Clank peak at 3.2 kHz
        a_clank = 10.0 ** (3.5 / 40.0)
        x_clank = f_col / 3200.0
        h_clank = (((1.0 - x_clank.pow(2)).pow(2) + (a_clank * x_clank / 1.5).pow(2)) /
                   ((1.0 - x_clank.pow(2)).pow(2) + (x_clank / (a_clank * 1.5)).pow(2))).sqrt()
        h_tension = h_sub * h_clank
    else:
        # Standard 34in
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = ((1.0 + g_snap ** 2 * (f_col / 2800.0).pow(2)) / (1.0 + (f_col / 2800.0).pow(2))).sqrt()
        
    # 5. Electrical RLC
    fr, Q = profile["fr"], profile["Q"]
    h_elec = 1.0 / (((1.0 - (f_col / fr).pow(2)).pow(2) + (1.0 / Q ** 2) * (f_col / fr).pow(2))).sqrt()
    
    if "hpf" in profile:
        fc_hpf = profile["hpf"]
        h_elec = h_elec * (f_col / (f_col.pow(2) + fc_hpf ** 2).sqrt())
        
    df = df.with_columns(
        (h_ap_transfer * h_pos_transfer * (h_low_tilt * h_hi_tilt) * h_tension * h_elec).alias("mag_raw")
    )
    
    max_val = df["mag_raw"].max()
    df = df.with_columns(
        (df["mag_raw"] / max_val).alias("mag_norm")
    ).with_columns(
        (20.0 * (pl.col("mag_norm").clip(1e-5, 1.0)).log10() + profile["gain_db"]).alias("magnitude_db"),
        pl.lit(profile["id"]).alias("voice_id"),
        pl.lit(profile["name"]).alias("voice_name"),
        pl.lit(profile["genre"]).alias("genre_role")
    ).select(["frequency", "magnitude_db", "voice_id", "voice_name", "genre_role"])
    
    return df

def generate_interactive_chart():
    print("Computing voice frequency responses using Polars...")
    dfs = [build_voice_dataframe(p) for p in PROFILES]
    master_df = pl.concat(dfs)
    
    print("Rendering interactive chart using Altair...")
    # Interactive legend selection parameter
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
                title="Passivizer Profile (Click to isolate)",
                scale=alt.Scale(scheme="tableau20")
            ),
            opacity=alt.condition(selection, alt.value(1.0), alt.value(0.12)),
            strokeWidth=alt.condition(selection, alt.value(2.8), alt.value(1.0)),
            tooltip=[
                alt.Tooltip("voice_name:N", title="Voice"),
                alt.Tooltip("genre_role:N", title="Genre / Role"),
                alt.Tooltip("frequency:Q", title="Frequency (Hz)", format=".1f"),
                alt.Tooltip("magnitude_db:Q", title="Magnitude (dB)", format="+.1f")
            ]
        )
        .add_params(selection)
        .properties(
            title=alt.TitleParams(
                text="Passivizer 10 Master Voices: Acoustic & Electrical Response Curves",
                subtitle="Source: 30\" EMG MM (77.5 mm from bridge) -> Target: 34\" Standard & 37\" Multi-Scale Datums",
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
    
    out_html = "docs/frequency_responses.html"
    chart.save(out_html)
    print(f"Saved interactive Altair visualization: {out_html}")

if __name__ == "__main__":
    generate_interactive_chart()
