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
- **Standard 34" Scale:** Standard Fender ($125.0\text{ mm}$ P, $155.6\text{ mm}$ 60s J neck, $63.5\text{ mm}$ 60s J bridge) and Music Man ($66.0\text{ mm}$ StingRay).
- **34"-37" Multi-Scale (Dingwall Fanned Fret):** High-tension wave speeds ($77.4\text{--}169.3\text{ m/s}$), angled bridge sweet spot ($48.0\text{ mm}$ datum), FD3 parallel dual-coil SPICE netlist ($f_r = 3.4\text{ kHz}, Q = 1.5$), and stainless-steel roundwound harmonic extension.

---

## 2. Tech Stack & Engineering Constraints

When contributing to or maintaining this repository, strictly adhere to these architectural standards:

- **Package & Environment Manager:** Always use **`uv`** (`uv run`, `uv add`).
- **Tabular Data & Visualizations:** Strictly use **`polars`** for dataframes (`pl.DataFrame`, `pl.concat`) and **`altair`** (Vega-Lite declarative charts compiling to standalone HTML in `docs/`). Do **NOT** use `pandas` or `matplotlib`.
- **Numerical Math & DSP:** Strictly use **`numpy`** for 1D frequency responses, acoustic/electrical vector math, and FFTs (`np.fft`).
- **Audio DSP & I/O:**
  - 24-bit audio file I/O uses **Spotify's `pedalboard`** (JUCE-backed SIMD C++ engine).
  - Minimum-phase FIR synthesis uses our internal homomorphic real-cepstrum Hilbert transform engine vectorized with NumPy.
  - Do **NOT** add `scipy` or `soundfile` as dependencies (they carry legacy C/Fortran bloat).
- **Circuit Simulation Engine:**
  - **Native WAV SPICE Engine:** Built-in Apple Silicon (`arm64`) WAV SPICE circuit simulation engine (`scripts/simulate_circuits.py`) providing zero-external-dependency SPICE netlist parsing, analytical nodal RLC solving, regularized differential SPICE transfer functions ($H_{\text{diff}} = H_{\text{target}} / H_{\text{source}}$), dynamic core saturation bypass, and vector soft-knee saturation ($V_{\text{sat}} \cdot \tanh(v/V_{\text{sat}})$) directly on audio waveforms at >1500x speed.

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
│   ├── sources/              # Active and commercial source instrument netlists
│   └── ... (01 through 14)
├── config/                   # Modular TOML configuration files
│   ├── instruments/          # Source bass definitions (scale, pickups, routing)
│   ├── scales.toml           # Standard scale wave speeds
│   ├── strings.toml          # Physical string core/wrap presets
│   └── voices.toml           # Voice metadata linking to SPICE netlists
├── docs/                     # Technical documentation & interactive charts
│   ├── architectural_guardrails.md # Master mathematical reference handbook & derivations
│   ├── voice_catalog.md      # Passive pickup models, RLC parameters, character
│   ├── circuit_theory.md     # Differential equations, 500k volume pot, treble bleed
│   ├── aperture_math.md      # Aperture sinc, wave speeds, multi-scale filters
│   ├── anagram_workflow.md   # Darkglass Anagram Block 1 routing & banks
│   ├── frequency_responses.html # Master interactive portal
│   └── frequency_responses/     # Per-instrument standalone Altair visualizations
├── models/                   # Trained Neural Amp Modeler (.nam) models (models/<instrument>/)
├── scripts/                  # Core Python pipelines
│   ├── model_physics.py      # Aperture sinc, scale wave speeds, and FIR engine
│   ├── analyze_voices.py     # Polars + Altair frequency curve visualizer & portal generator
│   ├── prep_nam_audio.py     # Standalone/legacy aperture pre-filter exporter
│   ├── simulate_circuits.py  # Native WAV SPICE simulator (in-memory aperture + circuit sim)
│   └── run_pipeline.py       # Master end-to-end automated runner
└── tests/                    # Pytest test suite (test_circuits, test_physics, test_guardrails)
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

---

## 5. Architectural Guardrails (Core Invariants)

