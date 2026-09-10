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
- **Tabular Data & Visualizations:** Strictly use **`polars`** for dataframes and tabular structures (`pl.DataFrame`, `pl.concat`), and **`altair`** (Vega-Lite declarative charts compiling to standalone HTML in `docs/`). Do **NOT** use `pandas` or `matplotlib`.
- **Numerical Math & DSP:** Strictly use **`numpy`** for 1D frequency responses, acoustic/electrical vector math, and FFTs (`np.fft`).
- **Audio DSP & I/O:**
  - 24-bit audio file I/O uses **Spotify's `pedalboard`** (JUCE-backed SIMD C++ engine).
  - Minimum-phase FIR synthesis uses our internal homomorphic real-cepstrum Hilbert transform engine vectorized with NumPy.
  - Do **NOT** add `scipy` or `soundfile` as dependencies (they carry legacy C/Fortran bloat).
- **Circuit Simulation Engine:**
  - **Native WAV SPICE Engine:** Built-in Apple Silicon (`arm64`) WAV SPICE circuit simulation engine (`scripts/simulate_circuits.py`) providing zero-external-dependency SPICE netlist parsing, analytical nodal RLC solving, regularized differential SPICE transfer functions ($H_{\text{diff}} = H_{\text{target}} / H_{\text{source}}$) for passive instruments, dynamic core saturation bypass, and vector soft-knee saturation ($V_{\text{sat}} \cdot \tanh(v/V_{\text{sat}})$) directly on audio waveforms at >1500x speed.

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
│   ├── 01_modern_jazz_active.cir
│   └── ... (01 through 14)
├── config/                   # Modular TOML configuration files
│   ├── instruments/          # Source bass definitions (scale, pickups, routing)
│   ├── scales.toml           # Standard scale wave speeds
│   └── voices.toml           # Voice metadata linking to SPICE netlists
├── docs/                     # Technical documentation & interactive charts
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
└── tests/                    # Pytest test suite (95 tests)
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

## 5. Architectural Guardrails: Physical Modeling Bug Classes to Prevent

To ensure high-fidelity modeling and prevent regressions, all agents and contributors must adhere to these seven architectural rules when modifying the DSP, physics, and simulation pipelines:

### 5.1 No Hardcoded Frequency Cutoffs for Wave/Delay Phenomena
- **Anti-Pattern:** Hardcoding static frequency boundaries (e.g. `f_start = 620.0`, `f_end = 1050.0` or `f_taper_start = 1800.0`, `f_taper_end = 3200.0`) for acoustic comb interference or de-combing.
- **Why It Fails:** Multi-pickup spacings vary dramatically across models: Jazz Bass ($\Delta x = 92.1\text{ mm}$), P/J ($\Delta x = 61.5\text{ mm}$), P/MM ($\Delta x \approx 66\text{ mm}$), as do scale lengths (30", 32", 34", 37"). A fixed $620\text{--}1050\text{ Hz}$ window terminates coherence decay before the $960\text{ Hz}$ P/J comb notch can fully form, destroying the acoustic mid-scoop. Similarly, de-combing up to $3200\text{ Hz}$ on a neck pickup inverts higher-order harmonic notches, causing harsh treble ripple noise.
- **Mandated Practice:** Always derive transition boundaries dynamically from actual impulse peak delays or physical pickup datums:
  - **Inter-Pickup Coherence Window:** $f_{\text{notch}} = \frac{1}{2\Delta\tau} = \frac{f_s}{2 \cdot \Delta\text{peaks}}$, with $f_{\text{start}} = f_{\text{notch}}$ and $f_{\text{end}} = 1.7 \cdot f_{\text{notch}}$.
  - **Source De-Combing Taper:** $f_{\text{peak, src}} = \frac{\bar{c}}{x_{\text{src}}}$, with $f_{\text{taper\_start}} = \min(f_{\text{peak, src}}, 2500\text{ Hz})$ and $f_{\text{taper\_end}} = \min(1.8 f_{\text{taper\_start}}, 4500\text{ Hz})$.

