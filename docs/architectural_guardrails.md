# Passivizer - Architectural Guardrails & Mathematical Modeling Handbook

This document provides the definitive mathematical specifications, physical equations, circuit theorems, and numerical derivations underlying the Passivizer modeling pipeline. It serves as the primary technical reference companion to `AGENTS.md`.

---

## Maintenance & Compaction Architecture

To preserve fast agent reasoning and prevent LLM context exhaustion, Passivizer maintains a strict two-tier architecture:
1. **`AGENTS.md` (Normative Core):** Contains only high-level rules, negative constraints ("Never do X"), and boundary conditions kept under **$18\text{ KB}$**.
2. **`docs/architectural_guardrails.md` (Unabridged Handbook):** Contains all extensive LaTeX equations, matrix derivations, parameter mappings, and physics proofs.
3. **`tests/test_guardrails.py` (Executable Invariants):** Programmatically enforces all rules on every test run.

When adding new modeling features, write the mathematical derivations into this document, declare the rule in `AGENTS.md`, and add an invariant check to `tests/test_guardrails.py`.

---

## 1. Spatial Acoustics, Scale Physics & Tuning/Gauge Invariance

### 1.1 Dynamic Comb & De-Combing Boundaries
Never hardcode static cutoff frequencies for wave/delay phenomena. Derive spatial transition boundaries dynamically from actual impulse peak delays or physical pickup datums:
$$f_{\text{notch}} = \frac{1}{2\Delta\tau} = \frac{f_s}{2 \cdot \Delta\text{peaks}}, \quad f_{\text{start}} = f_{\text{notch}}, \quad f_{\text{end}} = 1.7 \cdot f_{\text{notch}}$$
$$f_{\text{peak, src}} = \frac{\bar{c}}{x_{\text{src}}}, \quad f_{\text{taper\_start}} = \min(f_{\text{peak, src}}, 2500\text{ Hz}), \quad f_{\text{taper\_end}} = \min(1.8 f_{\text{taper\_start}}, 4500\text{ Hz})$$

### 1.2 Wavelength-Dependent Coherence Decay ($\lambda \le d$)
Evaluate humbucker cross-coherence decay dynamically per string/continuum wave speed $v$ based on acoustic wavelength $\lambda = v/f$ relative to coil spacing $d$:
$$f_{\text{start}} = \frac{v}{d}, \quad f_{\text{end}} = 1.8 \cdot \frac{v}{d}, \quad \gamma(f, v) = \frac{1}{2}\left[1 + \cos\left(\pi \cdot \text{clip}\left(\frac{f - f_{\text{start}}}{f_{\text{end}} - f_{\text{start}}}, 0, 1\right)\right)\right]$$
The transition begins right after the constructive peak ($f_{\text{start}}$), smoothly blending into incoherent power summation. Always engage coherence decay for any non-zero sample delay:
$$\text{has\_spatial\_delay} = (\text{len}(\text{channels}) > 1 \land \Delta\text{samples} > 0)$$

### 1.3 Spatial Arrival Delays & Causal Sample Shifting
When synthesizing multi-pickup branch FIR filters with spatial propagation delay differences ($\tau_i = \Delta x_i / \bar{c}$), apply delays strictly via causal discrete sample shifting:
$$\text{delay\_samples} = \lfloor \tau_i \cdot f_s + 0.5 \rfloor, \quad \text{fir} = [0]^{\text{delay\_samples}} + \text{fir}[:N - \text{delay\_samples}]$$
Never implement fractional arrival delays on causal minimum-phase FIR filters via circular FFT phase rotation ($H(f) \cdot e^{-j 2\pi f \tau_i}$). Because the minimum-phase impulse response peak is concentrated at tap 0, continuous-time sinc interpolation wraps the negative-time non-causal sinc tail around to the end of the circular buffer. Slicing the buffer back to $N$ taps discards this wrapped tail, convolving the frequency spectrum with a Dirichlet kernel and injecting artificial periodic Gibbs truncation ripples ($\Delta f = 1/\tau_i$) across the high frequencies ($8\text{--}20\text{ kHz}$).

