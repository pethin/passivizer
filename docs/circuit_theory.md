# Circuit Theory & Electrical Modeling

This document details the electrical equations, component parameters, and physical phenomena modeled in **Passivizer** to recreate authentic passive bass pickups and vintage/modern active preamps from active EMG X-Series signals.

---

## 1. The Passive Pickup Equivalent Network

A passive magnetic pickup is not merely a voltage source; it is a complex, high-impedance RLC resonant transducer. The standard linear equivalent circuit consists of:

$$V_{\text{out}}(s) = V_{\text{ind}}(s) \cdot H_{\text{elec}}(s)$$

Where:
* $V_{\text{ind}}$ is the voltage induced across the coils by the vibrating string ($V_{\text{ind}} \propto \frac{d\Phi}{dt}$).
* $H_{\text{elec}}(s)$ is the transfer function of the pickup loaded by the guitar's internal circuitry, cable, and amplifier.

```
                  ┌───────── R_eddy ────────┐
                  │                         │
[V_ind] ───[ L_coil ]───[ R_dc ]──┬─────────┴───┬─── [Lug 3: Volume In]
                                  │             │
                              [ C_coil ]    [ C-Switch ]
                                  │             │
                                 GND           GND
```

### Key Parameters:

1. **Coil Inductance ($L_{\text{coil}}$):**
   * Typically $1.6\text{ to }14.4\text{ Henries}$ for bass pickups.
   * Directly governs the frequency of the resonant peak ($f_r$). Higher inductance shifts the peak down into the low-mids.
   * Series wiring quadruples inductance relative to single coils ($L_{\text{ser}} \approx 4 \times L_{\text{single}}$), while parallel wiring halves it ($L_{\text{par}} \approx \frac{1}{2} L_{\text{single}}$).

2. **DC Resistance ($R_{\text{dc}}$):**
   * Resistance of thousands of turns of AWG 42 or 43 copper wire (typically $3.6\text{ k}\Omega\text{ to }28\text{ k}\Omega$).
   * Determines the baseline damping of the circuit and limits the maximum quality factor ($Q$).

3. **Inter-Winding Self-Capacitance ($C_{\text{coil}}$):**
   * Stray capacitance between adjacent coil turns, typically $50\text{ to }150\text{ pF}$.
   * Minor compared to cable capacitance in passive circuits, but sets the upper ceiling for unloaded resonance and active buffer isolation.

4. **Core Losses & Eddy Currents ($R_{\text{eddy}}$):**
   * Moving magnetic fields induce circular eddy currents in conductive pole pieces, steel baseplates, and magnets.
   * Modeled as a parallel resistance ($R_{\text{eddy}} \approx 60\text{ k}\Omega\text{ to }250\text{ k}\Omega$) across the coil.
   * This creates frequency-dependent damping: upper harmonics roll off more smoothly than an ideal 2nd-order filter, eliminating harsh, synthetic high-end resonance.

5. **Dynamic Core Compliance & String Excursion Saturation ($B_{\text{comp}}$):**
   * High-amplitude pick and slap transients push magnetic string coupling into non-linear excursion ($d\Phi/dx$).
   * Modeled in SPICE via an arbitrary behavioral voltage source:
     $$V_{\text{dyn}}(t) = V_{\text{sat}} \cdot \tanh\left(\frac{V(t)}{V_{\text{sat}}}\right)$$
   * For light to medium playing ($< 0.2\text{V}$), the response is $98\text{--}100\%$ linear.
   * On heavy pluck spikes ($> 0.4\text{V}$), the smooth $\tanh$ function provides $1.5\text{--}2.5\text{ dB}$ of analog soft-knee saturation, capturing authentic passive pickup compression and touch-sensitive dynamic give.

---

## 2. Onboard Control Harnesses & Loading Topologies

Passivizer does not assume a generic volume/tone harness for all instruments. Each voice utilizes its authentic manufacturer and era-specific harness:

### A. Active Preamp Buffer Topologies (`01_modern_jazz_active`, `07_modern_pj_active`, `09_stingray_mm_parallel`)
In instruments equipped with active onboard preamps (e.g., Sadowsky NYC 2-band, Spector 2-band, Music Man 2-band), an internal discrete JFET or op-amp buffer stage directly interfaces with the pickup coils:

```
[Coils] ── Lug 3 (Preamp In) ──► [Buffer Op-Amp: Zin = 1Meg || 25pF] ──► [Active 2-Band EQ] ──► [R_out: 100Ω] ──► [Cable + Anagram]
```

