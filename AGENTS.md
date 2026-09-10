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

To ensure high-fidelity modeling and prevent regressions, all contributors must strictly adhere to these five consolidated physical modeling rules:

### 5.1 Spatial Acoustics, Scale Physics & Tuning/Gauge Invariance
1. **Dynamic Comb & De-Combing Boundaries:** Never hardcode static cutoff frequencies for wave/delay phenomena. Derive transition boundaries dynamically from actual impulse peak delays or physical pickup datums:
   $$f_{\text{notch}} = \frac{1}{2\Delta\tau} = \frac{f_s}{2 \cdot \Delta\text{peaks}}, \quad f_{\text{start}} = f_{\text{notch}}, \quad f_{\text{end}} = 1.7 \cdot f_{\text{notch}}$$
   $$f_{\text{peak, src}} = \frac{\bar{c}}{x_{\text{src}}}, \quad f_{\text{taper\_start}} = \min(f_{\text{peak, src}}, 2500\text{ Hz}), \quad f_{\text{taper\_end}} = \min(1.8 f_{\text{taper\_start}}, 4500\text{ Hz})$$
2. **Wavelength-Dependent Coherence Decay ($\lambda \le d$):** Evaluate humbucker cross-coherence decay dynamically per string/continuum wave speed $v$ based on acoustic wavelength $\lambda = v/f$ relative to coil spacing $d$:
   $$f_{\text{start}} = \frac{v}{d}, \quad f_{\text{end}} = 1.8 \cdot \frac{v}{d}, \quad \gamma(f, v) = \frac{1}{2}\left[1 + \cos\left(\pi \cdot \text{clip}\left(\frac{f - f_{\text{start}}}{f_{\text{end}} - f_{\text{start}}}, 0, 1\right)\right)\right]$$
   Transition begins right after the constructive peak ($f_{\text{start}}$), smoothly blending into incoherent power summation. Always engage coherence decay for any non-zero sample delay ($\text{has\_spatial\_delay} = (\text{len}(\text{channels}) > 1 \land \Delta\text{samples} > 0)$).
3. **Sidewinder Architecture:** If coils feed a single central row of pole pieces under the string ($\Delta x = 0$, e.g. Gibson Mudbucker), configure a single coil entry with effective center position ($x = x_{\text{center}}$) and expanded aperture width ($w \approx 1.25''$), never a multi-coil spaced array.
4. **Scale-Normalized Fractional Coordinates ($\eta = x / L$):** Never subtract raw millimeters across different scale lengths. Calculate displacement using fractional coordinates normalized to standard 34" equivalent inches:
   $$\eta_{\text{tgt}} = \frac{x_{\text{tgt}}}{L_{\text{tgt}}}, \quad \eta_{\text{src}} = \frac{x_{\text{src}}}{L_{\text{src}}}, \quad \Delta x_{\text{in}} = (\eta_{\text{tgt}} - \eta_{\text{src}}) \times 34.0''$$
5. **Dynamic Target Scale Resolution & Tension Snap:** Dynamically resolve effective target scale length ($L_{\text{tgt}} = 37.0''$ for multiscale, $34.0''$ otherwise) and apply proportional tension snap whenever $L_{\text{src}} < L_{\text{tgt}}$:
   $$\text{snap\_db} = \min\left(3.5\text{ dB}, 1.8 \cdot \frac{L_{\text{tgt}} - L_{\text{src}}}{4.0''}\right)$$
6. **Continuous Wave-Speed Continuum ($f_0 \in [30.87, 100]\text{ Hz}$):** Never constrain acoustic spatial filtering to 4 discrete open-string wave speeds or note-name strings (`["E", "A"]`). Integrate acoustic aperture responses ($H_{\text{composite}}$) across a continuous, log-spaced distribution ($N \ge 24$ points, uniform $1/N$ weight) spanning Low B ($30.87\text{ Hz}$) to open G ($100.00\text{ Hz}$). Route continuum points geometrically via register halves (`[1, 2]` treble vs `[3, 4]` bass), never note names. Derive string stiffness $B_s(f_0)$ logarithmically and calculate mean propagation delay using register centroid $\bar{f}_0 = 66.9045\text{ Hz}$ ($\bar{c} = 2 L \bar{f}_0$). Keep `scripts/train_nam.py` strictly untouched.