### 1.4 Sidewinder Architecture
If coils feed a single central row of pole pieces under the string ($\Delta x = 0$, e.g. Gibson EB Mudbucker), configure a single coil entry with effective center position ($x = x_{\text{center}}$) and expanded aperture width ($w \approx 1.25''$), never a multi-coil spaced array.

### 1.5 Scale-Normalized Fractional Coordinates ($\eta = x / L$)
Never subtract raw millimeters across different scale lengths. Calculate displacement using fractional coordinates normalized to standard 34" equivalent inches:
$$\eta_{\text{tgt}} = \frac{x_{\text{tgt}}}{L_{\text{tgt}}}, \quad \eta_{\text{src}} = \frac{x_{\text{src}}}{L_{\text{src}}}, \quad \Delta x_{\text{in}} = (\eta_{\text{tgt}} - \eta_{\text{src}}) \times 34.0''$$

### 1.6 Dynamic Target Scale Resolution & Tension Snap
Dynamically resolve effective target scale length ($L_{\text{tgt}} = 37.0''$ for multiscale, $34.0''$ otherwise) and apply proportional tension snap whenever $L_{\text{src}} < L_{\text{tgt}}$:
$$\text{snap\_db} = \min\left(3.5\text{ dB}, 1.8 \cdot \frac{L_{\text{tgt}} - L_{\text{src}}}{4.0''}\right)$$

### 1.7 Continuous Wave-Speed Continuum ($f_0 \in [30.87, 100]\text{ Hz}$)
Never constrain acoustic spatial filtering to 4 discrete open-string wave speeds or note-name strings (`["E", "A"]`). Integrate acoustic aperture responses ($H_{\text{composite}}$) across a continuous, log-spaced distribution ($N \ge 24$ points, uniform $1/N$ weight) spanning Low B ($30.87\text{ Hz}$) to open G ($100.00\text{ Hz}$). Route continuum points geometrically via register halves (`[1, 2]` treble vs `[3, 4]` bass), never note names. On multi-scale instruments (e.g. 34"-37" Dingwall NG, 32"-35" Dingwall SP1), vibrating string length $L(f_0)$ smoothly interpolates logarithmically from $L_{\text{max}}$ at Low B ($30.87\text{ Hz}$) down to $L_{\text{min}}$ at High G ($100.0\text{ Hz}$):
$$t(f_0) = \frac{\log_2(f_0) - \log_2(f_{\text{min}})}{\log_2(f_{\text{max}}) - \log_2(f_{\text{min}})}, \quad L(f_0) = L_{\text{max}} - t(f_0) \cdot (L_{\text{max}} - L_{\text{min}}), \quad v_0(f_0) = 2 \cdot L(f_0) \cdot f_0$$
Derive string stiffness $B_s(f_0)$ logarithmically and calculate mean propagation delay using register centroid $\bar{f}_0 = 66.9045\text{ Hz}$ ($\bar{c} = 2 \bar{L} \bar{f}_0$).

### 1.8 Longitudinal Wave Transmission & Core Percussion ($H_{\text{long}}(f)$)
Plucking an electric bass string excites longitudinal compression waves propagating through the steel core wire ($c_L \approx 5100\text{ m/s}$), producing a distinct resonant clank at $f_L = c_L / (2L) \approx 2.7\text{--}3.3\text{ kHz}$. When target voicing string has higher longitudinal coupling than source ($\Delta k_{\text{long}} = \max(k_{\text{long,tgt}} - k_{\text{long,src}}, 0) > 0$):
$$H_{\text{long}}(f) = 1.0 + \Delta k_{\text{long}} \cdot \frac{f / f_L}{Q_L \sqrt{(1 - (f/f_L)^2)^2 + (f / (Q_L f_L))^2}} \cdot e^{-(f/6000.0)^2}, \quad Q_L = 8.0$$
Returns exact $1.0000$ ($0.00\text{ dB}$) when source matches target.

### 1.9 Cylindrical Rod vs Blade 2D Sensing Aperture
Differentiate magnetic pole geometry across sensing coils:
- **Cylindrical Rod Poles (Vintage Jazz/P, Music Man):** Evaluates 2D circular Airy/Bessel spatial sensitivity ($r_p = w_m / 2$):
  $$\text{ap\_cyl}(f, v) = \frac{1}{\sqrt{1 + 0.25 \cdot \left(\frac{2\pi r_p f}{v}\right)^2}}$$