1. **Cable Capacitance Isolation:**
   * In a traditional passive bass, the $750\text{ pF}$ instrument cable load capacitance directly shunts the high-impedance pickup coils, dragging the resonant peak down into the $2.5\text{--}3.5\text{ kHz}$ range.
   * An active preamp presents a high input impedance ($R_{\text{preamp\_in}} = 1.0\text{ M}\Omega$, $C_{\text{preamp\_in}} = 25\text{ pF}$). The coils resonate solely against $C_{\text{coil}} + C_{\text{in}} \approx 100\text{--}170\text{ pF}$, shifting the raw electrical resonant peak into the ultra-clarity $7.0\text{--}8.5\text{ kHz}$ region.
2. **Low-Impedance Cable Driver ($R_{\text{out}} = 100\,\Omega$):**
   * The low output impedance ($100\,\Omega$) drives long instrument cables and downstream pedalboards without high-frequency attenuation:
     $$f_{\text{cable\_cutoff}} = \frac{1}{2\pi \cdot 100 \cdot 780\text{ pF}} \approx 2.04\text{ MHz}$$
3. **Active 2-Band Shelving Filters:**
   * **Sadowsky 2-Band (Jazz & P/J):** $+4.0\text{ dB}$ Bass boost ($40\text{ Hz}$ shelf) and $+4.0\text{ dB}$ Treble boost ($4.0\text{ kHz}$ shelf).
   * **Music Man StingRay 2-Band:** $+5.0\text{ dB}$ Bass boost ($50\text{ Hz}$ shelf) and $+3.0\text{ dB}$ Treble boost ($7.0\text{ kHz}$ shelf).

### B. Vintage Dual-Volume Harness (`02_jazz_bass_pair`, `08_vintage_pj_passive`)
* Standard Jazz Basses and passive P/Js utilize two separate $250\text{k}\Omega$ volume pots wired in parallel.
* At $100\%$ volume, the two pots act as a combined resistive load:
  $$R_{\text{vol\_net}} = 250\text{ k}\Omega \parallel 250\text{ k}\Omega = 125\text{ k}\Omega$$
* This heavy $125\text{ k}\Omega$ loading naturally damps the $Q$ factor of the pickup coils, producing the warm, woody, organic low-mid bloom characteristic of vintage 1960s Jazz Basses and 1980s P/Js.
* Tone control is a single $250\text{k}\Omega$ pot with a $47\text{ nF}$ capacitor.

### C. Vintage CTS 250k Split-P Harness (`05_vintage_62_p_alnico`, `03_jazz_bridge_60s`)
* Classic 1962 Fender Precision specification:
  * Volume: CTS $250\text{ k}\Omega$ Audio Pot
  * Tone: CTS $250\text{ k}\Omega$ Audio Pot with $47\text{ nF}$ paper-in-oil capacitor
  * Net parallel pot load: $250\text{k} \parallel 250\text{k} = 125\text{ k}\Omega$ (unloaded) / with $1\text{ M}\Omega$ receiver: $111\text{ k}\Omega$.

### D. Modern Boutique 500k Harness with Treble Bleed (`04_modern_p_ceramic`)
* Modern ceramic split-coils use $500\text{ k}\Omega$ pots to maintain high-frequency extension:
  * Volume: $500\text{ k}\Omega$ Audio Pot
  * Tone: $500\text{ k}\Omega$ Audio Pot with $22\text{ nF}$ Orange Drop capacitor (higher cutoff than $47\text{ nF}$, preserving punchy midrange bite)
  * **Hybrid Treble Bleed Network:**
    $$Z_{\text{tb}}(s) = R_{\text{ser}} + \frac{R_{\text{par}}}{1 + s \cdot R_{\text{par}} \cdot C_{\text{tb}}}$$
    where $C_{\text{tb}} = 1000\text{ pF}$, $R_{\text{par}} = 150\text{ k}\Omega$, $R_{\text{ser}} = 20\text{ k}\Omega$.
    Maintains crisp pick transient definition when backing off volume without thinness.

### E. Factory Rickenbacker 330k Harness with Series HPF (`10_rickenbacker_bridge_hpf`)
* Authentic Rickenbacker 4001/4003 circuit:
  * Volume: $330\text{ k}\Omega$ Pot
  * Tone: $330\text{ k}\Omega$ Pot with $47\text{ nF}$ capacitor
  * **Vintage Push-Pull Series HPF:** In vintage mode, a $4.7\text{ nF}$ capacitor is inserted in series between the bridge pickup hot lead and the volume control:
    $$f_c = \frac{1}{2\pi \cdot R_{\text{load}} \cdot C_{\text{series}}} \approx 150\text{ Hz}$$
    Rolls off sub-bass rumble while sharpening the aggressive $1.5\text{--}2.5\text{ kHz}$ bridge bite.

