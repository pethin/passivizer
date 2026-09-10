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

To ensure high-fidelity modeling and prevent regressions, all agents and contributors must adhere to these eight architectural rules when modifying the DSP, physics, and simulation pipelines:

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

### 5.8 Quadrature Regularization vs. Rectified-Cosine ($|\cos\theta|$) V-Cusps at Comb Nulls
- **Anti-Pattern:** Assuming 100% spatial coherence ($\gamma = 1.0$) down to mathematical zero in multi-coil humbuckers, evaluating magnitude as a pure rectified phasor sum $m = |\text{coil\_sum}| \propto |\cos(\pi f d / v)|$.
- **Why It Fails:** As a coherent phasor sum passes through zero at fundamental destructive interference ($f_{\text{null}} = \frac{v}{2d}$), the first derivative of $|\cos\theta|$ abruptly flips sign from $-1$ to $+1$. This generates a non-differentiable mathematical V-shaped cusp at the bottom of the notch. When evaluated across 4 discrete string wave speeds ($N=4$), this artifact produces 4 visible sharp inflection corners across the $1.8\text{--}4.5\text{ kHz}$ midrange.
- **Mandated Practice:** Account for finite 3D pole-piece flux fringing and string diameter using a quadrature regularized coherent floor ($\epsilon_{\text{quad}} \approx 0.18$):
  $$p_{\text{coh\_reg}} = p_{\text{coh}} + \epsilon_{\text{quad}}^2 \cdot p_{\text{incoh}}$$
  $$m_{\text{blend}} = \frac{\sqrt{\gamma \cdot p_{\text{coh\_reg}} + (1 - \gamma) p_{\text{incoh}}}}{\text{dc\_norm}}$$
### 5.9 Absolute Transfer Ratios vs. Mid-Band Reference Normalization in Differential Passive Modeling
- **Anti-Pattern:** Normalizing differential circuit transfer functions by dividing by an arbitrary mid-frequency bin like 1 kHz (`ref_gain = h_diff[1000 Hz]`) prior to applying soft-knee boost limiters.
- **Why It Fails:** In passive-to-passive digital twin modeling, passive circuits with tone rolloff capacitors (e.g. 22nF, 47nF, 100nF ToneStyler shunts) naturally have significant attenuation at 1 kHz (down -8.5 dB for 22nF, -16 dB for 47nF, and -23 dB for 100nF). Normalizing by `h_diff[1000 Hz]` forces 1 kHz to 0 dB, artificially projecting the natural low-frequency passband (20–500 Hz) into a massive false "boost" (+8.5 to +23 dB). A 6 dB soft-knee limiter will clamp the entire passband across all tone-rolled voicings down to a flat ceiling, forcing distinct capacitor values (e.g. 22nF vs 100nF) to start rolling off at the exact same frequency (~700 Hz) and rendering them indistinguishable.
- **Mandated Practice:** Evaluate differential circuit transfer curves in absolute gain units:
  $$h_{\text{db}} = 20 \log_{10}(\max(h_{\text{diff}}, 10^{-6}))$$
  Because passive circuits naturally have DC transfer gain $\le 1.0$ ($0.0\text{ dB}$), attenuation ($h_{\text{db}} \le 0$) remains strictly untouched everywhere. The soft-knee limiter and high-frequency cosine taper only engage when true positive boost ($h_{\text{db}} > \text{thresh}$) occurs at high frequencies or sharp resonant peaks, ensuring authentic physical rolloff cutoffs (750 Hz for 22nF, 450 Hz for 47nF, 240 Hz for 100nF) form cleanly and distinctly.