### 5.2 Wavelength-Dependent Coherence Decay ($\lambda \le d$) for Multi-Coil Pickups
- **Anti-Pattern:** Applying a global static high-frequency transition (e.g. $f > 6\text{ kHz}$) for dual-coil humbucker cross-coherence decay.
- **Why It Fails:** Transverse string wave speeds differ widely across the 4 strings ($71.2\text{ m/s}$ on Low-E to $169.3\text{ m/s}$ on G). On the Low-E string, the second harmonic comb null occurs at $f = \frac{3v}{2d} \approx 5.61\text{ kHz}$. A static $6\text{ kHz}$ cutoff leaves this null in the 100% coherent zone, creating an unphysical notch/shelf at $5.4\text{ kHz}$.
- **Mandated Practice:** Coherence decay must be evaluated **per string** based on acoustic wavelength $\lambda = v / f$ relative to coil spacing $d$:
  $$f_{\text{start}} = \frac{v}{d}, \quad f_{\text{end}} = 1.8 \cdot \frac{v}{d}$$
  $$\gamma(f, v) = \frac{1}{2}\left[1 + \cos\left(\pi \cdot \text{clip}\left(\frac{f - f_{\text{start}}}{f_{\text{end}} - f_{\text{start}}}, 0, 1\right)\right)\right]$$
  Transition begins right after the fundamental constructive peak ($f_{\text{start}}$), smoothly blending into incoherent power summation and completely eliminating secondary harmonic comb nulls while preserving the authentic fundamental mid-scoop ($f = \frac{v}{2d}$).

### 5.3 Distinguish Sidewinder Architecture from Dual-Coil Spatial Arrays
- **Anti-Pattern:** Modeling a Gibson Mudbucker (or any sidewinder humbucker) as two discrete sensing coils separated by distance $d$ along the string.
- **Why It Fails:** In a sidewinder (Gibson EB-0/EB-3), two horizontal bobbins feed magnetic flux into a **single central row of vertical pole screws** directly under the string. Because there is only one sensing point along the string axis ($\Delta x = 0$), there is **zero inter-coil phase delay or comb filtering**. Modeling it as two spaced coils applies an unphysical $3.2\text{ kHz}$ comb notch and creates severe zigzag ripple teeth when interacting with active source pickup deconvolution filters.
- **Mandated Practice:** Always check physical pole piece geometry. If coils feed a single row of pole pieces ($\Delta x = 0$), configure a single coil entry with effective center position ($x = x_{\text{center}}$) and expanded aperture width ($w \approx 1.25''$), never a multi-coil array.

### 5.4 Scale-Normalized Fractional Coordinates ($\eta = x / L$) for Bridge Proximity Tilt
- **Anti-Pattern:** Subtracting raw millimeters ($\Delta x_{\text{raw}} = x_{\text{tgt}} - x_{\text{src}}$) to calculate bridge proximity frequency tilt between different scale lengths.
- **Why It Fails:** Standing-wave harmonic profiles scale proportionally with vibrating string length: $\sin(n\pi x / L) = \sin(n\pi \eta)$. A pickup at $62.2\text{ mm}$ on a 32" scale ($\eta = 7.64\%$) sits at the identical harmonic node as a pickup at $66.0\text{ mm}$ on a 34" scale ($\eta = 7.64\%$). Subtracting raw millimeters claims a false $+0.15''$ forward displacement, mistakenly applying proximity tilt between matching sweet spots.
- **Mandated Practice:** Always compute displacement using fractional coordinates normalized to standard 34" equivalent inches:
  $$\eta_{\text{tgt}} = \frac{x_{\text{tgt}}}{L_{\text{tgt}}}, \quad \eta_{\text{src}} = \frac{x_{\text{src}}}{L_{\text{src}}}, \quad \Delta x_{\text{in}} = (\eta_{\text{tgt}} - \eta_{\text{src}}) \times 34.0''$$

