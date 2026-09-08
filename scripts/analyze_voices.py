"""
Passivizer - Interactive Visualizer & Frequency Analyzer
Uses Polars and Altair to model, analyze, and render interactive frequency
response curves for all 10 Master Voices (30" / 32" EMG -> 34" / 37" Multi-Scale).
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
)
from simulate_circuits import (
    CIRCUITS_DIR,
    parse_netlist,
    compute_circuit_transfer_functions,
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

    # 1. Target Composite Acoustic + Electrical Pickup Superposition
    pickups = resolve_voice_pickups(cfg)
    cir_rel = cfg.get("circuit", f"circuits/{voice_id}.cir")
    cir_path = REPO_ROOT / cir_rel
    if not cir_path.exists():
        cir_path = CIRCUITS_DIR / f"{voice_id}.cir"

    sensor_type = cfg.get("sensor_type", "magnetic")
    is_identity = (sensor_type != "bridge_force") and is_voice_matching_source(inst, voice_id, cfg)

    if cir_path.exists():
        model = parse_netlist(cir_path)
        circuit_curves = compute_circuit_transfer_functions(model, freqs)
    else:
        # Fallback to idealized 2nd-order biquad approximation
        fc_hpf = cfg.get("hpf")
        circuit_curves = []
        for p in pickups:
            fr_p = p.get("fr", cfg.get("fr", 3000.0))
            Q_p = p.get("Q", cfg.get("Q", 1.5))
            h_el = 1.0 / np.sqrt((1.0 - (freqs / fr_p) ** 2) ** 2 + (1.0 / Q_p ** 2) * (freqs / fr_p) ** 2)
            if fc_hpf:
                h_el = h_el * (freqs / np.sqrt(freqs ** 2 + fc_hpf ** 2))
            circuit_curves.append(h_el)

    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, src_speeds)

    src_components = src_pickup.get("components", []) if src_pickup.get("type") == "composite" else []
    use_branch_matching = (len(src_components) == len(pickups) and len(pickups) > 1)

    # 2. Branch Accumulation: Acoustic Transfer * Macro Tilt * Circuit Curve * Weight * Polarity
    h_tgt_total = np.zeros_like(freqs)
    for i, (p, c_curve) in enumerate(zip(pickups, circuit_curves)):
        p_coils = p["coils"]
        p_weight = p.get("weight", 1.0)
        p_pol = p.get("polarity", 1.0)
        tgt_pos_eff = compute_effective_position(p_coils)

        if use_branch_matching:
            comp_sub_id = src_components[i]["pickup"]
            comp_sub_p = inst["pickups"][comp_sub_id]
            b_src_coils = resolve_pickup_coils(comp_sub_p, inst)
            b_src_pos_eff = compute_effective_position(b_src_coils)
            b_src_acoustic = numpy_pickup_acoustic_response(freqs, b_src_coils, src_speeds)
        else:
            b_src_coils = src_coils
            b_src_pos_eff = src_pos_eff
            b_src_acoustic = h_src_acoustic

        if sensor_type == "bridge_force":
            # Upright acoustic bridge force transducer physics
            eps = 0.08
            h_decomb = b_src_acoustic / (b_src_acoustic ** 2 + eps)
            mid_mask = (freqs >= 100.0) & (freqs <= 1000.0)
            h_decomb = h_decomb / np.median(h_decomb[mid_mask])

            f_damp = 4200.0
            h_damp = 1.0 / np.sqrt((1.0 - (freqs / f_damp) ** 2) ** 2 + 2.0 * (freqs / f_damp) ** 2)

            # 3. Subsonic rumble cut (32 Hz with -16.5 dB DC shelf floor to prevent cepstral zero)
            h_sub = np.maximum(freqs / np.sqrt(freqs ** 2 + 32.0 ** 2), 0.15)
            h_acoustic_transfer = h_decomb * h_damp * h_sub

            # Leaky velocity-to-force integrator
            h_tilt_raw = np.sqrt((1.0 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 70.0) ** 2))
            h_tilt = h_tilt_raw / np.max(h_tilt_raw)
        elif is_identity:
            h_acoustic_transfer = np.ones_like(freqs)
            h_tilt = np.ones_like(freqs)
        else:
            h_tgt_acoustic = numpy_pickup_acoustic_response(freqs, p_coils, tgt_speeds)
            h_src_macro = numpy_pickup_macro_aperture(freqs, b_src_coils, src_speeds)
            h_ratio = h_tgt_acoustic / np.maximum(h_src_macro, 0.08)
            h_acoustic_transfer = np.clip(h_ratio, 0.25, 2.5)

            delta_in = (tgt_pos_eff - b_src_pos_eff) / 0.0254
            tilt_db = delta_in * 1.5
            g_low = 10.0 ** (tilt_db / 20.0)
            g_hi = 10.0 ** (-tilt_db / 20.0)
            h_low_tilt = np.sqrt((g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2))
            h_hi_tilt = np.sqrt((1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2))
            h_tilt = h_low_tilt * h_hi_tilt

        weight_fac = 1.0 if (cir_path.exists() and len(circuit_curves) > 1) else p_weight
        branch_transfer = h_acoustic_transfer * h_tilt * np.asarray(c_curve, dtype=np.float64) * (weight_fac * p_pol)
        h_tgt_total += branch_transfer

    # 3. Active Pickup Electrical Resonance Deconvolution
    h_elec_inv = np.ones_like(freqs) if is_identity else resolve_pickup_electrical_deconvolution(freqs, src_pickup, inst)

    # 4. Scale-Length Tension Filter
    src_scale_in = inst.get("scale_length_in", 34.0)
    if is_identity:
        h_tension = np.ones_like(freqs)
    elif tgt_scale == "multiscale":
        sub_gain = 10.0 ** (1.5 / 20.0)
        h_sub = np.sqrt((sub_gain ** 2 + (freqs / 75.0) ** 2) / (1.0 + (freqs / 75.0) ** 2))
        a_clank = 10.0 ** (3.5 / 40.0)
        x_clank = freqs / 3200.0
        h_clank = np.sqrt(
            ((1.0 - x_clank ** 2) ** 2 + (a_clank * x_clank / 1.5) ** 2) /
            ((1.0 - x_clank ** 2) ** 2 + (x_clank / (a_clank * 1.5)) ** 2)
        )
        h_tension = h_sub * h_clank
    elif tgt_scale == "upright":
        g_bloom = 10.0 ** (2.0 / 20.0)
        h_bloom = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        h_tension = h_bloom
    elif tgt_scale == "34in" and src_scale_in != 34.0:
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = np.sqrt((1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2))
    else:
        h_tension = np.ones_like(freqs)

    mag_raw = h_tgt_total * h_elec_inv * h_tension
    if cfg.get("hpf") and cfg.get("hpf") >= 80.0:
        ref_idx = np.argmin(np.abs(freqs - 1000.0))
    elif cfg.get("sensor_type") == "bridge_force":
        ref_idx = np.argmin(np.abs(freqs - 100.0))
    else:
        ref_idx = 0

    ref_val = mag_raw[ref_idx]
    mag_norm = mag_raw / ref_val if ref_val > 0 else mag_raw
    mag_db = 20.0 * np.log10(np.clip(mag_norm, 1e-5, 20.0)) + cfg.get("gain_db", 0.0)

    return pl.DataFrame({
        "frequency": log_freqs,
        "magnitude_db": mag_db.tolist(),
        "voice_id": voice_id,
        "voice_name": cfg.get("name", voice_id),
        "topology": cfg.get("topology", "Passive Pickup"),
        "description": cfg.get("description", ""),
    })

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
    """Constructs a responsive, dark-mode portal HTML string with iframe navigation."""
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
  <title>Passivizer | Frequency Response Suite</title>
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
      margin-bottom: 20px;
    }}
    .header h1 {{
      font-size: 24px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 12px;
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
    .tabs-container {{
      margin-bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .tab-btn {{
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .tab-btn:hover {{
      background-color: var(--tag-bg);
      color: var(--text);
      border-color: #8b949e;
    }}
    .tab-btn.active {{
      background-color: var(--btn-active);
      border-color: #388bfd;
      color: #ffffff;
      box-shadow: 0 0 10px rgba(31, 111, 235, 0.4);
    }}
    .meta-panel {{
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 20px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)) auto;
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
      font-size: 14px;
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
      height: 640px;
      border: none;
      display: block;
      background-color: #121212;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Passivizer Frequency Response Suite <span class="badge">Acoustic + SPICE VA</span></h1>
      <div class="subtitle">Virtual analog acoustic aperture deconvolution & passive pickup circuit twins for Darkglass Anagram & Neural Amp Modeler.</div>
    </div>

    <div class="tabs-container" id="tabs">
    {tabs_markup}
    </div>

    <div class="meta-panel">
      <div class="meta-item">
        <div class="label">Source Instrument</div>
        <div class="value" id="meta-name">{default_meta["name"]}</div>
      </div>
      <div class="meta-item">
        <div class="label">Scale Length & Wave Speeds</div>
        <div class="value" id="meta-scale">{default_meta["scale_in"]}" scale ({default_meta["scale_m"]} m) | {default_meta["speeds_str"]}</div>
      </div>
      <div class="meta-item">
        <div class="label">Pickup Complement & Placement</div>
        <div class="value" id="meta-pickups">{default_meta["pickups_summary"]}</div>
      </div>
      <div>
        <a id="standalone-link" class="open-standalone-btn" href="{default_standalone_url}" target="_blank">
          Open Standalone Chart ↗
        </a>
      </div>
    </div>

    <div class="chart-card">
      <iframe id="chart-frame" src="{default_standalone_url}" title="Interactive Vega Frequency Response Chart"></iframe>
    </div>
  </div>

  <script>
    const instruments = {meta_json};
    const baseUrlPrefix = "{base_url_prefix}";
    let currentId = "{default_id}";

    function selectInstrument(id) {{
      if (!instruments[id]) return;
      currentId = id;
      const inst = instruments[id];

      // Update tab active classes
      document.querySelectorAll('.tab-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.dataset.id === id);
      }});

      // Update metadata panel
      document.getElementById('meta-name').textContent = inst.name;
      document.getElementById('meta-scale').textContent = `${{inst.scale_in}}" scale (${{inst.scale_m}} m) | ${{inst.speeds_str}}`;
      document.getElementById('meta-pickups').textContent = inst.pickups_summary;

      const standaloneUrl = `${{baseUrlPrefix}}${{id}}.html`;
      document.getElementById('standalone-link').href = standaloneUrl;
      document.getElementById('chart-frame').src = standaloneUrl;

      if (window.history.replaceState) {{
        window.history.replaceState(null, null, '#' + id);
      }}
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      const hash = window.location.hash.replace('#', '');
      if (hash && instruments[hash]) {{
        selectInstrument(hash);
      }} else {{
        selectInstrument(currentId);
      }}
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
        chart_file = out_dir / f"{inst_id}.html"
        if chart_file.exists() or not any(out_dir.glob("*.html")):
            active_meta[inst_id] = format_instrument_meta(inst_cfg)

    if not active_meta:
        for inst_id, inst_cfg in all_insts.items():
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

def generate_interactive_chart(instrument="30in", out_html=None, source_scale=None):
    """Calculates voice responses and renders an interactive Altair chart."""
    inst_selector = source_scale if source_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector
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

    chart.save(str(target_path))
    print(f"Saved interactive Altair visualization: {target_path}")
    return target_path

def generate_all_charts(output_dir=None):
    """Generates standalone Altair interactive charts for all configured instruments."""
    out_dir = Path(output_dir) if output_dir else RESPONSES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    all_insts = load_all_instruments()
    generated = {}
    for inst_id, inst_cfg in all_insts.items():
        out_file = out_dir / f"{inst_id}.html"
        generate_interactive_chart(instrument=inst_cfg, out_html=out_file)
        generated[inst_id] = out_file

    generate_portal_pages(output_dir=out_dir)
    return generated

def main():
    parser = argparse.ArgumentParser(description="Generate interactive Altair visualization of Passivizer voices.")
    parser.add_argument(
        "--instrument", "-i",
        default="all",
        help="Source instrument configuration (ID, alias like 30in, 32in, path to .toml, or 'all' to generate all)"
    )
    parser.add_argument(
        "--source-scale",
        dest="instrument",
        help="Legacy alias for --instrument (e.g. 30in, 32in)"
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
        target_file = generate_interactive_chart(instrument=inst, out_html=args.out)
        if args.out is None or (Path(args.out).resolve() == RESPONSES_DIR.resolve()):
            generate_portal_pages(output_dir=RESPONSES_DIR, default_id=inst.get("id"))

if __name__ == "__main__":
    main()