### F. High-Inductance 500k Harnesses (`11_pmm_hybrid_series`, `12_mudbucker_ultra_series`, `13_dingwall_multiscale_bridge`)
* High-inductance series pickups ($L > 7\text{ H}$) require $500\text{ k}\Omega$ volume and tone pots to prevent excessive high-frequency rolloff.
* Dingwall and P/MM voices use $47\text{ nF}$ tone caps; Gibson Mudbucker uses $22\text{ nF}$ tone cap.

---

## 3. Output Cable & Receiver Loading

A passive instrument cannot be modeled without including cable and receiver impedances:

### Instrument Cable Capacitance ($C_{\text{cable}}$)
A standard $15\text{--}20\text{ ft}$ quality instrument cable exhibits $30\text{ to }50\text{ pF per foot}$:
$$C_{\text{cable}} \approx 750\text{ pF}$$

This capacitance appears in parallel with the pickup's self-capacitance and receiver input capacitance:
$$C_{\text{tot}} \approx C_{\text{coil}} + C_{\text{cable}} + C_{\text{receiver}}$$

### Receiver Input Load
The Darkglass Anagram hardware input stage presents:
$$R_{\text{receiver}} = 1.0\text{ M}\Omega, \quad C_{\text{receiver}} \approx 30\text{ pF}$$

All Passivizer passive SPICE netlists incorporate this complete load network to guarantee zero tonal discrepancy between simulated DAW pipelines and hardware pedalboard operation.

---

## 4. Acoustic Bridge Force Transducers (`14_upright_bridge_transducer`)

Unlike magnetic pickups whose output is induced via Faraday's Law across an inductive coil ($V \propto d\Phi/dt$), an acoustic bridge transducer (e.g. Underwood, David Gage Realist) operates through the **piezoelectric effect**, generating electrical charge from mechanical shear stress within the bridge:

```
[V_piezo] ───[ R_dc: 50Ω ]──┬───[ C_rick: 15nF ]───┬─── [Direct Buffer Out]
                            │                      │
                        [ C_sensor: 1.2nF ]     [ Zin = 100Meg || 750pF ]
                            │                      │
                           GND                    GND
```

1. **Pure Capacitive Sensor ($L \approx 1\ \mu\text{H}, C_{\text{sensor}} = 1.2\text{ nF}$):**
   * Negligible inductance eliminates RLC peaking; electrical response is purely capacitive.
2. **Direct High-Z Buffer ($100\text{ M}\Omega$):**
   * Transducer bypasses guitar volume/tone pots into a transparent high-impedance buffer.
3. **Subsonic Rumble Decoupling ($C_{\text{series}} = 15\text{ nF}$):**
   * Decouples subsonic mechanical rumble ($f_c \approx 10.6\text{ Hz}$ into $1\text{ M}\Omega$).
4. **Dynamic Bridge Rocking Compliance ($B_{\text{comp}}$):**
   * Non-linear mechanical rocking under pizzicato attack modeled via:
     $$V_{\text{dyn}}(t) = V_{\text{sat}} \cdot \tanh\left(\frac{V(t)}{V_{\text{sat}}}\right)$$
     with $V_{\text{sat}} = 0.42\text{ V}$ (roundwounds) scaled to $0.336\text{ V}$ on 32" fretless flatwounds.

---

## 5. Passive-to-Passive Modeling & Differential SPICE Engine

When transforming a passive source bass (such as a stock Fender Precision Bass or Jazz Bass) into a target passive voice:

```
Active Source (EMG):    [Flat ~20 kHz] ──► [H_target(s)] ──► [Target Sound]
Passive Source:         [V_string] ──► [H_source(s)] ──► [Track] ──► [H_diff(s)] ──► [Target Sound]
```

### The Regularized Differential Transfer Function
To prevent double-filtering (which would cause a disastrous $-24\text{ dB/octave}$ cutoff), Passivizer uses an analytical differential transfer function:

$$|H_{\text{diff}}(f)| = \frac{|H_{\text{target}}(f)| \cdot |H_{\text{source}}(f)|}{|H_{\text{source}}(f)|^2 + \epsilon^2}$$