- **Blade / Slit Sensors (Active EMG, Dual-Rails):** Evaluates 1D rectangular integration of width $w_m$:
  $$\text{ap\_blade}(f, v) = \frac{1}{\sqrt{1 + \frac{1}{3} \cdot \left(\frac{\pi w_m f}{v}\right)^2}}$$
Both formulations evaluate to exact $1.0000$ at DC ($f=0$) and exact $0.00\text{ dB}$ identity matching.

### 1.10 Bridge Saddle Witness-Point Boundary Layer Stiffness ($H_{\text{saddle}}$)
Bass strings have finite flexural bending stiffness ($E I$), creating an exponential boundary layer ($l_b \approx \sqrt{B_s} \cdot L \approx 2.0\text{--}3.5\text{ mm}$) at the saddle witness point. For pickups situated close to the bridge ($x < 0.075\text{ m}$):
$$f_{\text{saddle}}(x) = 7200.0 \cdot \left(\frac{x}{0.075\text{ m}}\right) + 1200.0\text{ Hz}, \quad H_{\text{saddle}}(f, x) = \frac{1}{\sqrt{1 + (f / f_{\text{saddle}}(x))^2}}$$
Evaluated differentially ($H_{\text{saddle,tgt}} / H_{\text{saddle,src}}$). Evaluates to exact $1.0000$ ($0.00\text{ dB}$) when $x \ge 0.075\text{ m}$ or on identity matching, gently rolling off brittle ultra-high-frequency artifacts ($> 7\text{ kHz}$) on close-bridge pickups without dulling mid growl.

---

## 2. Mathematical Smoothness, Regularization & Boundary Continuity ($C^1 / C^\infty$)

### 2.1 Regularized Denominators & Soft-Knee Saturation
Never clamp transfer ratio denominators with premature floors (e.g. `np.maximum(mag, 0.05)`) or apply hard rectangular clipping (`np.clip(..., 0.15, 3.0)`). Use regularized denominators ($\max(\text{mag}, 10^{-6})$) so identical profiles evaluate to exact $1.0000$ ($0.00\text{ dB}$). Bound maximum boosts and damping using asymptotic bidirectional soft-knee saturation:
$$r_{\text{db}} = 20 \log_{10}(\text{ratio}), \quad r_{\text{soft\_db}} = g \cdot \tanh\left(\frac{r_{\text{db}}}{g}\right)$$

### 2.2 Smooth $C^\infty$ Transition Across $0\text{ dB}$ Threshold
Never use piecewise conditionals (`np.where(h > 0, h * s, h)`) which create first-derivative slope kinks at $0\text{ dB}$. Use smooth softplus blending:
$$\text{excess\_boost} = \frac{1}{\beta} \ln\left(1 + e^{\beta \cdot h_{\text{db\_soft}}}\right) = \frac{1}{\beta} \text{logaddexp}\left(0, \beta \cdot h_{\text{db\_soft}}\right), \quad \beta = 1.2$$
$$h_{\text{db\_final}} = h_{\text{db\_soft}} - (1.0 - s) \cdot \text{excess\_boost}$$

### 2.3 Quadrature Regularization Floor at Comb Nulls
Never evaluate multi-coil humbucker cancellation as a raw rectified phasor sum ($|\cos(\pi f d / v)|$), which creates non-differentiable V-shaped cusps at nulls. Account for 3D flux fringing with a quadrature regularized floor ($\epsilon_{\text{quad}} \approx 0.18$):
$$p_{\text{coh\_reg}} = p_{\text{coh}} + \epsilon_{\text{quad}}^2 \cdot p_{\text{incoh}}, \quad m_{\text{blend}} = \frac{\sqrt{\gamma \cdot p_{\text{coh\_reg}} + (1 - \gamma) p_{\text{incoh}}}}{\text{dc\_norm}}$$