### 5.2 Mathematical Smoothness, Regularization & Boundary Continuity ($C^1 / C^\infty$)
1. **Regularized Denominators & Soft-Knee Saturation:** Never clamp transfer ratio denominators with premature floors (e.g. `np.maximum(mag, 0.05)`) or apply hard rectangular clipping (`np.clip(..., 0.15, 3.0)`). Use regularized denominators ($\max(\text{mag}, 10^{-6})$) so identical profiles evaluate to exact $1.0000$ ($0.00\text{ dB}$). Bound maximum boosts and damping using asymptotic bidirectional soft-knee saturation:
   $$r_{\text{db}} = 20 \log_{10}(\text{ratio}), \quad r_{\text{soft\_db}} = g \cdot \tanh(r_{\text{db}} / g)$$
2. **Smooth $C^\infty$ Transition Across $0\text{ dB}$ Threshold:** Never use piecewise conditionals (`np.where(h > 0, h * s, h)`) which create first-derivative slope kinks at $0\text{ dB}$. Use smooth softplus blending:
   $$\text{excess\_boost} = \frac{1}{\beta} \ln(1 + e^{\beta \cdot h_{\text{db\_soft}}}) = \frac{1}{\beta} \text{logaddexp}(0, \beta \cdot h_{\text{db\_soft}}), \quad \beta = 1.2$$
   $$h_{\text{db\_final}} = h_{\text{db\_soft}} - (1.0 - s) \cdot \text{excess\_boost}$$
3. **Quadrature Regularization Floor at Comb Nulls:** Never evaluate multi-coil humbucker cancellation as a raw rectified phasor sum ($|\cos(\pi f d / v)|$), which creates non-differentiable V-shaped cusps at nulls. Account for 3D flux fringing with a quadrature regularized floor ($\epsilon_{\text{quad}} \approx 0.18$):
   $$p_{\text{coh\_reg}} = p_{\text{coh}} + \epsilon_{\text{quad}}^2 \cdot p_{\text{incoh}}, \quad m_{\text{blend}} = \frac{\sqrt{\gamma \cdot p_{\text{coh\_reg}} + (1 - \gamma) p_{\text{incoh}}}}{\text{dc\_norm}}$$
4. **Absolute Transfer Ratios (No Mid-Band Reference Normalization):** Never normalize differential circuit curves by dividing by an arbitrary mid-frequency bin like 1 kHz (`h_diff / h_diff[1 kHz]`). Passive circuits naturally attenuate high frequencies; mid-band normalization artificially projects attenuation into false low-frequency boost, clamping tone-rolled profiles. Evaluate curves in absolute gain units: $h_{\text{db}} = 20 \log_{10}(\max(h_{\text{diff}}, 10^{-6}))$.

### 5.3 True Differential Circuit Deconvolution & Staging Integrity
1. **True Differential Deconvolution ($H_{\text{diff}} = H_{\text{target}} / H_{\text{source}}$):**
   - Never use ad-hoc identity bypass conditionals (`if is_identity: return 1.0`) in place of true deconvolution, and never treat active instruments as unvoiced generic EMGs. Define explicit source SPICE netlists in `circuits/sources/` for all active instruments with onboard preamps (StingRay 2-band, Dingwall FD3n) and link them in `config/instruments/*.toml`.
   - Directly evaluate model equality: $\text{if } \text{allclose}(H_{\text{tgt}}, H_{\text{src}}): H_{\text{diff}} \equiv 1.000$ ($0.00\text{ dB}$ identity across all frequencies).
   - In both `analyze_voices.py` and `simulate_circuits.py`, universally evaluate differential transfer functions whenever `src_cir_path` is present.
