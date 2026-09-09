# Passivizer Master Voice Catalog (12 Passive Pickup Configurations & Transducers)

This catalog details the physical parameters, equivalent RLC circuit values, acoustic apertures, and electrical characteristics for the **Passivizer Passive Digital Twin Profiles**.

---

## Quick Reference Summary

| # | Profile ID | Pickup Architecture | Topology | $L_{\text{eq}}$ | $R_{\text{dc}}$ | $f_r$ (Peak) | $Q$ | Acoustic & Circuit Character |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `01_jazz_bass_pair` | J-Bass Pair | Dual Parallel | $1.69\text{ H}$ | $3.69\text{ k}\Omega$ | $3.9\text{ kHz}$ | $1.3$ | Dual narrow single-coils in parallel; 60s/modern $92.1\text{ mm}$ ($3\frac{5}{8}''$) aperture scoop with extended treble. |
| **02** | `02_jazz_bridge_60s` | 60s J-Bass Bridge | Single Coil | $3.60\text{ H}$ | $7.80\text{ k}\Omega$ | $3.2\text{ kHz}$ | $1.6$ | Narrow single-coil placed in 60s position ($63.5\text{ mm}$ from bridge); focused $1.2\text{ kHz}$ midrange bark with balanced low end. |
| **03** | `03_modern_p_ceramic` | Modern Split P | Single Split | $4.80\text{ H}$ | $9.50\text{ k}\Omega$ | $2.2\text{ kHz}$ | $1.8$ | Ceramic split-coil; high-inductance mid punch, tight pick transient attack, compressed low-mids. |
| **04** | `04_vintage_62_p_alnico`| Vintage '62 P | Single Split | $3.80\text{ H}$ | $10.50\text{ k}\Omega$ | $2.8\text{ kHz}$ | $1.4$ | Alnico V split-coil; lower eddy damping, open dynamic sensitivity, woody upper-mid bloom. |
| **05** | `05_p_bass_47nf_rolloff`| Split P w/ 47nF | Split w/ Shunt | $4.80\text{ H}$ | $9.50\text{ k}\Omega$ | $0.45\text{ kHz}$| $0.9$ | Split-coil loaded by $47\text{ nF}$ direct shunt; rolled-off highs above 800 Hz, pillowy sub fundamental. |
| **06** | `06_pj_hybrid_parallel` | P + J Hybrid | Parallel Sum | $2.06\text{ H}$ | $4.28\text{ k}\Omega$ | $3.6\text{ kHz}$ | $1.4$ | Split-P neck and single J-bridge in parallel; chest-thumping low end balanced by bridge snap. |
| **07** | `07_stingray_mm_parallel`| MM Humbucker | Dual Parallel | $2.40\text{ H}$ | $4.60\text{ k}\Omega$ | $3.5\text{ kHz}$ | $1.5$ | Dual-coil parallel humbucker ($d=0.75''$); comb-filter notch at $2.5\text{ kHz}$ and clank peak at $3.5\text{ kHz}$. |
| **08** | `08_rickenbacker_bridge_hpf`| 4003 Bridge HPF | Series HPF | $3.80\text{ H}$ | $8.40\text{ k}\Omega$ | $2.2\text{ kHz}$ | $2.2$ | Single-coil with vintage $4.7\text{ nF}$ series HPF; removes low-end mud below 150 Hz, aggressive pick grit. |
| **09** | `09_pmm_hybrid_series` | P + MM Hybrid | Series Sum | $7.20\text{ H}$ | $14.10\text{ k}\Omega$ | $2.0\text{ kHz}$ | $2.2$ | Split P and MM humbucker in series; $+5.8\text{ dB}$ inductive voltage boost with forward $2.0\text{ kHz}$ authority. |
| **10** | `10_mudbucker_ultra_series`| Overwound Series| Ultra Series | $14.40\text{ H}$| $27.90\text{ k}\Omega$ | $1.2\text{ kHz}$ | $1.6$ | Extreme dual-coil series network; subterranean low-end focus, steep natural top-end rolloff. |
| **11** | `11_dingwall_multiscale_bridge`| Multi-Scale MM | Angled Parallel | $2.30\text{ H}$| $4.40\text{ k}\Omega$ | $3.4\text{ kHz}$ | $1.7$ | 34"-37" fanned-fret bridge position ($48.0\text{ mm}$) with high-tension wave speeds and FD3 parallel dual-coil resonance. |
| **12** | `12_upright_bridge_transducer`| Upright Transducer | Bridge Force | — | — | $4.5\text{ kHz}$ | $0.7$ | Direct bridge force sensor with velocity-to-force leaky integration; woody double-bass bloom. |