### 5.5 Dynamic Target Scale Resolution vs. Hardcoded String Equality
- **Anti-Pattern:** Testing strict string equality `target_scale_key == "34in"` when applying scale physics such as string tension snap.
- **Why It Fails:** Multi-scale instruments (`scale = "multiscale"` in Voice 13) have effective scale lengths of $37.0''$ on low strings ($35.5''$ mean). Hardcoding `== "34in"` skips tension snap for multiscale conversions, giving a 30" short scale bass $+1.8\text{ dB}$ snap when converting to standard 34", but $0.0\text{ dB}$ snap when converting to high-tension 34"–37" multi-scale.
- **Mandated Practice:** Dynamically resolve effective target scale length ($L_{\text{tgt}} = 37.0''$ for multiscale, $34.0''$ otherwise) and apply proportional tension snap whenever $L_{\text{src}} < L_{\text{tgt}}$:
  $$\text{snap\_db} = \min\left(3.5\text{ dB}, 1.8 \cdot \frac{L_{\text{tgt}} - L_{\text{src}}}{4.0''}\right)$$

### 5.6 Soft-Knee Saturation vs. Hard Clipping Plateaus and Denominator Floors
- **Anti-Pattern:** Clamping ratio denominators with premature floors (e.g. `np.maximum(src_mag, 0.05)`) or applying hard rectangular clipping (e.g. `np.clip(ratio, 0.15, 3.0)` or `np.clip(..., 0.25, 2.5)`).
- **Why It Fails:** At high frequencies, damped source string magnitudes naturally fall below $0.05$ (e.g. vintage flatwounds at $20\text{ kHz}$ drop to $0.0081$). Freezing the denominator at $0.05$ causes identical strings (`flatwound_vintage_heavy -> flatwound_vintage_heavy`) to plunge down by $-16.48\text{ dB}$ instead of remaining exactly $0.00\text{ dB}$! Hard clipping creates artificial flat tabletop plateaus with slope kinks, inducing severe Gibbs ringing in minimum-phase cepstral FIR synthesis.
- **Mandated Practice:** Use machine epsilon / regularized denominators ($10^{-6}$) to ensure identical strings evaluate to exact $1.0000$ ($0.00\text{ dB}$) across all frequencies. Bound maximum boosts and acoustic damping using asymptotic bidirectional soft-knee saturation ($\tanh$):
  $$r_{\text{db}} = 20 \log_{10}(\text{ratio})$$
  $$r_{\text{soft\_db}} = \begin{cases} g_{\text{max}} \cdot \tanh(r_{\text{db}} / g_{\text{max}}) & \text{if } r_{\text{db}} > 0 \\ g_{\text{min}} \cdot \tanh(r_{\text{db}} / g_{\text{min}}) & \text{if } r_{\text{db}} \le 0 \end{cases}$$
  Guaranteeing $C^1$ smoothness everywhere and completely eliminating flat-topped plateaus.

### 5.7 Smooth $C^1$ Transition across $0\text{ dB}$ in Band-Limited Limiters
- **Anti-Pattern:** Using piecewise conditionals like `np.where(h_db_soft > 0.0, h_db_soft * s, h_db_soft)` to apply high-frequency boost tapers ($s = 0.25 + 0.75 w$).
- **Why It Fails:** Whenever a differential circuit transfer curve crosses $0.0\text{ dB}$ in the taper region ($8\text{--}20\text{ kHz}$), the first derivative abruptly jumps by a factor of $1/s \approx 2.5\text{--}4\times$. This creates an unnatural slope kink right at $0.0\text{ dB}$, degrading impulse response decay.
- **Mandated Practice:** Use smooth softplus blending:
  $$\text{excess\_boost} = \frac{1}{\beta} \ln(1 + e^{\beta \cdot h_{\text{db\_soft}}}) = \frac{1}{\beta} \text{logaddexp}(0, \beta \cdot h_{\text{db\_soft}}), \quad \beta = 1.2$$
  $$h_{\text{db\_final}} = h_{\text{db\_soft}} - (1.0 - s) \cdot \text{excess\_boost}$$
  Guarantees strictly continuous first derivatives ($C^\infty$) across the $0.0\text{ dB}$ crossing point while keeping attenuation ($h_{\text{db}} \le 0$) untouched.