2. **Strict Prevention of Double Voicing:**
   - Automatically inspect input filenames: if `Path(input_wav).name.startswith("aperture_")`, automatically set `prefiltered = True` to guarantee `compute_voice_prefilter_firs` is never re-convolved.
   - When target voice declares a multi-channel circuit, evaluate branch FIRs with unity weighting ($p_{\text{weight}} = 1.0$), letting the SPICE nodal network evaluate physical current division without $-6\text{ dB}$ double-attenuation.

### 5.4 Differential Non-Linear Metallurgy, Magnetic Dynamics & Analog Realism
1. **Differential Magnetic Softening:** Never bypass saturation with blanket conditionals (`is_passive or has_source_circuit`). Evaluate differential metallurgy between source and target:
   $$\Delta\alpha = \max(\alpha_{\text{tgt}} - \alpha_{\text{src}}, 0), \quad \Delta\alpha_3 = \max(\alpha_{3,\text{tgt}} - \alpha_{3,\text{src}}, 0), \quad \Delta\eta_{\text{hyst}} = \max(\eta_{\text{tgt}} - \eta_{\text{src}}, 0), \quad \Delta k_{\text{sag}} = \max(k_{\text{sag,tgt}} - k_{\text{sag,src}}, 0)$$
   $$\Delta k_{\text{eddy}} = \max(k_{\text{eddy,tgt}} - k_{\text{eddy,src}}, 0), \quad \Delta\kappa_{\text{orbit}} = \max(\kappa_{\text{orbit,tgt}} - \kappa_{\text{orbit,src}}, 0), \quad \Delta\beta_{\text{curv}} = \max(\beta_{\text{curv,tgt}} - \beta_{\text{curv,src}}, 0)$$
   $$\Delta k_{\text{pull}} = \max(k_{\text{pull,tgt}} - k_{\text{pull,src}}, 0), \quad \Delta\tau_{\text{touch}} = \max(\tau_{\text{touch,tgt}} - \tau_{\text{touch,src}}, 0)$$
   $$V_{\text{sat,eff}} = \begin{cases} V_{\text{sat,tgt}} & \text{if active source} \\ \frac{V_{\text{sat,tgt}}}{1.0 - \min\left(0.85, \frac{V_{\text{sat,tgt}}}{V_{\text{sat,src}}}\right) + 0.15} & \text{if passive source with } V_{\text{sat,tgt}} < V_{\text{sat,src}} \\ 10.0 & \text{otherwise} \end{cases}$$
   Engage softening if and only if $(\text{not is\_identity}) \land (\text{not is\_passive} \lor \text{is\_target\_more\_saturated})$. Bypass saturation on small signals ($\le 0.10$ peak) to preserve bit-exact test linearity.
2. **Nonlinear Magnetic String Pull & Attack Pitch Sag ($k_{\text{pull}}$):** Evaluate dynamic pole pull damping and attack pitch sag in `_lenz_velocity_drag_core`:
   $$\text{pull\_damping} = k_{\text{pull}} \cdot \text{excess} \cdot \tanh\left(\frac{\max(x[n], 0)}{V_{\text{sat}}}\right), \quad \text{pitch\_sag} = -k_{\text{pull}} \cdot \text{excess} \cdot (x_{\text{high}}[n] - x_{\text{high}}[n-1])$$
   $$\text{drag}_{\text{high}} = 1.0 - (k_{\text{sag}} + k_{\text{eddy}} + \text{pull\_damping}) \cdot \text{excess}, \quad x_{\text{out}}[n] = \text{drag}_{\text{low}} x_{\text{low}}[n] + \text{drag}_{\text{high}} (x_{\text{high}}[n] + \text{wobble} + \text{pitch\_sag})$$