---

## Detailed Profile Specifications

### 01. `01_jazz_bass_pair` (Dual Single-Coil Parallel)
* **Archetype:** Standard Jazz Bass Dual Single-Coil Pair
* **Pickup Architecture:** Dual parallel single coils (Neck: $3.20\text{ H}, f_r = 3.6\text{ kHz}$; Bridge: $3.60\text{ H}, f_r = 3.2\text{ kHz}$)
* **Coil Model:** Two narrow single coils ($w = 0.75''$) in parallel spaced $92.1\text{ mm}$ ($3\frac{5}{8}''$) apart ($155.6\text{ mm}$ neck, $63.5\text{ mm}$ bridge)
* **Electrical Parameters:** Dual parallel SPICE branches; combined $L_{\text{eq}} = 1.69\text{ H}$, $R_{\text{dc}} = 3.69\text{ k}\Omega$, $R_{\text{eddy}} = 65\text{ k}\Omega$, $C_{\text{coil}} = 145\text{ pF}$ (composite $f_r = 3.9\text{ kHz}, Q = 1.3$)
* **Acoustic Character:** Symmetrical dual-aperture phase cancellation produces a hollow mid-scoop at $1\text{ kHz}$ with extended sparkle up to $5.5\text{ kHz}$. Individual neck ($3.6\text{ kHz}$) and bridge ($3.2\text{ kHz}$) resonances preserve transient snap on top and body below.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 02. `02_jazz_bridge_60s` (60s Jazz Bass Bridge Single-Coil)
* **Archetype:** 1960s / Modern Fender Jazz Bass Bridge Single Coil
* **Coil Model:** Single coil ($w = 0.75''$) positioned $2.5''$ ($63.5\text{ mm}$) from the bridge
* **Electrical Parameters:** $L = 3.60\text{ H}$, $R_{\text{dc}} = 7.80\text{ k}\Omega$, $R_{\text{eddy}} = 125\text{ k}\Omega$, $C_{\text{coil}} = 70\text{ pF}$
* **Acoustic Character:** Focused harmonic bite centered in the $800\text{ Hz}\text{--}1.6\text{ kHz}$ range with solid, articulate low-end punch. Accentuates fingerstyle definition and chordal clarity.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 03. `03_modern_p_ceramic` (Modern Split-Coil Ceramic)
* **Archetype:** Ceramic High-Inductance Split-Coil P (Bartolini 8CBP style)
* **Coil Model:** Ceramic split-coil ($w = 1.00''$)
* **Electrical Parameters:** $L = 4.80\text{ H}$, $R_{\text{dc}} = 9.50\text{ k}\Omega$, $R_{\text{eddy}} = 110\text{ k}\Omega$, $C_{\text{coil}} = 80\text{ pF}$
* **Acoustic Character:** Immediate pick attack with solid, compressed low-mids ($300\text{--}800\text{ Hz}$) and rolled-off clatter above $4\text{ kHz}$. Anchors dense rhythm sections with clear note boundaries.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 04. `04_vintage_62_p_alnico` (Vintage '62 Split-Coil Alnico V)
* **Archetype:** 1962 Fender Precision with Alnico V Pole Pieces
* **Coil Model:** Alnico V split-coil ($w = 1.00''$)
* **Electrical Parameters:** $L = 3.80\text{ H}$, $R_{\text{dc}} = 10.50\text{ k}\Omega$, $R_{\text{eddy}} = 180\text{ k}\Omega$, $C_{\text{coil}} = 60\text{ pF}$
* **Acoustic Character:** Lower core eddy-current damping yields an open, touch-sensitive, uncompressed response with a higher resonant peak ($2.8\text{ kHz}$). Dynamic and woody with natural acoustic breath.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 05. `05_p_bass_47nf_rolloff` (Split-Coil P with 47nF Tone Shunt)
* **Archetype:** Vintage P-Bass with Tone Rolled to 0 (Jamerson / Palladino style)
* **Coil Model:** P-Bass split-coil loaded by direct $47\text{ nF}$ capacitor shunt
* **Electrical Parameters:** $L = 4.80\text{ H}$, $R_{\text{dc}} = 9.50\text{ k}\Omega$, $C_{\text{tone}} = 47\text{ nF}$
* **Acoustic Character:** Removes string clack and finger transients above $800\text{ Hz}$, concentrating energy purely in the fundamental $40\text{--}200\text{ Hz}$ register. Delivers warm, pillowy low-end thump.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 06. `06_pj_hybrid_parallel` (P/J Hybrid Parallel Sum)
* **Archetype:** P/J Bass Configuration (Fender Precision Special / Yamaha BB)
* **Pickup Architecture:** Dual parallel pickups:
  * **Precision Neck:** Split-coil Bartolini 8CBP ($L = 4.80\text{ H}, f_r = 2200\text{ Hz}, Q = 1.8$, E/A @ $139\text{ mm}$, D/G @ $111\text{ mm}$)
  * **Jazz Bridge:** Single-coil Bartolini 9CBJS1 ($L = 3.60\text{ H}, f_r = 3200\text{ Hz}, Q = 1.6$, @ $63.5\text{ mm}$)
* **Electrical Parameters:** Dual parallel SPICE branches; composite $L_{\text{eq}} = 2.06\text{ H}$, $R_{\text{dc}} = 4.28\text{ k}\Omega$, $R_{\text{eddy}} = 60\text{ k}\Omega$, $C_{\text{coil}} = 150\text{ pF}$ (composite $f_r = 3.6\text{ kHz}, Q = 1.4$)
* **Acoustic Character:** Simultaneous presentation of the deep $2.2\text{ kHz}$ P-neck fundamental punch and the bright $3.2\text{ kHz}$ J-bridge bite, modulated by $85\text{ mm}$ spatial phase cancellation in the lower midrange.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 07. `07_stingray_mm_parallel` (Music Man Dual-Coil Parallel)
* **Archetype:** Music Man StingRay 4-String Dual-Coil Parallel Humbucker
* **Coil Model:** Dual-coil humbucker ($w = 1.50''$, $d = 0.75''$) in parallel
* **Electrical Parameters:** $L = 2.40\text{ H}$, $R_{\text{dc}} = 4.60\text{ k}\Omega$, $R_{\text{eddy}} = 140\text{ k}\Omega$, $C_{\text{coil}} = 130\text{ pF}$
* **Acoustic Character:** Dual-coil phase comb cancellation notch at $2.5\text{ kHz}$ combined with an electrical resonance peak at $3.5\text{ kHz}$. Tight low end with pronounced metallic clank.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Dual-Coil Mode - Push/Pull Up).