All code contributions must strictly satisfy the following normative invariants (verified automatically via `tests/test_guardrails.py`). Complete mathematical proofs and derivations are documented in [`docs/architectural_guardrails.md`](file:///Users/peter/Projects/pethin/passivizer/docs/architectural_guardrails.md).

### 5.1 Spatial Acoustics, Scale Physics & Continuum Routing
1. **Dynamic Spatial Boundaries:** Derive comb null and de-combing taper boundaries dynamically from delays ($\bar{c}/x_{\text{src}}$); never hardcode static cutoff bins.
2. **Coherence Decay & Spatial Delays:** Cross-coherence decay across dual coils must transition smoothly into incoherent summation when $\lambda \le d$ (engage whenever $\Delta\text{samples} > 0$). Multi-pickup arrival delays ($\tau_i$) must be applied via causal integer sample shifts ($[0]*k + \text{fir}[:-k]$); never rotate phase via circular FFT ($e^{-j 2\pi f \tau_i}$) which wraps non-causal tails and injects high-frequency Gibbs truncation ripples. Model sidewinders as a single centered coil ($w \approx 1.25''$).
3. **Fractional Coordinates & Scale Snap:** Use scale-normalized fractional coordinates ($\eta = x / L \cdot 34''$); never subtract raw millimeters across scales. Apply proportional high-frequency tension snap when $L_{\text{src}} < L_{\text{tgt}}$, and model steel core longitudinal compression clank ($H_{\text{long}}$ at $2.7\text{--}3.3\text{ kHz}$).
4. **Wave-Speed Continuum:** Integrate aperture responses across a continuous 24-point log continuum ($30.87\text{ to } 100\text{ Hz}$) routed geometrically by register halves (`[1, 2]` treble vs `[3, 4]` bass), never note names. Keep `scripts/train_nam.py` strictly untouched.

### 5.2 Mathematical Smoothness & Regularization ($C^\infty$)
1. **Regularized Denominators & Softplus Blending:** Never clamp denominators with premature hard floors; use $\max(\text{mag}, 10^{-6})$ so identical setups yield exact $0.00\text{ dB}$. Use smooth softplus blending (`logaddexp`) across $0\text{ dB}$ (no piecewise conditionals or slope kinks). Bound boost/cut via asymptotic soft-knee saturation ($g \cdot \tanh(r_{\text{db}}/g)$).
2. **Quadrature Null Floors & Absolute Units:** Preserve 3D flux fringing with a quadrature floor ($\epsilon_{\text{quad}} \approx 0.18$) at comb nulls. Evaluate curves in absolute gain units ($20\log_{10}(\max(h_{\text{diff}}, 10^{-6}))$); never normalize by an arbitrary mid-frequency bin.

### 5.3 True Differential Circuit Deconvolution & Staging Integrity
1. **True Differential Deconvolution:** Evaluate $H_{\text{diff}} = H_{\text{tgt}} / H_{\text{src}}$ using dedicated netlists in `circuits/sources/` for active/buffered instruments. Exact equality must evaluate to $0.00\text{ dB}$ across all bins.
2. **Double Voicing Prevention:** Automatically bypass prefiltering if audio file starts with `aperture_`. Multi-channel target circuits evaluate branch FIRs with unity weight ($p_{\text{weight}} = 1.0$), letting the SPICE nodal network evaluate current division.
3. **Sub-Audible DC Transmission:** Active preamps must feature flat, finite DC transmission ($H_{\text{preamp}}(0) \ge 1.0$). Strictly omit sub-audible AC-coupling differentiators ($s / (s + \omega_{\text{sub}})$) from preamp EQ models to prevent Gibbs truncation ripples ($\Delta f = f_s / N = 23.4\text{ Hz}$) across $20\text{--}300\text{ Hz}$.

### 5.4 Differential Non-Linear Metallurgy & Dynamics
1. **Differential Metallurgy Softening:** Soften differentially based on relative target vs source metallurgy ($\Delta\alpha, \Delta k_{\text{sag}}, \Delta k_{\text{eddy}}, \Delta\kappa_{\text{geom}}, \Delta k_{\text{stein}}$). Bypass on small signals ($\le 0.10$) to preserve bit-exact test linearity.
2. **Dynamic Magnetic Feel:** Model magnetic string pull damping and attack pitch sag in `_lenz_velocity_drag_core`, displacement-modulated touch highpass tilt ($\tau_{\text{touch}}$), eddy de-Qing, $2f_0$ orbit bloom, core curvature wobble, soft-knee slew limiting, conformal clearance divergence, and $-108\text{ dBFS}$ Johnson noise dither.

### 5.5 Complex Electrical Impedance & Harnesses
1. **Fractional Dielectric & Permeability:** Model tone cap and cable admittance via Cole-Davidson fractional frequency scaling ($\alpha_{\text{tone}} \approx 0.988, \alpha_{\text{cable}} \approx 0.994$) and causal Jordan core relaxation ($\mu^*(\omega)$).
2. **Coupled System & Harness Controls:** Solve coupled $2\times 2$ nodal transfer matrix for parallel coils, hyperbolic transmission line admittance ($\tanh(\gamma)/\gamma$), and interactive volume/tone wiper splitting with cable capacitance loading ($P_{\text{vol}}, P_{\text{tone}}$).

---

## 6. High-Performance Audio DSP & SIMD Directives

To maintain simulation speeds exceeding $>1500\times$ real time:
1. **Buffer & Recurrence Acceleration:** Never execute interpreted Python loops over audio buffers. Compile recursive ODE state solvers with Numba (`@njit(fastmath=True)`). Pack 24-bit little-endian WAV bytes via C view slicing (`.astype("<i4").view(np.uint8)`). Formulate nodal circuit transfers on complex NumPy vectors ($s = 1j \cdot \omega$).
2. **Stage Fusion & Caching:** Fuse linear filter stages in the frequency domain. Broadcast input forward FFTs across channels. Cache parsed netlists with `@functools.lru_cache`. Precompute global target voice dataframes once.
3. **Automated Verification:** All changes must satisfy automated property assertions in `tests/test_guardrails.py`.