3. **Excursion-Dependent Dynamic Touch Spectral Tilt ($\tau_{\text{touch}}$):** In saturation stage, inject highpass attack harmonics modulated by displacement envelope:
   $$H_{\text{hp}}(s) = \frac{s}{s + 2\pi \cdot 400.0}, \quad \text{touch\_mod} = \tau_{\text{touch}} \cdot \tanh\left(\frac{|x_{\text{disp}}|}{V_{\text{sat}}}\right) \cdot x_{\text{disp,hp}}, \quad x_{\text{disp}} = x_{\text{disp}} + \text{touch\_mod}$$
4. **Dynamic Eddy De-Qing, Orbital Bloom & Inductance Curvature Wobble:**
   - Eddy current core de-Qing: $\text{eddy\_factor} = k_{\text{eddy}} \cdot \text{excess} \cdot \tanh(|x_{\text{high}}| / V_{\text{sat}})$.
   - 2D Elliptical string orbit bloom: $x_{\text{quad}} = x \cdot \mathcal{H}\{x\}$, $x_{\text{out}} = x + \Delta\kappa_{\text{orbit}} \cdot \tanh(|x| / V_{\text{sat}}) \cdot x_{\text{quad}}$ (zero DC bias $2f_0$ bloom).
   - Core inductance curvature wobble: $\text{wobble} = \beta_{\text{curv}} \cdot \tanh(x^2 / V_{\text{sat}}^2) \cdot (x_{\text{high}}[n] - x_{\text{high}}[n-1])$.
5. **Transient Magnetic Slew-Rate Limiting:** Bound domain-wall displacement delta via soft-knee saturation (`_slew_limit_core`):
   $$\Delta x_{\text{max}} = \frac{2\pi f_{\text{slew}} V_{\text{sat}}}{f_s}, \quad f_{\text{slew}} = 16000.0\text{ Hz}, \quad \Delta x_{\text{slew}}[n] = \Delta x_{\text{max}} \cdot \tanh\left(\frac{x[n] - x_{\text{slewed}}[n-1]}{\Delta x_{\text{max}}}\right)$$
6. **Thermal Dither & Body Coupling:**
   - Inject calibrated $-108\text{ dBFS}$ RLC-shaped Johnson noise dither to prevent hardware fixed-point neural gating pops (bypassed on small signals $\le 0.10$).
   - Model diffuse body microphonics on unpotted vintage passive pickups: $f_b = 6200.0\text{ Hz}, Q_b = 1.8, f_{\text{damp}} = 9500.0\text{ Hz}$.

### 4.5 Complex Electrical Impedance & Inter-Coil Transmission Modeling
1. **Fractional-Order Dielectric Absorption:** Model tone capacitor and cable admittance via Cole-Davidson fractional frequency scaling ($\alpha_{\text{tone}} \approx 0.988, \alpha_{\text{cable}} \approx 0.994, \omega_0 = 2\pi \cdot 1000\text{ rad/s}$):
   $$s_{\text{norm}} = \max\left(\frac{\omega}{\omega_0}, 10^{-6}\right), \quad Y_C(s) = s \cdot C \cdot s_{\text{norm}}^{\alpha - 1} \cdot e^{j(\alpha - 1)\pi / 2}$$
2. **Coupled $2\times 2$ Nodal Transfer Matrix:** For parallel dual-coil configurations, solve the coupled mutual system ($M = k_m \sqrt{L_n L_b}, Z_m = s M, Y_m = s C_m, \Delta_Z = Z_n Z_b - Z_m^2$):
   $$H_{n \to 2}(s) = \frac{Z_b - Z_m}{\Delta_Z(Y_{\text{eff}2} + Y_m) + Z_n + Z_b - 2 Z_m}, \quad H_{b \to 2}(s) = \frac{Z_n - Z_m}{\Delta_Z(Y_{\text{eff}2} + Y_m) + Z_n + Z_b - 2 Z_m}$$
