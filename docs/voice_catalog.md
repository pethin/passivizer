# Passivizer Master Voice Catalog (17 Pickup Configurations & Transducers)

This catalog details the physical parameters, equivalent RLC circuit values, acoustic apertures, control harnesses, and electrical characteristics for the **Passivizer Digital Twin Profiles**.

---

## Quick Reference Summary

| # | Profile ID | Pickup Architecture | Topology | Harness / Controls | $L_{\text{eq}}$ | $R_{\text{dc}}$ | $f_r$ (Peak) | Acoustic & Circuit Character |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `01_modern_jazz_active` | Modern Active Jazz | Active 2-Band | Sadowsky 2-Band Preamp ($R_{\text{in}}=1\text{M}\Omega, R_{\text{out}}=100\,\Omega$) | $1.69\text{ H}$ (isolated) | $3.69\text{ k}\Omega$ | $7.8\text{ kHz}$ | Sadowsky-style active 2-band boost with isolated 60s J-pair ($92.1\text{ mm}$ aperture scoop), wideband hi-fi sparkle, punchy active bass and treble shelving. |
| **02** | `02_jazz_bass_pair` | Vintage 60s J-Bass Pair | Dual Parallel | Vintage 60s $2\times 250\text{k}\Omega$ Vol ($125\text{k}\Omega$ net), $250\text{k}\Omega$ Tone, $47\text{nF}$ Cap | $1.69\text{ H}$ | $3.69\text{ k}\Omega$ | $2.7\text{ kHz}$ | Dual narrow single-coils in parallel; authentic 60s $92.1\text{ mm}$ ($3\frac{5}{8}''$) aperture scoop with natural woody low-mid resonance. |
| **02b**| `02b_jazz_bass_pair_22nf`| 60s J-Bass Pair (22nF ToneStyler)| Dual Parallel | Vintage 60s $2\times 250\text{k}\Omega$ Vol, 22nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$) | $1.69\text{ H}$ | $3.69\text{ k}\Omega$ | $762\text{ Hz}$ | Vocal midrange honk ($762\text{ Hz}$ resonant peak, $-3\text{ dB}$ at $1225\text{ Hz}$); pure capacitive shunt preserves punchy Jaco bridge growl with zero wiper mud. |
| **03** | `03_jazz_bridge_60s` | 60s J-Bass Bridge | Single Coil | Vintage $250\text{k}\Omega$ Vol, $250\text{k}\Omega$ Tone, $47\text{nF}$ Cap | $3.60\text{ H}$ | $7.80\text{ k}\Omega$ | $2.8\text{ kHz}$ | Narrow single-coil placed in 60s bridge position ($63.5\text{ mm}$ from bridge); focused midrange growl with articulate transient snap. |
| **04** | `04_modern_p_ceramic` | Modern Split P | Single Split | Modern Boutique $500\text{k}\Omega$ Vol, $500\text{k}\Omega$ Tone, $22\text{nF}$ Cap, Treble Bleed | $4.80\text{ H}$ | $9.50\text{ k}\Omega$ | $2.4\text{ kHz}$ | Ceramic split-coil; modern boutique 500k harness preserves high-mid punch and pick attack clarity; hybrid treble bleed maintains presence when backed off. |
| **05** | `05_vintage_62_p_alnico`| Vintage '62 P (Tone Open)| Single Split | Vintage 1962 CTS $250\text{k}\Omega$ Vol, $250\text{k}\Omega$ Tone Open, $47\text{nF}$ Cap | $3.80\text{ H}$ | $10.50\text{ k}\Omega$ | $2.1\text{ kHz}$ | Alnico V split-coil wide open; touch-sensitive dynamic response, woody organic bloom ($4.0\text{ kHz}$ cutoff). |
| **05b**| `05b_vintage_62_p_22nf` | Vintage '62 P (22nF ToneStyler)| Single Split | 22nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$) | $3.80\text{ H}$ | $10.50\text{ k}\Omega$ | $440\text{ Hz}$ | Modern Fender spec; punchy $440\text{ Hz}$ low-mid resonant focus (+1.5 dB), $-3\text{ dB}$ cutoff at $750\text{ Hz}$, eliminates fret clatter while retaining punch. |
| **05c**| `05c_vintage_62_p_47nf`| Vintage '62 P (47nF ToneStyler)| Single Split | 47nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$), Flatwound Heavy | $3.80\text{ H}$ | $10.50\text{ k}\Omega$ | $450\text{ Hz}$ | Authentic Jamerson Motown flatwound thump with 47nF ToneStyler pure capacitive shunt; low-tension bloom and deep pillowy warmth. |
| **05d**| `05d_vintage_50s_p_100nf`| Vintage '50s P (100nF ToneStyler)| Single Split | 100nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$) | $3.80\text{ H}$ | $10.50\text{ k}\Omega$ | Sub-bass | Original 1951–1959 Fullerton factory paper-in-oil spec; massive sub-bass shelf rolloff ($-3\text{ dB}$ at $240\text{ Hz}$, deep Motown / reggae dub thump). |
| **07** | `07_modern_pj_active` | Modern Active P/J | Active 2-Band | Sadowsky/Spector 2-Band Preamp ($R_{\text{in}}=1\text{M}\Omega, R_{\text{out}}=100\,\Omega$) | $2.06\text{ H}$ (isolated) | $4.28\text{ k}\Omega$ | $7.6\text{ kHz}$ | Active 2-band boost with isolated ceramic P/J coils ($139/111\text{ mm}$ P + $63.5\text{ mm}$ J); punchy sub-bass fundamental, wideband sparkle, and aggressive bridge clank. |
| **08** | `08_vintage_pj_passive`| Vintage '80s Passive P/J| Parallel Sum | Dual $250\text{k}\Omega$ Vol ($125\text{k}\Omega$ net), $250\text{k}\Omega$ Tone, $47\text{nF}$ Cap | $1.85\text{ H}$ | $4.48\text{ k}\Omega$ | $2.8\text{ kHz}$ | Vintage Alnico V split-P and 60s J-bridge in parallel; authentic '80s Fender Special / Yamaha BB thump with woody mid-punch. |
| **09** | `09_stingray_mm_parallel`| MM Humbucker Active | Active 2-Band | Music Man 2-Band Preamp ($R_{\text{in}}=1\text{M}\Omega, R_{\text{out}}=100\,\Omega$) | $2.40\text{ H}$ (isolated) | $4.60\text{ k}\Omega$ | $7.2\text{ kHz}$ | Dual-coil parallel humbucker with authentic active MM preamp buffer isolating coils from cable loading; comb notch at $2.5\text{ kHz}$ and clank peak at $7.2\text{ kHz}$. |
| **10** | `10_rickenbacker_bridge_hpf`| 4003 Bridge HPF | Series HPF | Factory Rickenbacker $330\text{k}\Omega$ Vol, $330\text{k}\Omega$ Tone, $4.7\text{nF}$ Series HPF | $3.80\text{ H}$ | $8.40\text{ k}\Omega$ | $2.2\text{ kHz}$ | High-output single-coil with vintage $4.7\text{ nF}$ series HPF; removes low-end mud below $150\text{ Hz}$, delivering aggressive pick grit and clang. |
| **11** | `11_pmm_hybrid_series` | P + MM Hybrid | Series Sum | Modern $500\text{k}\Omega$ Vol, $500\text{k}\Omega$ Tone, $47\text{nF}$ Cap | $7.20\text{ H}$ | $14.10\text{ k}\Omega$ | $1.6\text{ kHz}$ | Split P and MM humbucker in series; $+5.8\text{ dB}$ inductive voltage boost with forward $1.6\text{ kHz}$ punch. |
| **12** | `12_mudbucker_ultra_series`| Overwound Series| Ultra Series | Gibson $500\text{k}\Omega$ Vol, $500\text{k}\Omega$ Tone, $22\text{nF}$ Cap | $14.40\text{ H}$| $27.90\text{ k}\Omega$ | $1.2\text{ kHz}$ | Extreme dual-coil series network; subterranean low-end focus, steep natural top-end rolloff. |
| **13** | `13_dingwall_multiscale_bridge`| Multi-Scale MM | Angled Parallel | Dingwall $500\text{k}\Omega$ Vol, $500\text{k}\Omega$ Tone, $47\text{nF}$ Cap | $2.30\text{ H}$| $4.40\text{ k}\Omega$ | $3.4\text{ kHz}$ | 34"-37" fanned-fret bridge position ($48.0\text{ mm}$) with high-tension wave speeds and FD3 parallel dual-coil resonance. |
| **14** | `14_upright_bridge_transducer`| Upright Transducer | Bridge Force | Direct $100\text{ M}\Omega$ Buffer, $15\text{ nF}$ Subsonic Rumble Cap | — | — | $4.5\text{ kHz}$ | Direct bridge force sensor with velocity-to-force leaky integration; woody double-bass bloom. |