### 5.10 Strict Positive Threshold ($\Delta\text{samples} > 0$) for Inter-Pickup Spatial Coherence Decay
- **Anti-Pattern:** Using arbitrary non-zero sample delay thresholds like `delta_samples > 5` to gate acoustic inter-pickup spatial coherence decay.
- **Why It Fails:** At $f_s = 48\text{ kHz}$, 5 samples corresponds to $\Delta\tau = 0.104\text{ ms}$, which has a fundamental cancellation null at $f_{\text{notch}} = \frac{1}{2\Delta\tau} = 4.8\text{ kHz}$ and a secondary null at $14.4\text{ kHz}$. Pickups with tight spatial spacing (e.g. dual-blade soapbars or neck/bridge blend combinations) can have delays $\le 5$ samples. Skipping coherence decay when `delta_samples <= 5` falls into an unregularized raw coherent phasor sum ($2|\cos(\pi f \Delta\tau)|$), producing deep, unphysical mathematical comb notches plunging to $-35\text{ to } -40\text{ dB}$ in the musical clank region.
- **Mandated Practice:** Always trigger spatial coherence decay for any non-zero delay:
  $$\text{has\_spatial\_delay} = (\text{len}(\text{channels}) > 1 \text{ and } \Delta\text{samples} > 0)$$
  This guarantees that spatial coherence decay ($\gamma(f)$) smoothly transitions into incoherent power summation above $f_{\text{notch}}$, bounding the fundamental mid-scoop to an authentic physical depth (~$-12\text{ to } -15\text{ dB}$) and completely suppressing higher-order harmonic cancellation teeth.

### 5.11 True Differential Circuit Deconvolution vs. Ad-Hoc Identity Bypasses Across Active and Passive Datums
- **Anti-Pattern:** Using ad-hoc identity bypass conditionals (e.g. `if is_identity and not is_passive: circuit_curves = [ones]`) instead of genuine differential circuit deconvolution ($H_{\text{diff}} = H_{\text{target}} / H_{\text{source}}$), or treating all active instruments as unvoiced generic EMGs without explicit SPICE source netlists.
- **Why It Fails:** Commercial active instruments (e.g. 34" Active Music Man StingRay, 37" Multi-Scale Dingwall) possess distinct physical pickup coils and onboard active buffer/EQ circuits. Omitting their source circuit netlists (`source_active_stingray.cir`, `source_dingwall_fd3n.cir`) and patching identity matches with `if is_identity: return 1.0` leaves cross-instrument transformations completely broken: converting an active StingRay into a Vintage '62 P-Bass mistakenly cascades the P-Bass circuit *on top* of the StingRay's active 2-band preamp (+1.8 dB bass, +2.2 dB treble shelf) without deconvolving it! Furthermore, standard Wiener regularization quotients ($(H_{\text{tgt}} \cdot H_{\text{src}}) / (H_{\text{src}}^2 + \epsilon^2)$ with $\epsilon = 0.05$) crash to $-104\text{ dB}$ at DC when source models have subsonic highpass filters ($s \to 0$).
- **Mandated Practice:**
  1. Always define explicit SPICE source circuit netlists in `circuits/sources/` for commercial active instruments with onboard preamps/harnesses, linking them in `config/instruments/*.toml`.
  2. In `compute_differential_circuit_transfer_functions`, directly evaluate model equality:
     $$\text{if } \text{allclose}(H_{\text{tgt}}, H_{\text{src}}): \quad H_{\text{diff}} \equiv 1.000 \quad (0.00\text{ dB})$$
     guaranteeing mathematical identity across all frequencies without denominator or Wiener distortion.
  3. In both `analyze_voices.py` and `simulate_circuits.py`, universally evaluate differential transfer functions whenever `src_cir_path` is present:
     $$H_{\text{diff}} = \frac{H_{\text{target}}}{H_{\text{source}}}$$
     naturally deconvolving source pickup coils and onboard preamps on cross-instrument voicings, and achieving natural $0.00\text{ dB}$ identity on matching voices without ad-hoc bypass branches.
  4. Ensure all source instruments declare valid string presets existing in `config/strings.toml` (e.g. `roundwound_stainless_clank`).

---

## 6. Architectural Guardrails: High-Performance Audio DSP & SIMD Engineering

To maintain the native Virtual Analog simulation engine's $>1500\times$ real-time speed, all contributors must prevent the five performance anti-patterns resolved in commit `610dd93e`:

