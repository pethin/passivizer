# Circuit Theory & Electrical Modeling

This document details the electrical equations, component parameters, and physical phenomena modeled in **Passivizer** to recreate passive bass pickups from active EMG X-Series signals.

---

## 1. The Passive Pickup Equivalent Network

A passive magnetic pickup is not merely a voltage source; it is a complex, high-impedance RLC resonant transducer. The standard linear equivalent circuit consists of:

$$V_{\text{out}}(s) = V_{\text{ind}}(s) \cdot H_{\text{elec}}(s)$$

Where:
* $V_{\text{ind}}$ is the voltage induced across the coils by the vibrating string.
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
   * Typically $2\text{ to }10\text{ Henries}$ for bass pickups.
   * Directly governs the frequency of the resonant peak ($f_r$). Higher inductance shifts the peak down into the low-mids.
   * Series wiring quadruples inductance relative to single coils ($L_{\text{ser}} \approx 4 \times L_{\text{single}}$), while parallel wiring halves it ($L_{\text{par}} \approx \frac{1}{2} L_{\text{single}}$).

2. **DC Resistance ($R_{\text{dc}}$):**
   * Resistance of thousands of turns of AWG 42 or 43 copper wire (typically $4\text{ k}\Omega\text{ to }18\text{ k}\Omega$).
   * Determines the baseline damping of the circuit and limits the maximum quality factor ($Q$).

3. **Inter-Winding Self-Capacitance ($C_{\text{coil}}$):**
   * Stray capacitance between adjacent coil turns, typically $50\text{ to }150\text{ pF}$.
   * Minor compared to cable capacitance, but sets the theoretical upper ceiling for unloaded resonance.

4. **Core Losses & Eddy Currents ($R_{\text{eddy}}$):**
   * Moving magnetic fields induce circular eddy currents in conductive pole pieces, steel baseplates, and magnets.
   * Modeled as a parallel resistance ($R_{\text{eddy}} \approx 80\text{ k}\Omega\text{ to }180\text{ k}\Omega$) across the coil.
   * This creates frequency-dependent damping: upper harmonics roll off more smoothly than an ideal 2nd-order filter, eliminating harsh, synthetic high-end resonance.

5. **Dynamic Core Compliance & String Excursion Saturation ($B_{\text{comp}}$):**
   * High-amplitude pick and slap transients push magnetic string coupling into non-linear excursion ($d\Phi/dx$).
   * Modeled in SPICE via an arbitrary behavioral voltage source:
     $$V_{\text{dyn}}(t) = V_{\text{sat}} \cdot \tanh\left(\frac{V(t)}{V_{\text{sat}}}\right)$$
   * For light to medium playing ($< 0.2\text{V}$), the response is $98\text{--}100\%$ linear.
   * On heavy pluck spikes ($> 0.4\text{V}$), the smooth $\tanh$ function provides $1.5\text{--}2.5\text{ dB}$ of analog soft-knee saturation, capturing authentic passive pickup compression and touch-sensitive dynamic give.

---

## 2. Onboard Guitar Controls & Loading

Once the signal leaves the coils, it encounters the potentiometer network and tone controls:

```
[From Coils] ── Lug 3 (Input)
                  │
                  ├──[ Hybrid Treble Bleed: (C_tb || R_tb_par) + R_tb_ser ]──┐
                  │                                                          │
              [ R_vol: 500k ]                                                │
                  │                                                          │
                Lug 2 (Wiper / Output) ◄─────────────────────────────────────┘
                  │
                 Lug 1 (Ground) ──► GND
```

### A. The 500k Volume Pot
* Unlike a $250\text{ k}\Omega$ pot which damps the resonant peak, a $500\text{ k}\Omega$ pot maintains higher $Q$ (cleaner articulation and more pronounced transient bite).
* In SPICE, the pot is modeled as two variable resistors:
  $$R_{\text{top}} = R_{\text{pot}} \cdot (1 - \alpha), \quad R_{\text{bot}} = R_{\text{pot}} \cdot \alpha$$
  where $\alpha \in [0, 1]$ represents the mechanical taper.

### B. Hybrid Treble-Bleed Network
The blueprint specifies:
* **Capacitor ($C_{\text{tb}}$):** $1,000\text{ pF}$ ($1.0\text{ nF}$)
* **Parallel Resistor ($R_{\text{par}}$):** $150\text{ k}\Omega$ (1/4W, 1%)
* **Series Resistor ($R_{\text{ser}}$):** $20\text{ k}\Omega$ (1/4W, 1%)