* $\epsilon = 0.05$ is the **Wiener regularization floor**, preventing division by near-zero stopband values.
* **High-Frequency Clamping:** Above $4.5\text{ kHz}$, maximum boost is clamped to $+6.0\text{ dB}$ relative to $1\text{ kHz}$ reference gain, preventing amplification of passive coil noise and audio interface hiss.
* **True Identity Verification:** When the source instrument equals the target voice (e.g., standard Precision Bass into `05_vintage_62_p_alnico`, or standard Jazz Bass into `02_jazz_bass_pair`), $H_{\text{diff}}$ evaluates to an exact flat line ($\Delta < 0.10\text{ dB}$ across $40\text{--}4500\text{ Hz}$).
* **Dynamic Saturation Bypass:** When `electronics = "passive"`, forward $\tanh$ saturation is automatically bypassed, preserving authentic uncompressed dynamics.

---

## 6. Fractional Core Eddy-Current Diffusion (Foster Ladder)

Traditional guitar circuit simulations treat pickup coil inductance as a fixed, frequency-independent parameter ($s L$). In physical pickups, the high electrical conductivity of solid metallic pole pieces (e.g. Alnico V cylinder magnets or mild steel pole screws) causes eddy currents to circulate within the core as frequency rises.

This magnetic skin effect expels magnetic flux from the core's center into the outer air, causing:
1. An effective reduction in inductance $L(f)$ above $1\text{--}3\text{ kHz}$ (typically $6\text{--}10\%$ drop for conductive Alnico alloys).
2. Frequency-dependent resistive eddy damping ($R_{\text{eddy}} \propto \sqrt{f}$).

Passivizer models this phenomenon using a physical **Foster 2-stage ladder network**:

```
           ┌─── L_core ───┐
──[ L_inf ]┴─── R_core ───┴──
```

$$Z_L(s) = s L_{\infty} + \frac{s L_{\text{core}} R_{\text{core}}}{s L_{\text{core}} + R_{\text{core}}}$$

Where:
* $L_{\infty} = (1 - k_{\text{core}}) L_0$ is the high-frequency asymptote where core flux is expelled.
* $L_{\text{core}} = k_{\text{core}} L_0$ is the core inductance subject to eddy suppression.
* $R_{\text{core}} = 2\pi f_{\text{core}} L_{\text{core}}$ is the eddy loss resistance tuned to the pole piece skin-depth transition frequency ($f_{\text{core}}$).

---

## 7. Dahl Magnetic Domain-Wall Pinning Hysteresis Model

Ferromagnetic core materials exhibit touch-sensitive sustain bloom and micro-hysteresis due to the pinning of magnetic domain walls at grain boundaries and material defects.

Passivizer simulates rate-independent minor hysteresis loops in the string displacement domain at $96\text{ kHz}$ oversampling:

$$\Delta[n] = |x[n] - z[n-1]|$$
$$\text{coupling}[n] = \frac{\Delta[n]}{\Delta[n] + r}$$
$$z[n] = z[n-1] + \Delta x[n] \cdot \text{coupling}[n]$$
$$x_{\text{hyst}}[n] = (1 - \eta_{\text{hyst}}) x[n] + \eta_{\text{hyst}} z[n]$$

Where:
* $z[n]$ represents the internal pinned magnetic polarization state.
* $r = 0.06$ is the domain-wall unpinning threshold.
* $\eta_{\text{hyst}}$ is the material-specific hysteresis coupling factor ($0.06$ for Alnico V; $0.09$ for Alnico II; $0.02$ for Ceramic; $0.01$ for Neodymium; $0.00$ for Piezo).
* This provides warm sustain bloom and subtle phase delay without introducing DC offset.

---

## 8. Magnet Metallurgy Parameter Reference

| Magnet Material | $k_{\text{core}}$ | $f_{\text{core}}\text{ (Hz)}$ | $\eta_{\text{hyst}}$ | Asymmetry $\alpha$ | Physical Metallurgy & Application |
|---|---|---|---|---|---|
| **Alnico V** | $0.08$ | $2500$ | $0.06$ | $0.26$ | Highly conductive cast Al-Ni-Co alloy; vintage P-Bass, Jazz Bass, StingRay. |
| **Alnico II** | $0.10$ | $1800$ | $0.09$ | $0.32$ | Softer magnetic pull, lower coercivity, rich 2nd harmonic bloom; Gibson Mudbucker. |
| **Ceramic (Ferrite)** | $0.02$ | $6500$ | $0.02$ | $0.12$ | Electrically insulating Ba/Sr ferrite; Modern P, Modern PJ, Rickenbacker 4003. |
| **Neodymium** | $0.01$ | $8500$ | $0.01$ | $0.08$ | High coercivity, linear magnetic response; Dingwall FD3 multi-scale. |
| **Piezo** | $0.00$ | $0$ | $0.00$ | $0.00$ | Non-magnetic PZT ceramic transducer; Upright acoustic bridge. |