### 08. `08_rickenbacker_bridge_hpf` (Rickenbacker 4003 Bridge with 4.7nF HPF)
* **Archetype:** Rickenbacker 4001/4003 Bridge Pickup with Vintage High-Pass Push-Pull
* **Coil Model:** High-output single coil with $4.7\text{ nF}$ series capacitor
* **Electrical Parameters:** $L = 3.80\text{ H}$, $R_{\text{dc}} = 8.40\text{ k}\Omega$, $C_{\text{series}} = 4.7\text{ nF}$, $C_{\text{coil}} = 90\text{ pF}$
* **Acoustic Character:** The series capacitor acts as a high-pass filter, rolling off sub-bass below $150\text{ Hz}$ while focusing midrange punch ($1.5\text{--}2.5\text{ kHz}$). Produces an aggressive, gritty pick attack.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 09. `09_pmm_hybrid_series` (P/MM Hybrid Series Sum)
* **Archetype:** Custom P/MM Hybrid in Series
* **Pickup Architecture:** Dual series pickups:
  * **Precision Neck:** Split-coil Bartolini 8CBP ($L = 4.80\text{ H}, f_r = 2200\text{ Hz}, Q = 1.8$)
  * **Music Man Bridge:** Dual-coil humbucker MM4CBC ($L = 2.40\text{ H}, f_r = 3500\text{ Hz}, Q = 1.5$)