### 2.4 Absolute Transfer Ratios (No Mid-Band Reference Normalization)
Never normalize differential circuit curves by dividing by an arbitrary mid-frequency bin like 1 kHz (`h_diff / h_diff[1 kHz]`). Passive circuits naturally attenuate high frequencies; mid-band normalization artificially projects attenuation into false low-frequency boost, clamping tone-rolled profiles. Evaluate curves in absolute gain units:
$$h_{\text{db}} = 20 \log_{10}\left(\max(h_{\text{diff}}, 10^{-6})\right)$$

---

## 3. True Differential Circuit Deconvolution & Staging Integrity

### 3.1 True Differential Deconvolution ($H_{\text{diff}} = H_{\text{target}} / H_{\text{source}}$)
- Never use ad-hoc identity bypass conditionals (`if is_identity: return 1.0`) in place of true deconvolution, and never treat active instruments as unvoiced generic EMGs. Define explicit source SPICE netlists in `circuits/sources/` for all active instruments with onboard preamps (StingRay 2-band, Dingwall FD3n) and link them in `config/instruments/*.toml`.
- Directly evaluate model equality: $\text{if } \text{allclose}(H_{\text{tgt}}, H_{\text{src}}): H_{\text{diff}} \equiv 1.000$ ($0.00\text{ dB}$ identity across all frequencies).
- In both `analyze_voices.py` and `simulate_circuits.py`, universally evaluate differential transfer functions whenever `src_cir_path` is present.

### 3.2 Strict Prevention of Double Voicing
- Automatically inspect input filenames: if `Path(input_wav).name.startswith("aperture_")`, automatically set `prefiltered = True` to guarantee `compute_voice_prefilter_firs` is never re-convolved.
- When target voice declares a multi-channel circuit, evaluate branch FIRs with unity weighting ($p_{\text{weight}} = 1.0$), letting the SPICE nodal network evaluate physical current division without $-6\text{ dB}$ double-attenuation.

### 3.3 Sub-Audible DC Decoupling & Gibbs Truncation Ripple Prevention
- Active bass preamps feature DC-blocking capacitors ($10\text{--}47\ \mu\text{F}$) solely for power rail DC offset isolation. Never include sub-audible AC-coupling differentiator poles ($s / (s + \omega_{\text{sub}})$ where $\omega_{\text{sub}} \le 2\pi \cdot 20\text{ rad/s}$) in active preamp transfer functions (`compute_active_preamp_eq`).
- Forcing $H_{\text{source}}(s) \to 0$ as $s \to 0$ causes differential deconvolution against passive targets ($H_{\text{target}}(0) > 0$) to synthesize an unphysical $>30\text{ dB}$ sub-audible inversion step ($0\text{--}5.86\text{ Hz}$, $T > 170\text{ ms}$).
- In finite-tap minimum-phase FIR synthesis ($N = 2048$, duration $42.6\text{ ms}$ at $48\text{ kHz}$), truncating such long-period waves truncates the impulse response mid-cycle, convolving the spectrum with a Dirichlet kernel and generating periodic Gibbs truncation ripples:
  $$\Delta f = \frac{f_s}{N} = \frac{48000\text{ Hz}}{2048} = 23.4375\text{ Hz}$$
  across $20\text{--}300\text{ Hz}$.
- Active preamp models must strictly represent musical shelving contours ($H_{\text{bass}} \cdot H_{\text{treble}}$) with flat, finite DC transmission ($H_{\text{preamp}}(0) \ge 1.0$), ensuring smooth, ripple-free differential curves down to $20\text{ Hz}$.

---

## 4. Differential Non-Linear Metallurgy, Magnetic Dynamics & Analog Realism

