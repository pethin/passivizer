# Darkglass Anagram Integration & Preset Architecture

This document provides a guide for deploying **Passivizer** IRs and NAM models onto the **Darkglass Anagram** workstation.

---

## 1. Optimal Block Layout

The Darkglass Anagram allows up to 24 simultaneous blocks in series or parallel. To maintain authentic analog behavior, the Passivizer model should always occupy **Block 1 (immediately following the hardware input stage)**:

```
[Hardware 1/4" Input]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 1: Passivizer Pickup Emulation                   │
│   ├── Choice A: NAM Preamp ("Bartolini_8CBP.nam")      │
│   └── Choice B: IR Loader ("EMG_to_Bartolini_8CBP.wav")│
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 2: Darkglass Drive / Preamp Engine               │
│   ├── Microtubes B7K Ultra / Vintage Microtubes        │
│   └── Alpha·Omega / Microtubes Infinity                │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 3: Speaker Cabinet Impulse Response (Cab IR)     │
│   └── Ampeg 8x10, Darkglass 4x10, or custom cab IR     │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 4+: Time-Based Effects & Output Processing       │
│   └── Compression, Reverb, Chorus, Global EQ / Limiter │
└────────────────────────────────────────────────────────┘
          │
          ▼
[Stereo XLR Outputs to FOH / USB-C Audio]
```

> [!IMPORTANT]
> **Why Block 1?**
> Overdrive and fuzz circuits react dramatically to input impedance and pickup resonant peaks. By placing the Passivizer model in Block 1, the Darkglass drive engines (B7K, Alpha·Omega, etc.) distort the *passive* resonant peak and rolled-off top end, rather than distorting the raw, ultra-wideband active EMG signal.

---

## 2. Gain Staging & Volume Normalization

One of the greatest annoyances of physical passive multi-coil basses is **level disparity**:
* Splitting an MM humbucker to a single-coil drops volume by $\sim 3\text{--}4\text{ dB}$.
* Switching into Series boosts volume by $+4\text{ to }+6\text{ dB}$, often pushing analog preamps into unwanted clipping.

### In the Anagram:
Inside your Anagram presets, use the Block 1 output level trim to normalize all 10 voices to an identical target RMS level:

| Profile | Raw Circuit Offset | Recommended Anagram Block 1 Trim |
| :--- | :--- | :--- |
| **`01_j_jazz_atelier_pair`** | $-0.5\text{ dB}$ | $+0.5\text{ dB}$ |
| **`02_jaco_fusion_bridge`** | $-2.5\text{ dB}$ | $+2.5\text{ dB}$ (Brings solo single-coil to parity) |
| **`03_jrock_modern_p`** | $+1.5\text{ dB}$ | $0.0\text{ dB}$ (Reference Baseline) |
| **`04_vintage_62_alnico_p`** | $+0.5\text{ dB}$ | $+1.0\text{ dB}$ |
| **`05_motown_neo_soul_dub`** | $-1.0\text{ dB}$ | $+1.0\text{ dB}$ |
| **`06_studio_workhorse_pj`** | $+0.8\text{ dB}$ | $+0.5\text{ dB}$ |
| **`07_jmetal_prog_stingray`**| $0.0\text{ dB}$ | $+1.5\text{ dB}$ |
| **`08_prog_rick_clank`** | $-1.5\text{ dB}$ | $+2.0\text{ dB}$ (Compensates for series HPF cut) |
| **`09_power_trio_bulldozer`**| $+5.8\text{ dB}$ | $-4.0\text{ dB}$ (Prevents clipping drive blocks) |
| **`10_stoner_doom_mudbucker`**| $+6.2\text{ dB}$ | $-4.5\text{ dB}$ (Controls high-inductance surge) |

---

## 3. Footswitching & Preset Architecture (3 Core Banks)

The Darkglass Anagram features three tactile footswitches and a 7-inch touchscreen. Group the 10 voices into **three dedicated 3-button banks** for seamless genre switching on stage:

### Bank 1: Anisong, J-Jazz & Modern Slap
* **Footswitch A: "Atelier Slap"**
  * Block 1: `01_j_jazz_atelier_pair.nam`
  * Block 2: Clean Studio Preamp (subtle $1\text{ kHz}$ scoop)
  * Block 3: Ported 4x10 Cab IR
* **Footswitch B: "J-Rock Pick"**
  * Block 1: `03_jrock_modern_p.nam`
  * Block 2: Vintage Microtubes (aggressive pick bite)
  * Block 3: Sealed 8x10 Cab IR
* **Footswitch C: "J-Fusion Solo"**
  * Block 1: `02_jaco_fusion_bridge.nam`
  * Block 2: Mild optical compression + mid boost @ $1.2\text{ kHz}$
  * Block 3: 2x10 Ported Cab IR

### Bank 2: Heavy Rock, Prog & J-Metal
* **Footswitch A: "Prog StingRay"**
  * Block 1: `07_jmetal_prog_stingray.nam`
  * Block 2: Microtubes B7K Ultra (aggressive high-mid grind)
  * Block 3: Darkglass 4x10 Cab IR
* **Footswitch B: "Rick Clank"**
  * Block 1: `08_prog_rick_clank.nam`
  * Block 2: Alpha·Omega (ferocious dual-drive pick bite)
  * Block 3: 8x10 High-Output Cab IR
* **Footswitch C: "Stoner Fuzz Doom"**
  * Block 1: `10_stoner_doom_mudbucker.nam`
  * Block 2: Darkglass Duality / Fuzz engine (thick saturated doom)
  * Block 3: 2x15 Sub-Heavy Cab IR

### Bank 3: Vintage Foundations & Everyday Studio
* **Footswitch A: "Studio P/J"**
  * Block 1: `06_studio_workhorse_pj.nam`
  * Block 2: Clean Tube Preamp (warm, transparent)
  * Block 3: Ampeg 8x10 Sealed Cab IR
* **Footswitch B: "'62 Alnico P"**
  * Block 1: `04_vintage_62_alnico_p.nam`
  * Block 2: Vintage Microtubes (mild warm tube saturation)
  * Block 3: Ampeg B-15 Flip-Top Cab IR
* **Footswitch C: "Motown / Dub"**
  * Block 1: `05_motown_neo_soul_dub.nam`
  * Block 2: Tube compressor (slow attack, fat sustain)
  * Block 3: 1x15 Sealed Vintage Cab IR

---

## 4. Importing Files via Darkglass Suite

1. Connect your Darkglass Anagram to your Mac via USB-C.
2. Launch the **Darkglass Suite** application.
3. **For IRs:** Navigate to the **IR Manager** tab, drag and drop `irs/*.wav` into user slots 1–10.
4. **For NAM Models:** Navigate to the **NAM / Neural Capture** library, drag and drop `models/*.nam` into your preset bank.
5. In the touchscreen interface, tap Block 1, select your custom NAM or IR file, and save your preset.