* **Electrical Parameters:** Series-connected SPICE stages; total series $L_{\text{ser}} = 7.20\text{ H}$, $R_{\text{dc}} = 14.10\text{ k}\Omega$, $R_{\text{eddy}} = 250\text{ k}\Omega$, $C_{\text{coil}} = 50\text{ pF}$ (composite $f_r = 2.0\text{ kHz}, Q = 2.2$)
* **Acoustic Character:** Series inductance addition yields a large $+5.8\text{ dB}$ signal boost and a dense, forward $2.0\text{ kHz}$ resonant center. Fills out sparse instrument arrangements with commanding low-mids.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Dual-Coil Mode - Push/Pull Up).

### 10. `10_mudbucker_ultra_series` (Ultra-High Inductance Overwound Series)
* **Archetype:** Gibson EB-0 Mudbucker / Overwound Series Dual-Coil
* **Coil Model:** Extreme dual-coil overwound series network
* **Electrical Parameters:** $L = 14.40\text{ H}$, $R_{\text{dc}} = 27.90\text{ k}\Omega$, $R_{\text{eddy}} = 80\text{ k}\Omega$, $C_{\text{coil}} = 80\text{ pF}$
* **Acoustic Character:** Resonant peak pulls down to $1.2\text{ kHz}$, naturally rolling off high frequencies. Deep, massive low end with zero high-frequency fizz, ideal for heavy fuzz and saturated drive stages.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 11. `11_dingwall_multiscale_bridge` (Fanned-Fret Multi-Scale Bridge)
* **Archetype:** Dingwall NG Multi-Scale Angled Bridge Position
* **Coil Model:** Dual-coil humbucker in parallel positioned $48.0\text{ mm}$ from bridge
* **Electrical Parameters:** $L = 2.30\text{ H}$, $R_{\text{dc}} = 4.40\text{ k}\Omega$, $R_{\text{eddy}} = 150\text{ k}\Omega$, $C_{\text{coil}} = 120\text{ pF}$
* **Acoustic Character:** 34"-37" fanned-fret wave-speed scaling with high string tension, angled bridge sweet spot ($48.0\text{ mm}$), FD3 dual-coil parallel resonance ($3.4\text{ kHz}$), and stainless-steel string harmonic extension.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Dual-Coil Mode - Push/Pull Up).