### 4.1 Differential Magnetic Softening
Never bypass saturation with blanket conditionals (`is_passive or has_source_circuit`). Evaluate differential metallurgy between source and target:
$$\Delta\alpha = \max(\alpha_{\text{tgt}} - \alpha_{\text{src}}, 0), \quad \Delta\alpha_3 = \max(\alpha_{3,\text{tgt}} - \alpha_{3,\text{src}}, 0), \quad \Delta\eta_{\text{hyst}} = \max(\eta_{\text{tgt}} - \eta_{\text{src}}, 0), \quad \Delta k_{\text{sag}} = \max(k_{\text{sag,tgt}} - k_{\text{sag,src}}, 0)$$
$$\Delta k_{\text{eddy}} = \max(k_{\text{eddy,tgt}} - k_{\text{eddy,src}}, 0), \quad \Delta\kappa_{\text{orbit}} = \max(\kappa_{\text{orbit,tgt}} - \kappa_{\text{orbit,src}}, 0), \quad \Delta\beta_{\text{curv}} = \max(\beta_{\text{curv,tgt}} - \beta_{\text{curv,src}}, 0)$$
$$\Delta k_{\text{pull}} = \max(k_{\text{pull,tgt}} - k_{\text{pull,src}}, 0), \quad \Delta\tau_{\text{touch}} = \max(\tau_{\text{touch,tgt}} - \tau_{\text{touch,src}}, 0), \quad \Delta\kappa_{\text{geom}} = \max(\kappa_{\text{geom,tgt}} - \kappa_{\text{geom,src}}, 0), \quad \Delta k_{\text{stein}} = \max(k_{\text{stein,tgt}} - k_{\text{stein,src}}, 0)$$

$$V_{\text{sat,eff}} = \begin{cases} V_{\text{sat,tgt}} & \text{if active source} \\ \frac{V_{\text{sat,tgt}}}{1.0 - \min\left(0.85, \frac{V_{\text{sat,tgt}}}{V_{\text{sat,src}}}\right) + 0.15} & \text{if passive source with } V_{\text{sat,tgt}} < V_{\text{sat,src}} \\ 10.0 & \text{otherwise} \end{cases}$$
Engage softening if and only if $(\text{not is\_identity}) \land (\text{not is\_passive} \lor \text{is\_target\_more\_saturated})$. Bypass saturation on small signals ($\le 0.10$ peak) to preserve bit-exact test linearity.

### 4.2 Nonlinear Magnetic String Pull & Attack Pitch Sag ($k_{\text{pull}}$)
Evaluate dynamic pole pull damping and attack pitch sag in `_lenz_velocity_drag_core`, dynamically weighted by register excursion ratio:
$$w_{\text{reg}} = 0.70 + 0.60 \cdot \frac{|x_{\text{low}}[n]|}{\max(|x_{\text{low}}[n]| + |x_{\text{high}}[n]|, 10^{-6})}$$
$$\text{pull\_damping} = k_{\text{pull}} \cdot w_{\text{reg}} \cdot \text{excess} \cdot \tanh\left(\frac{\max(x[n], 0)}{V_{\text{sat}}}\right), \quad \text{pitch\_sag} = -k_{\text{pull}} \cdot w_{\text{reg}} \cdot \text{excess} \cdot (x_{\text{high}}[n] - x_{\text{high}}[n-1])$$
$$\text{drag}_{\text{high}} = 1.0 - (k_{\text{sag}} + k_{\text{eddy}} + \text{pull\_damping} + \text{stein\_damping}) \cdot \text{excess}$$
$$x_{\text{out}}[n] = \text{drag}_{\text{low}} x_{\text{low}}[n] + \text{drag}_{\text{high}} (x_{\text{high}}[n] + \text{wobble} + \text{pitch\_sag})$$
Thick lower strings ($f_0 \le 60\text{ Hz}$) experience up to $1.3\times$ pull damping and transient pitch sag, capturing authentic Alnico pole drag without choking high-register sustain ($0.7\times$).

### 4.3 Excursion-Dependent Dynamic Touch Spectral Tilt ($\tau_{\text{touch}}$)
In saturation stage, inject highpass attack harmonics modulated by displacement envelope:
$$H_{\text{hp}}(s) = \frac{s}{s + 2\pi \cdot 400.0}, \quad \text{touch\_mod} = \tau_{\text{touch}} \cdot \tanh\left(\frac{|x_{\text{disp}}|}{V_{\text{sat}}}\right) \cdot x_{\text{disp,hp}}, \quad x_{\text{disp}} = x_{\text{disp}} + \text{touch\_mod}$$