**Transfer Function of the Bleed Network:**
$$Z_{\text{tb}}(s) = R_{\text{ser}} + \frac{R_{\text{par}}}{1 + s \cdot R_{\text{par}} \cdot C_{\text{tb}}}$$

* At wide-open volume ($\alpha = 1$), Lug 2 connects directly to Lug 3, shorting out $Z_{\text{tb}}$ entirely (zero tonal coloration).
* When rolling volume down to $6\text{--}8$, the network routes frequencies above $1.5\text{ kHz}$ directly to the output, preventing high-frequency loss while avoiding the thin, tinny sound of pure-capacitor bleeds.

---

## 3. Output Cable & Receiver Impedance

A passive guitar cannot be analyzed in isolation from the cable and amplifier input.

### Cable Capacitance ($C_{\text{cable}}$)
A standard $15\text{--}20\text{ ft}$ quality instrument cable exhibits $30\text{ to }50\text{ pF per foot}$:
$$C_{\text{cable}} \approx 700\text{ to }850\text{ pF}$$

This capacitance is in parallel with the pickup's self-capacitance and dominates the total load capacitance $C_{\text{tot}}$:
$$C_{\text{tot}} \approx C_{\text{coil}} + C_{\text{cable}} + C_{\text{amp}}$$

### The Resonant Formula
The resulting resonant peak frequency ($f_r$) is:
$$f_r = \frac{1}{2\pi \sqrt{L_{\text{coil}} \cdot C_{\text{tot}}}}$$

For the **Bartolini 8CBP** ($L = 4.8\text{ H}$, $C_{\text{tot}} \approx 850\text{ pF}$):
$$f_r = \frac{1}{2\pi \sqrt{4.8 \cdot 850 \times 10^{-12}}} \approx 2,490\text{ Hz}$$
Under pot and core loading, this lands right at $\approx 2.2\text{ kHz}$, providing the signature punchy P-bass high-mid growl.

### Amplifier Input Impedance
The Darkglass Anagram input stage presents a load of:
$$R_{\text{load}} = 1.0\text{ M}\Omega, \quad C_{\text{load}} \approx 30\text{ pF}$$
This load is included in the Passivizer SPICE netlists to guarantee zero impedance mismatch when loaded onto hardware.

---

## 4. Acoustic Bridge Force Transducers (Piezoelectric Load)

Unlike magnetic pickups whose output is induced via Faraday's Law across an inductive coil ($V \propto d\Phi/dt$), an acoustic bridge transducer (e.g. Underwood, David Gage Realist, Fishman Full Circle) operates through the **piezoelectric effect**, generating electrical charge from mechanical shear stress and compression within the maple bridge wings:

```
[V_piezo] ───[ R_dc: 50Ω ]──┬───[ C_rick: 15nF ]───┬─── [Direct Tailpiece Out]
                            │                      │
                        [ C_sensor: 1.2nF ]     [ Cable: 750pF || Anagram: 1Meg ]
                            │                      │
                           GND                    GND
```

### Key Parameters & Differences from Magnetic Circuits:
1. **Zero Inductive Peaking ($L \approx 1\ \mu\text{H}$):**
   * Piezoelectric ceramics exhibit negligible inductance. The transducer has no passive electrical $RLC$ resonant peak; its electrical response is purely capacitive ($C_{\text{sensor}} \approx 1.2\text{ nF}$).
2. **Direct Tailpiece Wiring (Volume Pot Bypass):**
   * Upright bridge transducers connect directly to high-impedance buffers without passing through typical $500\text{ k}\Omega$ volume pots or treble bleed networks. The circuit load resistance is set to $100\text{ M}\Omega$ internal, dominated solely by the receiver ($1.0\text{ M}\Omega$ Anagram input).
3. **Subsonic Decoupling ($C_{\text{rick}} = 15\text{ nF}$):**
   * A series decoupling capacitor decouples DC and subsonic stage rumble ($f_c \approx 10.6\text{ Hz}$ into $1\text{ M}\Omega$), preventing handling thumps from overloading downstream compressors and impulse engines.
4. **Dynamic Bridge Rocking Compliance ($B_{\text{comp}}$):**
   * Under heavy pizzicato finger plucks, physical maple wood flex and soundpost compliance introduce gentle mechanical soft-knee saturation modeled in SPICE via:
     $$V_{\text{dyn}}(t) = 0.42 \cdot \tanh\left(\frac{V(t)}{0.42}\right)$$
   * Captures the warm, compressed "bloom" and physical tactile pushback of a double-bass bridge.