3. **Complex Magnetic Permeability Dispersion ($\mu^*(\omega)$):** In `compute_core_impedance`, model causal Jordan core relaxation via logarithmic dispersion:
   $$\mu_{\text{rel}}(s) = 1.0 - \chi_{\mu} \ln\left(1.0 + \frac{s}{\omega_{\mu}}\right), \quad \omega_{\mu} = 2\pi \cdot 1200.0\text{ rad/s}, \quad Z_L(s) = \mu_{\text{rel}}(s) \cdot \left[s L_{\infty} + \frac{s L_{\text{core}} R_{\text{core}}}{s L_{\text{core}} + R_{\text{core}}}\right]$$
4. **Distributed Inter-Winding Transmission Line Admittance:** Replace lumped parallel coil admittance with the hyperbolic transmission factor ($k_{\text{dist}} \in [0.00, 0.05], \omega_{\text{dist}} = 2\pi \cdot 10000\text{ rad/s}$):
   $$\gamma_{\text{dist}} = k_{\text{dist}} \sqrt{\frac{s}{\omega_{\text{dist}}}}, \quad Y_{\text{coil}}(s) = (s C_{\text{coil}} + G_{\text{coil}}) \cdot \frac{\tanh(\gamma_{\text{dist}})}{\gamma_{\text{dist}}}$$

---

## 5. Architectural Guardrails: High-Performance Audio DSP & SIMD Engineering

To maintain the native Virtual Analog simulation engine's $>1500\times$ real-time speed, adhere to these three performance directives:

### 5.1 Buffer & Recurrence Execution Acceleration
- **No Interpreted Loops Over Audio Buffers:** Never write scalar Python loops (`for i in range(n)`) over audio buffers. Always accelerate recursive ODE state solvers (Lenz drag, Dahl hysteresis, slew limiting) using Numba JIT compilation (`@njit(fastmath=True)`) with graceful pure-Python fallback ($220\times$ speedup).
- **NumPy View Byte Packing:** Vectorize 24-bit little-endian WAV packing in C via NumPy view slicing (`scaled.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3].tobytes()`, $135\times$ speedup).
- **SIMD Circuit Transfer Evaluation:** Formulate all nodal impedances, admittances, and voltage divider ratios directly on complex NumPy frequency vectors ($s = 1j \cdot \omega$) rather than scalar loops ($12\times$ speedup).

### 5.2 Frequency-Domain Stage Fusion & Caching
- **Fuse Linear Stages in Frequency Domain:** Avoid redundant FFT/IRFFT round-trips. Apply displacement pre-filters ($X_{\text{up}} \cdot H_{\text{pre}}$) before inverse FFT, and combine de-emphasis ($H_{\text{de}} / \text{scale}$) and anti-aliasing lowpass ($aa\_mask$) into a single product before decimation.
- **Broadcast Input FFTs:** In multi-pickup instruments, precompute the mono input forward FFT once across all channels using `max_ir_len` and broadcast it across channel FIRs.
- **In-Memory Netlist LRU Caching:** Wrap SPICE netlist parsing with `@functools.lru_cache(maxsize=128)` and return shallow copies (`copy.copy(cached)`), eliminating redundant disk reads and regex tokenization.

### 5.3 Parallel Concurrency & Test Bounding
- **Multi-Process Concurrency:** Expose parallel process execution using `concurrent.futures.ProcessPoolExecutor` with `-j/--jobs` CLI flags (defaulting to `min(4, os.cpu_count())`), dropping 16-voice batch simulation from $7+\text{ minutes}$ to $80\text{ seconds}$.
- **Decouple Target vs Differential Curve Generation:** Precompute global target output voice master dataframe **once** globally. Compute source-to-target difference dataframes once per instrument, reducing dataframe builds by $73\%$.
- **Frame-Bounded Audio Processing (`max_samples`):** Support bounded frame prefixes (`max_samples = 4800` to `48000`) in unit tests to drop test execution from $22\text{s}$ down to $0.15\text{s}$ while preserving complete signal pipeline verification.