### 4.4 Dynamic Eddy De-Qing, Orbital Bloom & Inductance Curvature Wobble
- **Eddy current core de-Qing:** $\text{eddy\_factor} = k_{\text{eddy}} \cdot \text{excess} \cdot \tanh(|x_{\text{high}}| / V_{\text{sat}})$.
- **2D Elliptical string orbit bloom:** $x_{\text{quad}} = x \cdot \mathcal{H}\{x\}$, $x_{\text{out}} = x + \Delta\kappa_{\text{orbit}} \cdot \tanh(|x| / V_{\text{sat}}) \cdot x_{\text{quad}}$ (zero DC bias $2f_0$ bloom).
- **Core inductance curvature wobble:** $\text{wobble} = \beta_{\text{curv}} \cdot \tanh(x^2 / V_{\text{sat}}^2) \cdot (x_{\text{high}}[n] - x_{\text{high}}[n-1])$.

### 4.5 Transient Magnetic Slew-Rate Limiting
Bound domain-wall displacement delta via soft-knee saturation (`_slew_limit_core`):
$$\Delta x_{\text{max}} = \frac{2\pi f_{\text{slew}} V_{\text{sat}}}{f_s}, \quad f_{\text{slew}} = 16000.0\text{ Hz}, \quad \Delta x_{\text{slew}}[n] = \Delta x_{\text{max}} \cdot \tanh\left(\frac{x[n] - x_{\text{slewed}}[n-1]}{\Delta x_{\text{max}}}\right)$$

### 4.6 Thermal Dither & Body Coupling
- Inject calibrated $-108\text{ dBFS}$ RLC-shaped Johnson noise dither to prevent hardware fixed-point neural gating pops (bypassed on small signals $\le 0.10$).
- Model diffuse body microphonics on unpotted vintage passive pickups: $f_b = 6200.0\text{ Hz}, Q_b = 1.8, f_{\text{damp}} = 9500.0\text{ Hz}$.

### 4.7 Conformal Geometric Clearance & Dynamic Steinmetz AC Core Loss
- **Conformal clearance divergence:** $x_{\text{disp}} / (1 - \kappa_{\text{geom}} \tanh(x_{\text{disp}} / V_{\text{sat}}))$ modeling pole proximity growl and pushback without negative rail clipping.
- **Dynamic Steinmetz core loss:** $\text{stein\_damping} = k_{\text{stein}} \cdot \text{excess} \cdot (|dx_{\text{high}}/dt| / V_{\text{sat}})^{0.6}$ softening harsh flux spikes on attack plucks.

---

## 5. Complex Electrical Impedance & Inter-Coil Transmission Modeling

### 5.1 Fractional-Order Dielectric Absorption
Model tone capacitor and cable admittance via Cole-Davidson fractional frequency scaling ($\alpha_{\text{tone}} \approx 0.988, \alpha_{\text{cable}} \approx 0.994, \omega_0 = 2\pi \cdot 1000\text{ rad/s}$):
$$s_{\text{norm}} = \max\left(\frac{\omega}{\omega_0}, 10^{-6}\right), \quad Y_C(s) = s \cdot C \cdot s_{\text{norm}}^{\alpha - 1} \cdot e^{j(\alpha - 1)\pi / 2}$$

### 5.2 Coupled $2\times 2$ Nodal Transfer Matrix
For parallel dual-coil configurations, solve the coupled mutual system ($M = k_m \sqrt{L_n L_b}, Z_m = s M, Y_m = s C_m, \Delta_Z = Z_n Z_b - Z_m^2$):
$$H_{n \to 2}(s) = \frac{Z_b - Z_m}{\Delta_Z(Y_{\text{eff}2} + Y_m) + Z_n + Z_b - 2 Z_m}, \quad H_{b \to 2}(s) = \frac{Z_n - Z_m}{\Delta_Z(Y_{\text{eff}2} + Y_m) + Z_n + Z_b - 2 Z_m}$$

