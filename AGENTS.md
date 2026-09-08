# Passivizer - Agent Development Guidelines

Welcome to **Passivizer**. This repository houses an analog digital twin and modeling pipeline designed to transform active, wideband 18V EMG bass pickups into authentic high-impedance passive pickup configurations (P-Bass, Jazz Bass, StingRay, Rickenbacker, P/J, P/MM) tailored for the **Darkglass Anagram** pedalboard, Neural Amp Modeler (NAM), and DAW plugin hosts.

---

## 1. Physical Hardware Specifications & Datums

### Source Instruments
1. **Current Bass (30" Short Scale):**
   - Pickup: Single active 18V EMG MMTW (dual-mode: MM dual coil or J single-coil, coil spacing $d=0.90''$, coil aperture $w=0.75''$).
   - Physical Datum: Centerline located **$77.5\text{ mm}$ from the bridge** ($303.5\text{ mm}$ from the 12th fret; neck coil $88.9\text{ mm}$, bridge coil $66.1\text{ mm}$).
   - Character: Warm low-mid bloom ($180\text{--}250\text{ Hz}$), reduced string tension compared to 34", selectable J-bridge growl or MM authority.

2. **Planned Bass (32" Medium Scale):**
   - Routing: Reverse EMG PX split ($122.8\text{ mm}$ from bridge) + EMG MMTWX ($62.2\text{ mm}$ centerline, $50.8\text{ mm}$ bridge coil) with EMG ABCX active blend.
   - Reference: `/Users/peter/Projects/pethin/medium-scale-bass/Pickup Placement - P_MM.md`.

### Target Instruments & Tonal Scalings
- **Standard 34" Scale:** Standard Fender ($125.0\text{ mm}$ P, $40.6\text{ mm}$ 70s J bridge) and Music Man ($66.0\text{ mm}$ StingRay).
- **34"-37" Multi-Scale (Dingwall Fanned Fret):** High-tension wave speeds, angled bridge sweet spot ($48.0\text{ mm}$), tightened sub-bass ($+1.5\text{ dB}$ @ $75\text{ Hz}$), trimmed low-mids ($-3.5\text{ dB}$ @ $220\text{ Hz}$), and metallic clank ($+3.5\text{ dB}$ @ $3.2\text{ kHz}$).

---

## 2. Tech Stack & Engineering Constraints

When contributing to or maintaining this repository, strictly adhere to these architectural standards:

- **Package & Environment Manager:** Always use **`uv`** (`uv run`, `uv add`).
- **Tabular Data & Visualizations:** Strictly use **`polars`** for dataframes and tabular structures (`pl.DataFrame`, `pl.concat`), and **`altair`** (Vega-Lite declarative charts compiling to standalone HTML in `docs/`). Do **NOT** use `pandas` or `matplotlib`.
- **Numerical Math & DSP:** Strictly use **`numpy`** for 1D frequency responses, acoustic/electrical vector math, and FFTs (`np.fft`).
- **Audio DSP & I/O:**
  - 24-bit audio file I/O uses **Spotify's `pedalboard`** (JUCE-backed SIMD C++ engine).
  - Minimum-phase FIR synthesis uses our internal homomorphic real-cepstrum Hilbert transform engine vectorized with NumPy.
  - Do **NOT** add `scipy` or `soundfile` as dependencies (they carry legacy C/Fortran bloat).
- **Circuit Simulation Engine:**
  - **Native Engine (Default):** Native Apple Silicon (`arm64`) Virtual Analog solver (`scripts/simulate_circuits.py`) providing zero-external-dependency analytical nodal RLC solving and vector soft-knee saturation ($V_{\text{sat}} \cdot \tanh(v/V_{\text{sat}})$) at >1500x speed.
  - **LTspice (Optional Legacy):** Standalone `.cir` netlists formatted for headless LTspice (`/Applications/LTspice.app/Contents/MacOS/LTspice -b`) selectable via `--backend ltspice`.

---

## 3. Repository Layout

```
passivizer/
├── AGENTS.md                 # Antigravity project rules and context (this file)
├── pyproject.toml            # Project metadata (polars, altair, pedalboard)
├── README.md                 # Comprehensive architecture, CLI usage, roadmap
├── main.py                   # Main CLI entrypoint delegation
├── audio/                    # Generated 24-bit audio digital twins (audio/<instrument>/)
├── circuits/                 # Standalone SPICE circuit netlists (.cir)
│   ├── 01_jazz_bass_pair.cir
│   └── ... (01 through 11)
├── config/                   # Modular TOML configuration files
│   ├── instruments/          # Source bass definitions (scale, pickups, routing)
│   ├── scales.toml           # Standard scale wave speeds
│   └── voices.toml           # Voice metadata linking to SPICE netlists
├── docs/                     # Technical documentation & interactive charts
│   ├── voice_catalog.md      # Passive pickup models, RLC parameters, character
│   ├── circuit_theory.md     # Differential equations, 500k volume pot, treble bleed
│   ├── aperture_math.md      # Aperture sinc, wave speeds, multi-scale filters
│   ├── anagram_workflow.md   # Darkglass Anagram Block 1 routing & banks
│   └── frequency_responses.html # Interactive Altair visualization
├── models/                   # Trained Neural Amp Modeler (.nam) models (models/<instrument>/)
├── scripts/                  # Core Python pipelines
│   ├── model_physics.py      # Aperture sinc, scale wave speeds, and FIR engine
│   ├── analyze_voices.py     # Polars + Altair frequency curve visualizer
│   ├── prep_nam_audio.py     # Standalone/legacy aperture pre-filter exporter
│   ├── simulate_circuits.py  # Unified Virtual Analog engine (in-memory aperture + circuit sim)
│   └── run_pipeline.py       # Master end-to-end automated runner
└── tests/                    # Pytest test suite (45 tests)
```

---

## 4. Signal Flow on Darkglass Anagram

The models produced by Passivizer are loaded into **Block 1** (as a high-impedance passive pickup front-end before preamp and drive):
```
[Bass: 18V EMG] -> [Block 1: Passivizer NAM] -> [Block 2: Darkglass Preamp/Drive] -> [Block 3: Cab IR Loader] -> [FOH/Audio Interface]
```
- **Block 1 (NAM Preamp):** Load trained `.nam` neural model (feather/nano architecture) capturing full RLC resonance, eddy currents, and non-linear magnetic feel.
- **Block 2 (Darkglass Preamp/Drive):** Microtubes B7K, Vintage Ultra, or Alpha·Omega for bass saturation.
- **Block 3 (Cabinet IR Loader):** Downstream speaker cabinet impulse responses (4x10, 8x10, 2x12).