---

## Detailed Profile Specifications

### 01. `01_modern_jazz_active` (Modern Active Jazz Bass Pair)
* **Archetype:** Sadowsky / Modern NYC Active Jazz Bass (Dual Single-Coil with 2-Band Boost Preamp)
* **Pickup Architecture:** Dual parallel single coils (Neck: $3.20\text{ H}$, Bridge: $3.60\text{ H}$ in 60s spacing, $92.1\text{ mm}$ coil spacing)
* **Control Harness:** Sadowsky-style active 2-band preamp buffer ($R_{\text{in}} = 1.0\text{ M}\Omega$, $C_{\text{in}} = 25\text{ pF}$, low-impedance $R_{\text{out}} = 100\,\Omega$). Preamp active EQ provides $+4.0\text{ dB}$ bass boost ($40\text{ Hz}$ shelf) and $+4.0\text{ dB}$ treble boost ($4.0\text{ kHz}$ shelf).
* **Electrical Parameters:** The active buffer completely isolates the high-impedance pickup coils from cable capacitance ($750\text{ pF}$). The coils resonate with only $C_{\text{coil}} + C_{\text{in}} \approx 170\text{ pF}$, shifting the raw coil resonance up to $\sim 7.8\text{ kHz}$.
* **Acoustic Character:** Modern hi-fi sparkle, punchy extended low-end weight, tight transient response, and transparent scooped midrange.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 02. `02_jazz_bass_pair` (Vintage 60s Jazz Bass Pair)
* **Archetype:** Standard 1960s Fender Jazz Bass Dual Single-Coil Pair (Tone Wide Open)
* **Pickup Architecture:** Dual parallel single coils (Neck: $3.20\text{ H}$; Bridge: $3.60\text{ H}$) spaced $92.1\text{ mm}$ ($3\frac{5}{8}''$) apart ($155.6\text{ mm}$ neck, $63.5\text{ mm}$ bridge)
* **Control Harness:** Authentic vintage dual $250\text{k}\Omega$ volume pots in parallel ($125\text{k}\Omega$ net load resistance), single $250\text{k}\Omega$ tone pot, $47\text{ nF}$ capacitor, no treble bleed.
* **Electrical Parameters:** Dual parallel SPICE branches; combined $L_{\text{eq}} = 1.69\text{ H}$, $R_{\text{dc}} = 3.69\text{ k}\Omega$, $R_{\text{eddy}} = 65\text{ k}\Omega$, $C_{\text{coil}} = 145\text{ pF}$. When loaded by $125\text{k}\Omega$ volume, $250\text{k}\Omega$ tone, and $750\text{ pF}$ cable, the composite loaded resonance sits at $2.7\text{ kHz}$.
* **Acoustic Character:** Symmetrical dual-aperture phase cancellation produces a hollow mid-scoop at $1\text{ kHz}$ with classic woody low-mid resonance and open high-end.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 02b. `02b_jazz_bass_pair_22nf` (Vintage 60s Jazz Bass Pair - 22nF ToneStyler)
* **Archetype:** Standard 1960s Fender Jazz Bass Dual Single-Coil Pair with Stellartone ToneStyler (22nF Pure Capacitive Shunt)
* **Pickup Architecture:** Dual parallel single coils (Neck: $3.20\text{ H}$; Bridge: $3.60\text{ H}$) spaced $92.1\text{ mm}$ ($3\frac{5}{8}''$) apart ($155.6\text{ mm}$ neck, $63.5\text{ mm}$ bridge)
* **Control Harness:** Authentic vintage dual $250\text{k}\Omega$ volume pots in parallel ($125\text{k}\Omega$ net load), Stellartone ToneStyler rotary switch selecting a precision $22\text{ nF}$ capacitor shunt to ground ($R_{\text{tone}} = 3.3\,\Omega$ switch/lead ESR, zero variable wiper damping).
* **Electrical Parameters:** Combined $L_{\text{eq}} = 1.69\text{ H}$, $R_{\text{dc}} = 3.69\text{ k}\Omega$, $R_{\text{tone}} = 3.3\,\Omega$, $C_{\text{tone}} = 22\text{ nF}$. Undamped resonant peak at **$762\text{ Hz}$**, $-3\text{ dB}$ cutoff at **$1225\text{ Hz}$**.
* **Acoustic Character:** The iconic Jaco Pastorius / Marcus Miller fingerstyle vocal bridge burp: by eliminating variable potentiometer wiper resistance, the high-$Q$ resonant bump (+4.8 dB above standard 50% pot) is preserved directly in the vocal $760\text{ Hz}$ register, filtering out fret click and pick noise while maintaining commanding midrange articulation and punch.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 03. `03_jazz_bridge_60s` (60s Jazz Bass Bridge Single-Coil)
* **Archetype:** 1960s Fender Jazz Bass Bridge Single Coil
* **Coil Model:** Single coil ($w = 0.75''$) positioned $2.5''$ ($63.5\text{ mm}$) from the bridge
* **Control Harness:** Authentic $250\text{k}\Omega$ volume pot, $250\text{k}\Omega$ tone pot, $47\text{ nF}$ tone capacitor, no treble bleed.
* **Electrical Parameters:** $L = 3.60\text{ H}$, $R_{\text{dc}} = 7.80\text{ k}\Omega$, $R_{\text{eddy}} = 125\text{ k}\Omega$, $C_{\text{coil}} = 70\text{ pF}$. Loaded $f_r = 2.8\text{ kHz}$.
* **Acoustic Character:** Focused harmonic bite centered in the $800\text{ Hz}\text{--}1.6\text{ kHz}$ range with solid, articulate low-end punch. Accentuates fingerstyle definition and classic Jaco growl.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 04. `04_modern_p_ceramic` (Modern Split-Coil Ceramic)
* **Archetype:** Ceramic High-Inductance Split-Coil P (Bartolini 8CBP style)
* **Coil Model:** Ceramic split-coil ($w = 1.00''$)
* **Control Harness:** Modern boutique $500\text{k}\Omega$ audio volume pot, $500\text{k}\Omega$ no-load/linear tone pot, $22\text{ nF}$ Orange Drop capacitor, and hybrid treble bleed ($1000\text{ pF} \parallel 150\text{ k}\Omega + 20\text{ k}\Omega$).
* **Electrical Parameters:** $L = 4.80\text{ H}$, $R_{\text{dc}} = 9.50\text{ k}\Omega$, $R_{\text{eddy}} = 110\text{ k}\Omega$, $C_{\text{coil}} = 80\text{ pF}$. Loaded $f_r = 2.4\text{ kHz}$.
* **Acoustic Character:** Immediate pick attack with solid, compressed low-mids ($300\text{--}800\text{ Hz}$) and extended high-mid clarity. The $500\text{k}\Omega$ harness prevents resonant damping, maintaining an open, aggressive transient edge.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 05. `05_vintage_62_p_alnico` (Vintage '62 Split-Coil Alnico V - Tone Open)
* **Archetype:** 1962 Fender Precision with Alnico V Pole Pieces (Tone Wide Open)
* **Coil Model:** Alnico V split-coil ($w = 1.00''$)
* **Control Harness:** Vintage 1962 CTS $250\text{k}\Omega$ volume pot, $250\text{k}\Omega$ tone pot wide open, $47\text{ nF}$ paper-in-oil tone capacitor, no treble bleed.
* **Electrical Parameters:** $L = 3.80\text{ H}$, $R_{\text{dc}} = 10.50\text{ k}\Omega$, $R_{\text{eddy}} = 180\text{ k}\Omega$, $C_{\text{coil}} = 60\text{ pF}$. Loaded $f_r = 2.1\text{ kHz}$, $-3\text{ dB}$ cutoff at $4.0\text{ kHz}$.
* **Acoustic Character:** Lower core eddy-current damping yields an open, touch-sensitive, uncompressed response with organic woody upper-mid bloom and complete harmonic extension.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 05b. `05b_vintage_62_p_22nf` (Vintage '62 Split-P - 22nF ToneStyler)
* **Archetype:** 1962 Fender Precision with Stellartone ToneStyler (22nF Pure Capacitive Shunt)
* **Coil Model:** Alnico V split-coil ($w = 1.00''$)
* **Control Harness:** Vintage 1962 CTS $250\text{k}\Omega$ volume pot, Stellartone ToneStyler rotary switch selecting a precision $22\text{ nF}$ capacitor shunt to ground ($R_{\text{tone}} = 3.3\,\Omega$, zero series wiper damping).
* **Electrical Parameters:** $L = 3.80\text{ H}$, $R_{\text{dc}} = 10.50\text{ k}\Omega$, $R_{\text{tone}} = 3.3\,\Omega$, $C_{\text{tone}} = 22\text{ nF}$. Undamped resonant peak at **$440\text{ Hz}$** (+1.5 dB), $-3\text{ dB}$ cutoff at **$750\text{ Hz}$**.
* **Acoustic Character:** Modern Fender tone capacitor spec: eliminates fret clatter and pick click while preserving high-$Q$ punch in the punchy $440\text{ Hz}$ low-mid register.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 05c. `05c_vintage_62_p_47nf` (Vintage '62 Split-P - 47nF ToneStyler Motown)
* **Archetype:** Vintage 1960s Precision Bass with Stellartone ToneStyler 47nF Pure Capacitive Shunt & Heavy Flatwounds (Jamerson / Motown style)
* **Coil Model:** Alnico V split-coil ($w = 1.00''$)
* **Control Harness:** Vintage CTS $250\text{k}\Omega$ volume pot, Stellartone ToneStyler rotary switch selecting a precision $47\text{ nF}$ paper-in-oil capacitor shunt to ground ($R_{\text{tone}} = 3.3\,\Omega$ contact/lead ESR, zero series wiper resistance damping).
* **Electrical Parameters:** $L = 3.80\text{ H}$, $R_{\text{dc}} = 10.50\text{ k}\Omega$, $R_{\text{eddy}} = 180\text{ k}\Omega$, $C_{\text{coil}} = 60\text{ pF}$, $R_{\text{tone}} = 3.3\,\Omega$, $C_{\text{tone}} = 47\text{ nF}$. Loaded resonant peak at **$450\text{ Hz}$** (+1.2 dB), steep rolloff above $800\text{ Hz}$.
* **Acoustic Character:** Removes fret clatter and transient click above $800\text{ Hz}$ while preserving a punchy resonant low-mid bump at $450\text{ Hz}$. Paired with heavy flatwound string acoustic damping, delivers iconic pillowy Motown thump.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 05d. `05d_vintage_50s_p_100nf` (Vintage '50s Split-P - 100nF ToneStyler)
* **Archetype:** Early 1950s Fender Precision with Stellartone ToneStyler (100nF / 0.1µF Pure Capacitive Shunt)
* **Coil Model:** Alnico V split-coil ($w = 1.00''$)
* **Control Harness:** Vintage 1962 CTS $250\text{k}\Omega$ volume pot, Stellartone ToneStyler rotary switch selecting a precision $100\text{ nF}$ (0.1µF) paper-in-oil / ceramic disc capacitor shunt to ground ($R_{\text{tone}} = 3.3\,\Omega$).
* **Electrical Parameters:** $L = 3.80\text{ H}$, $R_{\text{dc}} = 10.50\text{ k}\Omega$, $R_{\text{tone}} = 3.3\,\Omega$, $C_{\text{tone}} = 100\text{ nF}$. Sub-bass shelf, $-3\text{ dB}$ cutoff at **$240\text{ Hz}$**.
* **Acoustic Character:** Original 1951–1959 Fullerton factory 0.1µF spec: massive low-pass filter concentrating all energy into the sub-bass register, yielding deep Motown / reggae dub thump.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

*(Note: Slot 06 is currently reserved / unassigned.)*

### 07. `07_modern_pj_active` (Modern Active P/J Bass)
* **Archetype:** Sadowsky P/J / Spector NS-2 Active 2-Band P/J
* **Pickup Architecture:** Dual parallel pickups:
  * **Precision Neck:** Modern ceramic split-coil Bartolini 8CBP ($L = 4.80\text{ H}$, E/A @ $139\text{ mm}$, D/G @ $111\text{ mm}$)
  * **Jazz Bridge:** Modern ceramic single-coil Bartolini 9CBJS1 ($L = 3.60\text{ H}$, @ $63.5\text{ mm}$)
* **Control Harness:** Sadowsky/Spector active 2-band preamp buffer ($R_{\text{in}} = 1.0\text{ M}\Omega$, $C_{\text{in}} = 25\text{ pF}$, low-impedance $R_{\text{out}} = 100\,\Omega$). Active EQ provides $+4.0\text{ dB}$ bass boost ($40\text{ Hz}$ shelf) and $+4.0\text{ dB}$ treble boost ($4.0\text{ kHz}$ shelf).
* **Electrical Parameters:** Active buffer isolates both pickups from cable capacitance ($750\text{ pF}$). Raw ceramic resonance sits in the high-clarity $7.6\text{ kHz}$ region.
* **Acoustic Character:** Thunderous modern low-end weight with zero muddiness, balanced against articulate, clanky bridge bite. Cuts through dense modern pop, gospel, and metal mixes.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 08. `08_vintage_pj_passive` (Vintage '80s Passive P/J Bass)
* **Archetype:** 1980s Fender Jazz Bass Special / Yamaha BB3000 Style Passive P/J
* **Pickup Architecture:** Dual parallel pickups:
  * **Precision Neck:** Vintage '62 Alnico V split-coil ($L = 3.80\text{ H}, R_{\text{dc}} = 10.50\text{ k}\Omega$, E/A @ $139\text{ mm}$, D/G @ $111\text{ mm}$)
  * **Jazz Bridge:** Vintage 60s Alnico V single-coil ($L = 3.60\text{ H}, R_{\text{dc}} = 7.80\text{ k}\Omega$, @ $63.5\text{ mm}$)
* **Control Harness:** Authentic passive dual volume harness ($2\times 250\text{k}\Omega$ pots in parallel = $125\text{k}\Omega$ net load), $250\text{k}\Omega$ tone pot, $47\text{ nF}$ capacitor, no treble bleed.
* **Electrical Parameters:** Dual parallel SPICE branches; composite $L_{\text{eq}} = 1.85\text{ H}$, $R_{\text{dc}} = 4.48\text{ k}\Omega$, $R_{\text{eddy}} = 74\text{ k}\Omega$, $C_{\text{coil}} = 130\text{ pF}$. Loaded $f_r = 2.8\text{ kHz}$.
* **Acoustic Character:** Classic '80s rock/punk/funk thump (Duff McKagan / Michael Anthony style). Warm, woody, mid-forward punch with gentle high-end roll-off.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 09. `09_stingray_mm_parallel` (Music Man Active Dual-Coil Parallel)
* **Archetype:** Music Man StingRay 4-String Active Dual-Coil Humbucker
* **Coil Model:** Dual-coil humbucker ($w = 1.50''$, $d = 0.75''$) wired in parallel
* **Control Harness:** Authentic Music Man active 2-band op-amp preamp buffer ($R_{\text{in}} = 1.0\text{ M}\Omega$, $C_{\text{in}} = 25\text{ pF}$, low-impedance $R_{\text{out}} = 100\,\Omega$). Active EQ provides $+5.0\text{ dB}$ bass boost ($50\text{ Hz}$ shelf) and $+3.0\text{ dB}$ treble boost ($7.0\text{ kHz}$ shelf).
* **Electrical Parameters:** The active buffer isolates the coils from the $750\text{ pF}$ instrument cable. Pickup self-capacitance ($130\text{ pF}$) plus input capacitance ($25\text{ pF}$) places raw coil resonance at $7.2\text{ kHz}$.
* **Acoustic Character:** Dual-coil phase comb cancellation notch at $2.5\text{ kHz}$ combined with authoritative active bass punch and signature metallic treble clank.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Dual-Coil Mode - Push/Pull Up).

### 10. `10_rickenbacker_bridge_hpf` (Rickenbacker 4003 Bridge with 4.7nF HPF)
* **Archetype:** Rickenbacker 4001/4003 Bridge Pickup with Vintage High-Pass Push-Pull
* **Coil Model:** High-output single coil with $4.7\text{ nF}$ series capacitor
* **Control Harness:** Factory Rickenbacker $330\text{k}\Omega$ volume pot, $330\text{k}\Omega$ tone pot, $47\text{ nF}$ tone cap, $4.7\text{ nF}$ vintage series capacitor.
* **Electrical Parameters:** $L = 3.80\text{ H}$, $R_{\text{dc}} = 8.40\text{ k}\Omega$, $C_{\text{series}} = 4.7\text{ nF}$, $C_{\text{coil}} = 90\text{ pF}$. Loaded $f_r = 2.2\text{ kHz}$.
* **Acoustic Character:** The series capacitor acts as a high-pass filter, rolling off sub-bass below $150\text{ Hz}$ while focusing midrange punch ($1.5\text{--}2.5\text{ kHz}$). Produces an aggressive, gritty pick attack.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Single-Coil Mode - Push/Pull Down).

### 11. `11_pmm_hybrid_series` (P/MM Hybrid Series Sum)
* **Archetype:** Custom P/MM Hybrid in Series
* **Pickup Architecture:** Dual series pickups:
  * **Precision Neck:** Split-coil Bartolini 8CBP ($L = 4.80\text{ H}$)
  * **Music Man Bridge:** Dual-coil humbucker MM4CBC ($L = 2.40\text{ H}$)
* **Control Harness:** Modern $500\text{k}\Omega$ volume pot, $500\text{k}\Omega$ tone pot, $47\text{ nF}$ tone capacitor.
* **Electrical Parameters:** Series-connected SPICE stages; total series $L_{\text{ser}} = 7.20\text{ H}$, $R_{\text{dc}} = 14.10\text{ k}\Omega$, $R_{\text{eddy}} = 250\text{ k}\Omega$, $C_{\text{coil}} = 50\text{ pF}$. Loaded $f_r = 1.6\text{ kHz}$.
* **Acoustic Character:** Series inductance addition yields a large $+5.8\text{ dB}$ signal boost and a dense, forward $1.6\text{ kHz}$ resonant center. Fills out sparse instrument arrangements with commanding low-mids.
* **32" Bass Setting:** ABCX Blend at **Center Detent (50/50)** (MMTWX in Dual-Coil Mode - Push/Pull Up).

### 12. `12_mudbucker_ultra_series` (Ultra-High Inductance Overwound Series)
* **Archetype:** Gibson EB-0 Mudbucker / Overwound Series Dual-Coil
* **Coil Model:** Extreme dual-coil overwound series network
* **Control Harness:** Gibson-spec $500\text{k}\Omega$ volume pot, $500\text{k}\Omega$ tone pot, $22\text{ nF}$ tone capacitor.
* **Electrical Parameters:** $L = 14.40\text{ H}$, $R_{\text{dc}} = 27.90\text{ k}\Omega$, $R_{\text{eddy}} = 80\text{ k}\Omega$, $C_{\text{coil}} = 80\text{ pF}$. Loaded $f_r = 1.2\text{ kHz}$.
* **Acoustic Character:** Resonant peak pulls down to $1.2\text{ kHz}$, naturally rolling off high frequencies. Deep, massive low end with zero high-frequency fizz, ideal for heavy fuzz and saturated drive stages.
* **32" Bass Setting:** ABCX Blend **100% Neck (PX/PCSX)**.

### 13. `13_dingwall_multiscale_bridge` (Fanned-Fret Multi-Scale Bridge)
* **Archetype:** Dingwall NG Multi-Scale Angled Bridge Position
* **Coil Model:** Dual-coil humbucker in parallel positioned $48.0\text{ mm}$ from bridge
* **Control Harness:** Dingwall-spec $500\text{k}\Omega$ volume pot, $500\text{k}\Omega$ tone pot, $47\text{ nF}$ tone capacitor.
* **Electrical Parameters:** $L = 2.30\text{ H}$, $R_{\text{dc}} = 4.40\text{ k}\Omega$, $R_{\text{eddy}} = 150\text{ k}\Omega$, $C_{\text{coil}} = 120\text{ pF}$. Loaded $f_r = 3.4\text{ kHz}$.
* **Acoustic Character:** 34"-37" fanned-fret wave-speed scaling with high string tension, angled bridge sweet spot ($48.0\text{ mm}$), FD3 dual-coil parallel resonance ($3.4\text{ kHz}$), and stainless-steel string harmonic extension.
* **32" Bass Setting:** ABCX Blend **100% Bridge** (MMTWX in Dual-Coil Mode - Push/Pull Up).

### 14. `14_upright_bridge_transducer` (Upright Acoustic Bridge Transducer)
* **Archetype:** Direct Bridge Force Transducer on 3/4 Double Bass (41.5" Scale, Underwood / David Gage Realist style)
* **Target String Archetype:** 3/4 Double Bass spiral rope-core strings (`double_bass_spirocore`, $265\text{ lbs}$ tension, coupled spruce soundboard damping)
* **Sensor Model:** Direct bridge saddle force sensor ($x = 5.0\text{ mm}$) with velocity-to-force leaky integration ($+6\text{ dB/oct}$ from $70\text{ Hz}$ to $250\text{ Hz}$)
* **Dynamic Compliance:** Soft-knee bridge rocking saturation ($V_{\text{sat}} \cdot \tanh(v / V_{\text{sat}})$), dynamically scaled for lower-tension strings ($V_{\text{sat}} = 0.336\text{ V}$ on 32" fretless with La Bella LTF vs $0.42\text{ V}$ baseline)
* **Anti-Double-Damping:** Automatically matches source string damping ($f_{\text{damp, src}}$) to target double-bass damping ($f_{\text{damp, tgt}}$). When evaluated from flatwound instruments (La Bella LTF), the filter avoids double-muffling the high frequencies while preserving woody bridge bite.
* **Electrical Parameters:** Pure capacitive piezo sensor ($C_{\text{piezo}} = 1.2\text{ nF}$), direct $100\text{ M}\Omega$ buffer, $15\text{ nF}$ subsonic rumble decoupling @ $32\text{ Hz}$
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
| **`01_modern_jazz_active`** | J-Pair Virtual Center | $86.8\text{ mm}$ | $+9.3\text{ mm}\ (+0.37'')$ | De-humbuck aperture, mild forward tilt, active 2-band boost |
| **`02_jazz_bass_pair`** | J-Pair Virtual Center | $86.8\text{ mm}$ | $+9.3\text{ mm}\ (+0.37'')$ | De-humbuck aperture, mild forward tilt |
| **`02b_jazz_bass_pair_22nf`**| J-Pair Virtual Center | $86.8\text{ mm}$ | $+9.3\text{ mm}\ (+0.37'')$ | De-humbuck aperture, mild forward tilt, 22nF ToneStyler |
| **`03_jazz_bridge_60s`** | MMTWX Bridge Coil (JB) | $50.8\text{ mm}$ | $-26.7\text{ mm}\ (-1.05'')$ | De-humbuck aperture, tighter bridge bite tilt |
| **`04_modern_p_ceramic`** | Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | $+2.7\text{ dB}$ low boost, tames bridge bite |
| **`05_vintage_62_p_alnico`**| Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | $+2.7\text{ dB}$ low boost, smooth woody rolloff |
| **`05b_vintage_62_p_22nf`** | Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | $+2.7\text{ dB}$ low boost, 22nF ToneStyler 440 Hz punch |
| **`05c_vintage_62_p_47nf`** | Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | 47nF ToneStyler Motown flatwound deep sub-thump |
| **`05d_vintage_50s_p_100nf`**| Reverse PX Split Center | $122.8\text{ mm}$ | $+45.3\text{ mm}\ (+1.78'')$ | 100nF ToneStyler 1950s deep sub-bass dub thump |
| **`07_modern_pj_active`** | P/J Virtual Center | $86.8\text{ mm}$ | $+9.3\text{ mm}\ (+0.37'')$ | Hybrid aperture mix, active 2-band boost, wideband shimmer |
| **`08_vintage_pj_passive`** | P/J Virtual Center | $86.8\text{ mm}$ | $+9.3\text{ mm}\ (+0.37'')$ | Hybrid aperture mix, vintage Alnico dual-volume warmth |
| **`09_stingray_mm_parallel`**| MMTWX Centerline | $62.2\text{ mm}$ | $-15.3\text{ mm}\ (-0.60'')$ | Preserves dual-coil comb, active 2-band boost |
| **`10_rickenbacker_bridge_hpf`** | Bridge Clank Position | $50.8\text{ mm}$ | $-26.7\text{ mm}\ (-1.05'')$ | Series HPF engaged, maximum pick bite |
| **`11_pmm_hybrid_series`**| Dual Series Center | $92.5\text{ mm}$ | $+15.0\text{ mm}\ (+0.59'')$ | Series inductance boost, thick low-mids |
| **`12_mudbucker_ultra_series`**| Deep Series Center | $92.5\text{ mm}$ | $+15.0\text{ mm}\ (+0.59'')$ | Extreme $14.4\text{ H}$ low-frequency foundation |
| **`13_dingwall_multiscale_bridge`**| Angled Sweet Spot | $48.0\text{ mm}$ | $-29.5\text{ mm}\ (-1.16'')$ | High string wave speed, metallic clank |
| **`14_upright_bridge_transducer`**| Bridge Transducer Datum | $5.0\text{ mm}$ | $-72.5\text{ mm}\ (-2.85'')$ | Bridge force integration, de-comb, body bloom |