### 6.1 Never Run Interpreted Python Loops over Audio Sample Buffers (ODE / Recursive State Solvers)
- **Anti-Pattern:** Writing scalar `for i in range(1, n)` loops in standard Python to solve state-space recurrence equations (e.g. Dahl magnetic hysteresis, non-linear capacitor charge, or physical string models) over 48 kHz buffers ($4.5\text{M}$ samples for a 95-second sweep; $9.1\text{M}$ samples at 2x oversampling).
- **Why It Fails:** Interpreted CPython bytecode evaluation incurs massive function-call and pointer indirection overhead, taking $17.7\text{ seconds}$ per audio channel.
- **Mandated Practice:** Always accelerate recursive sample-by-sample ODE solvers using Numba JIT compilation (`@njit(fastmath=True)`) with an automatic, graceful pure-Python fallback when Numba is not installed. Achieves a **$220\times$ speedup** ($17.7\text{s} \to 0.08\text{s}$).

### 6.2 Fuse Consecutive Linear Stages in Frequency Domain (Avoid Redundant FFT/IRFFT Round-Trips)
- **Anti-Pattern:** Bouncing back and forth between time and frequency domains with separate `np.fft.rfft` and `np.fft.irfft` calls for each consecutive linear filter stage (e.g. forward FFT $\to$ displacement pre-filter $\to$ inverse FFT $\to$ non-linearity $\to$ forward FFT $\to$ de-emphasis filter $\to$ anti-aliasing filter $\to$ inverse FFT).
- **Why It Fails:** Multi-million-point FFT/IRFFT round-trips on $9.12\text{M}$-sample arrays waste gigabytes of memory bus bandwidth and evict CPU L2/L3 caches.
- **Mandated Practice:** Fuse consecutive linear operations in the frequency domain. Apply pre-filters directly to the spectrum ($X_{\text{up}} \cdot H_{\text{pre}}$) before a single inverse FFT, and combine de-emphasis ($H_{\text{de}} / \text{scale}$) and anti-aliasing lowpass ($aa\_mask$) into a single frequency-domain product before final decimation, eliminating 4 redundant multi-million-point FFT round-trips.

### 6.3 Precompute and Broadcast Input FFTs across Multi-Channel Filters
- **Anti-Pattern:** Calling `np.fft.rfft(input_mono, n_fft)` inside the channel loop for every pickup branch in `apply_prefilter_to_audio`.
- **Why It Fails:** In multi-pickup instruments (Jazz Bass pairs, P/J, P/MM), the exact same mono input sweep was being forward-transformed 2 to 4 times, duplicating heavy FFT operations.
- **Mandated Practice:** Precompute the forward FFT of `input_mono` once across all channels using the maximum impulse response length (`max_ir_len`), and broadcast it across the channel FIR convolutions.

### 6.4 Vectorize 24-Bit Little-Endian WAV Byte Packing via NumPy Views
- **Anti-Pattern:** Converting 24-bit audio buffers using Python loops and `int(val).to_bytes(3, byteorder="little")` appended to a `bytearray`.
- **Why It Fails:** Allocating and appending 4.5 million 3-byte slices in Python interpreter space takes $3.63\text{ seconds}$ per audio file.
- **Mandated Practice:** Vectorize 24-bit little-endian packing in C via NumPy view slicing:
  ```python
  scaled = np.clip(samples * 8388607.0, -8388608.0, 8388607.0).astype(np.int32)
  raw_bytes = scaled.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
  ```
  Yields a **$135\times$ speedup** ($3.63\text{s} \to 0.026\text{s}$) with zero Python loop overhead.

