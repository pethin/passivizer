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
    compute_voice_prefilter_firs,
    synthesize_minimum_phase_fir,
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

        positions = [compute_effective_position(p["coils"]) for p in pickups]
        pos_max = max(positions) if positions else 0.0
        c_mean = float(np.mean(tgt_speeds)) if tgt_speeds else 113.7

        N = 8192
        f_bins = np.fft.rfftfreq(N, 1.0 / 48000.0)
        H_tot = np.zeros(N // 2 + 1, dtype=complex)
        for i, (p, c_curve) in enumerate(zip(pickups, circuit_curves)):
            p_weight = p.get("weight", 1.0)
            p_pol = p.get("polarity", 1.0)
            weight_fac = 1.0 if (cir_path.exists() and len(circuit_curves) > 1) else p_weight
            if sensor_type == "bridge_force":
                f_lin = np.asarray(FREQS, dtype=np.float64)
                is_flatwound = "flat" in tgt_string.get("type", "")
                f_damp = 4200.0 if is_flatwound else 3600.0
                h_damp = 1.0 / np.sqrt((1.0 - (f_lin / f_damp) ** 2) ** 2 + 2.0 * (f_lin / f_damp) ** 2)
                h_sub = np.maximum(f_lin / np.sqrt(f_lin ** 2 + 32.0 ** 2), 0.15)
                h_tilt_raw = np.sqrt((1.0 + (f_lin / 250.0) ** 2) / (1.0 + (f_lin / 70.0) ** 2))
                h_tilt = h_tilt_raw / np.max(h_tilt_raw)
                branch = np.asarray(c_curve, dtype=np.float64) * h_damp * h_sub * h_tilt
            else:
                branch = np.asarray(c_curve, dtype=np.float64) * (weight_fac * p_pol)

            fir_b = synthesize_minimum_phase_fir(branch, num_taps=2048, normalize=False)
            tau_i = (pos_max - positions[i]) / c_mean if len(pickups) > 1 else 0.0
            H_b = np.fft.rfft(fir_b, N)
            if tau_i > 0.0:
                H_b = H_b * np.exp(-1j * 2.0 * np.pi * f_bins * tau_i)
            H_tot += H_b

        h_tgt_total = np.interp(freqs, f_bins, np.abs(H_tot))

        # Tension / Bloom for target instrument
        if tgt_scale == "upright":
            delta_bloom = float(tgt_string.get("bloom_db", 2.8))
            g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
            h_tension = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        else:
            h_tension = np.ones_like(freqs)

        # String voicing for target instrument (relative to standard nickel roundwound)
        if sensor_type != "bridge_force" and cfg.get("target_string") and cfg.get("target_string") != "roundwound_nickel_standard":
            std_str = {"bloom_db": 0.0, "damping_factor": 1.0, "type": "roundwound_nickel"}
            h_str = compute_differential_string_transfer(freqs, std_str, tgt_string)
        else:
            h_str = np.ones_like(freqs)

        mag_raw = h_tgt_total * h_tension * h_str

    else:
        # 2. Input/Output Difference: H_diff = H_target / H_source
        is_passive = (inst.get("electronics") == "passive")
        src_pickup = get_source_pickup(inst, voice_id)

        if is_passive and cir_path.exists():
            src_cir_rel = src_pickup.get("circuit", "circuits/sources/source_standard_p.cir")
            src_cir_path = REPO_ROOT / src_cir_rel
            model = parse_netlist(cir_path)
            apply_magnet_properties_to_model(model, cfg)
            if src_cir_path.exists():
                src_model = parse_netlist(src_cir_path)
                apply_magnet_properties_to_model(src_model, src_pickup)
                circuit_curves = compute_differential_circuit_transfer_functions(model, src_model, freqs=FREQS)
            else:
                circuit_curves = compute_circuit_transfer_functions(model, freqs=FREQS)
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
        H_tot = np.zeros(N // 2 + 1, dtype=complex)
        for i in range(len(prefilter_firs)):
            pf = np.array(prefilter_firs[i], dtype=np.float32)
            cf = np.array(synthesize_minimum_phase_fir(circuit_curves[i], num_taps=2048, normalize=False), dtype=np.float32)
            H_tot += np.fft.rfft(pf, N) * np.fft.rfft(cf, N)
        mag_raw = np.interp(freqs, f_bins, np.abs(H_tot))

    if cfg.get("hpf") and cfg.get("hpf") >= 80.0:
        ref_idx = np.argmin(np.abs(freqs - 1000.0))
    elif cfg.get("sensor_type") == "bridge_force":
        ref_idx = np.argmin(np.abs(freqs - 100.0))
    else:
        ref_idx = 0

    ref_val = mag_raw[ref_idx]
    mag_norm = mag_raw / ref_val if ref_val > 0 else mag_raw
    mag_db = 20.0 * np.log10(np.clip(mag_norm, 1e-5, 20.0)) + cfg.get("gain_db", 0.0)

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
    """Constructs a responsive, dark-mode portal HTML string with view switcher and iframe navigation."""
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
    default_standalone_url = f"{base_url_prefix}{default_id}_diff.html"

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
    }}
    .mode-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 6px 14px;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
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
      padding: 16px 20px;
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

    <div class="view-mode-bar">
      <div class="mode-toggle-group" role="tablist" aria-label="Response Mode">
        <button class="mode-btn active" id="mode-btn-diff" onclick="selectMode('difference')" role="tab" aria-selected="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 3h5v5M4 20L21 3M21 16v5h-5M15 15l6 6M4 4l5 5"></path></svg>
          <span>Input / Output Difference (&Delta;)</span>
        </button>
        <button class="mode-btn" id="mode-btn-output" onclick="selectMode('output')" role="tab" aria-selected="false">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
          <span>Output Voice (Target Profiles)</span>
        </button>
      </div>
      <div class="mode-hint" id="mode-hint">
        Displaying regularized differential transfer function (H_target / H_source) applied to transform {default_meta["name"]} into each voice.
      </div>
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
      <div class="meta-item">
        <div class="label">Response View</div>
        <div class="value" id="meta-view-mode">Input / Output Difference (&Delta; Filter)</div>
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
    let currentMode = "difference";

    function getChartUrl(id, mode) {{
      const modeSuffix = (mode === 'difference' || mode === 'diff') ? '_diff.html' : '_output.html';
      return `${{baseUrlPrefix}}${{id}}${{modeSuffix}}`;
    }}

    function updateView() {{
      const inst = instruments[currentId];
      if (!inst) return;

      // Update tab active classes
      document.querySelectorAll('.tab-btn').forEach(btn => {{
        btn.classList.toggle('active', btn.dataset.id === currentId);
      }});

      // Update mode toggle buttons
      const isDiff = (currentMode === 'difference' || currentMode === 'diff');
      document.getElementById('mode-btn-diff').classList.toggle('active', isDiff);
      document.getElementById('mode-btn-output').classList.toggle('active', !isDiff);

      // Update metadata & hint
      const hintEl = document.getElementById('mode-hint');
      const viewStatusEl = document.getElementById('meta-view-mode');
      if (isDiff) {{
        hintEl.textContent = `Displaying regularized differential transfer function (H_target / H_source) applied to transform ${{inst.name}} into each voice.`;
        if (viewStatusEl) viewStatusEl.textContent = 'Input / Output Difference (Δ Filter)';
      }} else {{
        hintEl.textContent = 'Displaying authentic target passive pickup RLC resonance curves, spatial aperture comb filtering, and loaded frequency responses.';
        if (viewStatusEl) viewStatusEl.textContent = 'Output Voice (Target Profiles)';
      }}

      document.getElementById('meta-name').textContent = inst.name;
      document.getElementById('meta-scale').textContent = `${{inst.scale_in}}" scale (${{inst.scale_m}} m) | ${{inst.speeds_str}}`;
      document.getElementById('meta-pickups').textContent = inst.pickups_summary;

      const chartUrl = getChartUrl(currentId, currentMode);
      document.getElementById('standalone-link').href = chartUrl;
      document.getElementById('chart-frame').src = chartUrl;

      if (window.history.replaceState) {{
        window.history.replaceState(null, null, '#' + currentId + ':' + currentMode);
      }}
    }}

    function selectInstrument(id) {{
      if (!instruments[id]) return;
      currentId = id;
      updateView();
    }}

    function selectMode(mode) {{
      currentMode = (mode === 'output') ? 'output' : 'difference';
      updateView();
    }}

    window.addEventListener('DOMContentLoaded', () => {{
      const hash = window.location.hash.replace('#', '');
      if (hash) {{
        const parts = hash.split(':');
        const hashId = parts[0];
        const hashMode = parts[1];
        if (instruments[hashId]) {{
          currentId = hashId;
        }}
        if (hashMode === 'output') {{
          currentMode = 'output';
        }} else if (hashMode === 'difference' || hashMode === 'diff') {{
          currentMode = 'difference';
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

def generate_interactive_chart(instrument="30in", out_html=None, mode="unified"):
    """
    Calculates voice responses and renders an interactive Altair chart.
    mode:
      - 'unified': embeds both Output Voice and Input/Output Difference curves with interactive radio buttons.
      - 'output': standalone chart strictly plotting the 12 target Output Voice curves.
      - 'difference': standalone chart strictly plotting the Input/Output Difference curves for this instrument.
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

    print(f"Computing voice frequency responses (mode={mode}, instrument={inst_name})...")
    voice_selection = alt.selection_point(fields=["voice_name"], bind="legend")

    if mode == "output":
        dfs = [build_voice_dataframe(vid, cfg, instrument=inst, mode="output") for vid, cfg in VOICES.items()]
        master_df = pl.concat(dfs)
        chart_title = "Passivizer Master Voices: Output Voice Frequency Responses"
        chart_subtitle = f"Target Passive Acoustic Apertures & SPICE Loaded RLC Resonances (Reference: {inst_name})"
        y_title = "Normalized Output Magnitude (dB)"
        y_domain = [-30, 10]
        params = [voice_selection]
        filters = []
    elif mode == "difference":
        dfs = [build_voice_dataframe(vid, cfg, instrument=inst, mode="difference") for vid, cfg in VOICES.items()]
        master_df = pl.concat(dfs)
        chart_title = "Passivizer Master Voices: Input/Output Differential Transfer Functions"
        chart_subtitle = f"Source: {inst_name} -> Target: 34\" Standard & 37\" Multi-Scale Datums (Δ Transfer Filter)"
        y_title = "Differential Transfer Magnitude (dB)"
        y_domain = [-28, 12]
        params = [voice_selection]
        filters = []
    else:  # mode == "unified"
        dfs_out = [build_voice_dataframe(vid, cfg, instrument=inst, mode="output", include_mode_col=True) for vid, cfg in VOICES.items()]
        dfs_diff = [build_voice_dataframe(vid, cfg, instrument=inst, mode="difference", include_mode_col=True) for vid, cfg in VOICES.items()]
        master_df = pl.concat(dfs_diff + dfs_out)
        chart_title = "Passivizer Master Voices: Acoustic & Electrical Response Curves"
        chart_subtitle = f"Interactive View ({inst_name}) — Switch between Input/Output Difference and Output Voice"
        y_title = "Normalized Magnitude / Differential Gain (dB)"
        y_domain = [-30, 12]
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

    print("Rendering interactive chart using Altair...")
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
                title="Passivizer Pickup Profile (Click to isolate)",
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
        width=920,
        height=520
    ).configure_view(strokeWidth=0).interactive()

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
        # 1. Standalone Output Voice chart
        out_output_file = out_dir / f"{inst_id}_output.html"
        generate_interactive_chart(instrument=inst_cfg, out_html=out_output_file, mode="output")

        # 2. Standalone Input/Output Difference chart
        out_diff_file = out_dir / f"{inst_id}_diff.html"
        generate_interactive_chart(instrument=inst_cfg, out_html=out_diff_file, mode="difference")

        # 3. Main unified chart with interactive switcher
        out_file = out_dir / f"{inst_id}.html"
        generate_interactive_chart(instrument=inst_cfg, out_html=out_file, mode="unified")
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
        "--mode", "-m",
        choices=["unified", "output", "difference"],
        default="unified",
        help="Chart mode: 'unified' (both with switcher), 'output' (target response), or 'difference' (transfer function)"
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