### 5.3 Complex Magnetic Permeability Dispersion ($\mu^*(\omega)$)
In `compute_core_impedance`, model causal Jordan core relaxation via logarithmic dispersion:
$$\mu_{\text{rel}}(s) = 1.0 - \chi_{\mu} \ln\left(1.0 + \frac{s}{\omega_{\mu}}\right), \quad \omega_{\mu} = 2\pi \cdot 1200.0\text{ rad/s}, \quad Z_L(s) = \mu_{\text{rel}}(s) \cdot \left[s L_{\infty} + \frac{s L_{\text{core}} R_{\text{core}}}{s L_{\text{core}} + R_{\text{core}}}\right]$$

### 5.4 Distributed Inter-Winding Transmission Line Admittance
Replace lumped parallel coil admittance with the hyperbolic transmission factor ($k_{\text{dist}} \in [0.00, 0.05], \omega_{\text{dist}} = 2\pi \cdot 10000\text{ rad/s}$):
$$\gamma_{\text{dist}} = k_{\text{dist}} \sqrt{\frac{s}{\omega_{\text{dist}}}}, \quad Y_{\text{coil}}(s) = (s C_{\text{coil}} + G_{\text{coil}}) \cdot \frac{\tanh(\gamma_{\text{dist}})}{\gamma_{\text{dist}}}$$

### 5.5 Interactive Potentiometer Wiper Division & Cable Loading
Model Volume and Tone pot wiper positions ($P_{\text{vol}}, P_{\text{tone}} \in [0, 1]$). Rolling volume down splits $R_{\text{vol}}$ into series $R_{\text{top}}$ and shunt $R_{\text{bot}}$, interacting with cable capacitance $C_{\text{cable}}$; rolling tone down reduces series resistance into $C_{\text{tone}}$. Exactly preserves netlist defaults when $P_{\text{vol}} = 1.0, P_{\text{tone}} = 1.0$.

---

## 6. High-Performance Audio DSP & SIMD Directives

### 6.1 Buffer & Recurrence Execution Acceleration
- **No Interpreted Loops Over Audio Buffers:** Never write scalar Python loops (`for i in range(n)`) over audio buffers. Always accelerate recursive ODE state solvers (Lenz drag, Dahl hysteresis, slew limiting) using Numba JIT compilation (`@njit(fastmath=True)`) with graceful pure-Python fallback ($220\times$ speedup).
- **NumPy View Byte Packing:** Vectorize 24-bit little-endian WAV packing in C via NumPy view slicing (`scaled.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3].tobytes()`, $135\times$ speedup).
- **SIMD Circuit Transfer Evaluation:** Formulate all nodal impedances, admittances, and voltage divider ratios directly on complex NumPy frequency vectors ($s = 1j \cdot \omega$) rather than scalar loops ($12\times$ speedup).

### 6.2 Frequency-Domain Stage Fusion & Caching
- **Fuse Linear Stages in Frequency Domain:** Avoid redundant FFT/IRFFT round-trips. Apply displacement pre-filters ($X_{\text{up}} \cdot H_{\text{pre}}$) before inverse FFT, and combine de-emphasis ($H_{\text{de}} / \text{scale}$) and anti-aliasing lowpass ($aa\_mask$) into a single product before decimation.
- **Broadcast Input FFTs:** In multi-pickup instruments, precompute the mono input forward FFT once across all channels using `max_ir_len` and broadcast it across channel FIRs.
- **In-Memory Netlist LRU Caching:** Wrap SPICE netlist parsing with `@functools.lru_cache(maxsize=128)` and return shallow copies (`copy.copy(cached)`), eliminating redundant disk reads and regex tokenization.

### 6.3 Parallel Concurrency & Test Bounding
- **Multi-Process Concurrency:** Expose parallel process execution using `concurrent.futures.ProcessPoolExecutor` with `-j/--jobs` CLI flags (defaulting to `min(4, os.cpu_count())`), dropping 16-voice batch simulation from $7+\text{ minutes}$ to $80\text{ seconds}$.
- **Decouple Target vs Differential Curve Generation:** Precompute global target output voice master dataframe once globally. Compute source-to-target difference dataframes once per instrument, reducing dataframe builds by $73\%$.
- **Frame-Bounded Audio Processing (`max_samples`):** Support bounded frame prefixes (`max_samples = 4800` to `48000`) in unit tests to drop test execution from $22\text{s}$ down to $0.15\text{s}$ while preserving complete signal pipeline verification.