### 12. `12_upright_bridge_transducer` (Upright Acoustic Bridge Transducer)
* **Archetype:** Direct Bridge Force Transducer on 3/4 Double Bass (41.5" Scale, Underwood / David Gage Realist style)
* **Target String Archetype:** 3/4 Double Bass spiral rope-core strings (`double_bass_spirocore`, $265\text{ lbs}$ tension, coupled spruce soundboard damping)
* **Sensor Model:** Direct bridge saddle force sensor ($x = 5.0\text{ mm}$) with velocity-to-force leaky integration ($+6\text{ dB/oct}$ from $70\text{ Hz}$ to $250\text{ Hz}$)
* **Dynamic Compliance:** Soft-knee bridge rocking saturation ($V_{\text{sat}} \cdot \tanh(v / V_{\text{sat}})$), dynamically scaled for lower-tension strings ($V_{\text{sat}} = 0.336\text{ V}$ on 32" fretless with La Bella LTF vs $0.42\text{ V}$ baseline)
* **Anti-Double-Damping:** Automatically matches source string damping ($f_{\text{damp, src}}$) to target double-bass damping ($f_{\text{damp, tgt}}$). When evaluated from flatwound instruments (La Bella LTF), the filter avoids double-muffling the high frequencies while preserving woody bridge bite.
* **Electrical Parameters:** Pure capacitive piezo sensor ($C_{\text{piezo}} = 1.2\text{ nF}$), direct high-Z tailpiece wiring, subsonic rumble decoupling @ $32\text{ Hz}$
* **Acoustic Character:** Eliminates magnetic pickup comb filtering; delivers smooth, woody double-bass pizzicato bloom with deep sub-bass body resonance.
* **32" Fretless Setting:** ABCX Blend to **Upright Blend** (85% PCSX + 15% MMTWX Single - Push/Pull Down: J Mode). Pair with **3 Sigma Upright Bass IR** in Anagram Block 3.

---

## Geometry & Displacement Mapping (30" EMG MM $\to$ 32" Target Datums)

When running Passivizer from a **30" short-scale bass with a single 18V EMG MM pickup**, the software compensates for aperture and physical spatial displacement:

### Physical Datums:
* **Source Instrument (30" Bass):**
  * Scale Length: $30.0'' = 762.0\text{ mm}$
  * 12th Fret Datum: $381.0\text{ mm}$ from nut
  * Pickup Center Datum: $303.5\text{ mm}$ from 12th fret toward bridge
  * **Pickup Center from Bridge ($x_{\text{source}}$):** $381.0 - 303.5 = \mathbf{77.5\text{ mm}}\ (3.051'')$
  * Pickup Architecture: Fixed Dual-Coil Humbucker ($w = 1.50''$, $d = 0.75''$)

* **Target Reference Instrument (32" Bass from `Pickup Placement - P_MM.md`):**
  * Scale Length: $32.0'' = 812.8\text{ mm}$
  * Reverse PX Split Center Datum: $\mathbf{122.8\text{ mm}}\ (4.835'')$ from bridge
  * MMTWX Centerline Datum: $\mathbf{62.2\text{ mm}}\ (2.449'')$ from bridge
  * MMTWX Bridge-side Coil (Jazz Bridge) Datum: $\mathbf{50.8\text{ mm}}\ (2.000'')$ from bridge

### Spatial Displacement Offsets ($\Delta x = x_{\text{target}} - 77.5\text{ mm}$):

| Profile ID | Target Location | Target $x$ | Displacement $\Delta x$ | Acoustic Compensation |
| :--- | :--- | :--- | :--- | :--- |
| **`01_jazz_bass_pair`** | J-Pair Virtual Center | $86.8\text{ mm}$ | $+9.3\text{ mm}\ (+0.37'')$ | De-humbuck aperture, mild forward tilt |
| **`02_jazz_bridge_60s`** | MMTWX Bridge Coil (JB) | $50.8\text{ mm}$ | $-26.7\text{ mm}\ (-1.05'')$ | De-humbuck aperture, tighter bridge bite tilt |
| **`03_modern_p_ceramic`** | Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | $+2.7\text{ dB}$ low boost, tames bridge bite |
| **`04_vintage_62_p_alnico`**| Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | $+2.7\text{ dB}$ low boost, smooth woody rolloff |
| **`05_p_bass_47nf_rolloff`** | Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | Full $47\text{ nF}$ rolloff; deep sub-thump |
| **`06_pj_hybrid_parallel`** | P/J Virtual Center | $86.8\text{ mm}$ | $+9.3\text{ mm}\ (+0.37'')$ | Hybrid aperture mix, balanced energy |
| **`07_stingray_mm_parallel`**| MMTWX Centerline | $62.2\text{ mm}$ | $-15.3\text{ mm}\ (-0.60'')$ | Preserves dual-coil comb, tightens lows |
| **`08_rickenbacker_bridge_hpf`** | Bridge Clank Position | $50.8\text{ mm}$ | $-26.7\text{ mm}\ (-1.05'')$ | Series HPF engaged, maximum pick bite |
| **`09_pmm_hybrid_series`**| Dual Series Center | $92.5\text{ mm}$ | $+15.0\text{ mm}\ (+0.59'')$ | Series inductance boost, thick low-mids |
| **`10_mudbucker_ultra_series`**| Deep Series Center | $92.5\text{ mm}$ | $+15.0\text{ mm}\ (+0.59'')$ | Extreme $14.4\text{ H}$ low-frequency foundation |
| **`11_dingwall_multiscale_bridge`**| Angled Sweet Spot | $48.0\text{ mm}$ | $-29.5\text{ mm}\ (-1.16'')$ | High string wave speed, metallic clank |
| **`12_upright_bridge_transducer`**| Bridge Transducer Datum | $5.0\text{ mm}$ | $-72.5\text{ mm}\ (-2.85'')$ | Bridge force integration, de-comb, body bloom |
