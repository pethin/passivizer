# Passivizer - Agent Development Guidelines

Welcome to **Passivizer**. This repository houses an analog digital twin and modeling pipeline designed to transform active, wideband 18V EMG bass pickups into authentic high-impedance passive pickup configurations (P-Bass, Jazz Bass, StingRay, Rickenbacker, P/J, P/MM) tailored for the **Darkglass Anagram** pedalboard, Neural Amp Modeler (NAM), and DAW plugin hosts.

---

## 1. Physical Hardware Specifications & Datums

### Source Instruments
1. **Current Bass (30" Short Scale):**
   - Pickup: Single active 18V EMG MM (dual coil, fixed aperture $w=1.5''$, coil spacing $d=0.75''$).
   - Physical Datum: Centerline located **$77.5\text{ mm}$ from the bridge** ($303.5\text{ mm}$ from the 12th fret).
   - Character: Warm low-mid bloom ($180\text{--}250\text{ Hz}$), reduced string tension compared to 34".

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
- **Tabular Data & Math:** Strictly use **`polars`** expressions (`pl.col`, `pl.when().then()`) and Python standard library `math`. Do **NOT** use `pandas` or introduce `numpy` in user-facing scripts.
- **Visualizations:** Strictly use **`altair`** (Vega-Lite declarative charts compiling to standalone HTML in `docs/`). Do **NOT** use `matplotlib`.
- **Audio DSP & I/O:**
  - Fast convolution and 24-bit audio file I/O uses **Spotify's `pedalboard`** (JUCE-backed SIMD C++ engine).
  - Minimum-phase FIR synthesis uses our internal homomorphic real-cepstrum Hilbert transform engine in pure Python.
  - Do **NOT** add `scipy` or `soundfile` as dependencies (they carry legacy C/Fortran bloat).
- **SPICE Circuit Simulation:** Standalone `.cir` netlists formatted for headless LTspice (`/Applications/LTspice.app/Contents/MacOS/LTspice -b`).

---

## 3. Repository Layout

```
passivizer/
├── AGENTS.md                 # Antigravity project rules and context (this file)
├── pyproject.toml            # Project metadata (polars, altair, pedalboard)
├── README.md                 # Comprehensive architecture, CLI usage, roadmap
├── main.py                   # Main CLI entrypoint delegation
├── circuits/                 # Standalone SPICE circuit netlists (.cir)
│   ├── 01_jazz_bass_pair.cir
│   └── ... (01 through 11)
├── docs/                     # Technical documentation & interactive charts
│   ├── voice_catalog.md      # Passive pickup models, RLC parameters, character
│   ├── circuit_theory.md     # Differential equations, Dunlop pot, treble bleed
│   ├── aperture_math.md      # Aperture sinc, wave speeds, multi-scale filters
│   ├── anagram_workflow.md   # Darkglass Anagram Block 1 routing & banks
│   └── frequency_responses.html # Interactive Altair visualization
├── models/                   # Trained Neural Amp Modeler (.nam) models
├── scripts/                  # Core Python pipelines
│   ├── model_physics.py      # Aperture sinc, scale wave speeds, and FIR engine
│   ├── analyze_voices.py     # Polars + Altair frequency curve visualizer
│   ├── prep_nam_audio.py     # Spotify Pedalboard NAM audio pre-filter
│   └── run_pipeline.py       # Master end-to-end automated runner
└── tests/                    # Pytest test suite (16 tests)
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