### 6.5 Multi-Process Concurrency for Batch Voice Simulation
- **Anti-Pattern:** Running batch simulations across all 16 target voices sequentially in a single Python thread.
- **Why It Fails:** Audio circuit simulation is CPU-bound and embarrassingly parallel. Single-threaded execution leaves multi-core CPUs (e.g. Apple Silicon M-series chips with 8–16 cores) mostly idle while users wait 7+ minutes for a batch run.
- **Mandated Practice:** Expose parallel process execution using `concurrent.futures.ProcessPoolExecutor` with `--jobs` / `-j` CLI flags (defaulting to `min(4, os.cpu_count())`). Drops full 16-voice batch simulation time from **$7+\text{ minutes}$ down to $80\text{ seconds}$**.

### 6.6 Vectorize Analytical Circuit Transfer Functions with NumPy SIMD ($s = j\omega$)
- **Anti-Pattern:** Evaluating analytical nodal AC equations (Foster 2-stage core ladders, tone shunt admittances, active preamp boost filters) with scalar point-by-point Python loops (`for f in freqs:`).
- **Why It Fails:** Iterating 500 to 1,000 frequency bins in pure Python evaluates millions of scalar mathematical operations and temporary object allocations, bottlenecking circuit curve evaluations ($184\text{ ms} \to 15\text{ ms}$ for 25 netlists; over 5.2 million calls to `compute_core_impedance` during full catalog analysis).
- **Mandated Practice:** Formulate all nodal impedances, admittances, and voltage divider ratios directly on complex NumPy frequency vectors ($s = 1j \cdot \omega$). Yields a **$12.2\times$ raw speedup** while maintaining bit-exact ($10^{-12}$) numerical precision.

### 6.7 In-Memory LRU Caching of SPICE Netlists and Circuit Models
- **Anti-Pattern:** Re-reading and re-parsing identical `.cir` text files from disk using regex on every voice evaluation or dataframe build.
- **Why It Fails:** Disk I/O and text tokenization repeated across 11 source instruments, 17 target voices, and multiple analysis modes generates hundreds of redundant disk operations and object constructions.
- **Mandated Practice:** Wrap SPICE netlist parsing with `@functools.lru_cache(maxsize=128)` and return defensive shallow copies (`copy.copy(cached)`). Guarantees zero disk reads on repeated queries while allowing callers to independently mutate core eddy diffusion parameters without cross-talk.

### 6.8 Decouple Invariant Target Voice Analysis from Source-Dependent Differential Curves
- **Anti-Pattern:** Re-evaluating target output voice curves (`mode="output"`) inside nested instrument loops.
- **Why It Fails:** Target voice responses (acoustic aperture sinc filters, loaded RLC circuit peaks, target string voicings) are completely independent of the source instrument. Recomputing them across $N_{\text{inst}}$ instruments in both output and unified modes incurs $2 N_{\text{inst}} \times N_{\text{voices}}$ redundant evaluations (374 redundant dataframe builds across 11 instruments).
- **Mandated Practice:** Precompute the global target output voice master dataframe **once** globally. Compute the source-to-target difference dataframes **once** per instrument, and synthesize unified multi-mode visualizations by combining them in memory with `pl.lit(...).alias("mode")`. Reduces dataframe builds by **73%** ($748 \to 204$).

### 6.9 Frame-Bounded Audio Processing (`max_samples`) for Unit Tests and Previews
- **Anti-Pattern:** Processing the full 95-second 48 kHz calibration sweep ($4.56\text{M}$ samples; $9.12\text{M}$ at 2x oversampling) in unit tests that only verify sweep auto-detection, fallback handling, or RMS level normalization.
- **Why It Fails:** Running 7 full 95-second simulations in the test suite wastes over 21 seconds executing millions of ODE state solver steps and large FFTs on identical sweep frames.
- **Mandated Practice:** Support bounded frame processing via `max_samples: int = None` in `simulate_circuit_audio` and `simulate_voice`. Use bounded prefixes (e.g. 4,800 samples = 0.1s for auto-detection; 48,000 samples = 1.0s with active signal for RMS/peak normalization) in unit tests, dropping test execution from **$21.8\text{s}$ down to $0.15\text{s}$** (~$145\times$ speedup) without sacrificing end-to-end signal pipeline verification.



