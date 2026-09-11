# Darkglass Anagram Integration & Routing Architecture

This document provides a reference for deploying **Allomorph** IRs and NAM models onto the **Darkglass Anagram** pedalboard.

---

## 1. Optimal Block Layout (Architecture C Two-Stage Pipeline)

The Darkglass Anagram allows up to 24 simultaneous blocks in series or parallel. In Architecture C, Allomorph divides pickup modeling into two dedicated blocks:

```
[Hardware 1/4" Input]
          │  Peak calibrated to -3.0 dBFS on Anagram hardware meter
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 1: Frontend Deconvolution (Minimum-Phase IR)     │  ◄── IR Loader Block (0% CPU, 0 ms latency)
│   └── "30in_emg_mmtw_dual.wav" (2048 taps)             │      Matches your physical pickup switch position!
│   • Inverts source RLC, pot/cable load, & aperture sinc│
│   • Normalizes to Canonical Intermediate Baseline      │
└────────────────────────────────────────────────────────┘
          │ (Canonical Intermediate @ 93.5mm: -1.5 dBFS Peak / -16.5 dBFS RMS)
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 2: Target Voicing (A2-Lite NAM Preamp)           │  ◄── NAM Preamp Block (1 of 9 slots used)
│   ├── Clean Pack:            "cln_04_modern_p.nam"     │      (0% Saturation / High Headroom)
│   ├── Standard Dynamic Pack: "std_04_modern_p.nam"     │      (Standard Give & Bloom / Nominal Saturation)
│   └── Hot Rod Pack:          "hot_04_modern_p.nam"     │      (175% Overwound Drive Pre-Conditioner)
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 3: Darkglass Drive / Preamp Engine               │  ◄── 8 Neural Slots Free!
│   ├── Microtubes B7K Ultra / Vintage Microtubes        │
│   └── Alpha·Omega / Microtubes Infinity                │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 4: Speaker Cabinet Impulse Response (Cab IR)     │
│   └── Ampeg 8x10, Darkglass 4x10, or custom cab IR     │
└────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 5+: Time-Based Effects & Output Processing       │
│   └── Compression, Reverb, Chorus, Global EQ / Limiter │
└────────────────────────────────────────────────────────┘
          │
          ▼
[Stereo XLR Outputs to FOH / USB-C Audio]
```

> [!IMPORTANT]
> **The Golden Rule: Physical Knobs at 100% Wide Open**
> For Block 1 to perform an exact mathematical deconvolution ($0.00\text{ dB}$ flat intermediate baseline), keep your physical bass's volume and tone knobs completely wide open ($100\%$). Tone cap roll-offs (e.g. 22nF, 47nF Motown, 100nF Dub) and loading are selected in Block 2.

> [!NOTE]
> **Why Two Stages?**
> Deconvolving your instrument's linear circuit and spatial aperture in Block 1 requires 0% neural CPU. This leaves 8 of the Anagram's 9 neural slots completely free for multiple drive engines, amp captures, or polyphonic synths.

---

## 2. Hardware Input Gain Staging & Headroom Calibration

Active 18V EMG pickups provide immense dynamic headroom, delivering up to $+14\text{ dBu}$ of peak voltage on aggressive slap or heavy finger plucks. To preserve 100% linear conversion before neural processing in **Block 1 (Allomorph NAM)**:

1. **Adjust the Anagram Global Input Level / Pad:**
   * Navigate to the Anagram global I/O settings.
   * Play your most aggressive thumb slap and heavy finger strokes on the lowest string (Low B or E).
   * Adjust the analog input gain so that maximum peaks register cleanly between **$-6.0\text{ and } -3.0\text{ dBFS}$** on the hardware input meter.
2. **Prevent Hardware A/D Converter Clipping:**
   * Setting the input gain too hot will hard-clip the pedalboard's physical analog-to-digital converters before Block 1, introducing harsh inter-sample distortion that the NAM model cannot undo.
   * Setting the input gain too low will lower signal-to-noise ratio and prevent the model from engaging dynamic Alnico magnetic saturation.
3. **Downstream Processing in Block 2 (Preamp/Drive):**
   * Keeping input peaks at $-6.0\text{ to } -3.0\text{ dBFS}$ ensures the signal entering Block 1 mirrors the calibrated $[-1.0, +1.0]$ float window used during model training, allowing the downstream Darkglass drive in Block 2 (Microtubes B7K, Vintage Ultra) to distort organically.

---

## 3. Block 1 Level Trim & Perceived Loudness Matching

Passive and active multi-coil instruments often present notable level disparities:
* Splitting an MM humbucker to a single coil drops output level by $\sim 3\text{--}4\text{ dB}$.
* Switching pickups into Series configuration produces an inductive voltage surge of $+4\text{ to }+6\text{ dB}$.
* Active preamps provide $+3\text{ to }+5\text{ dB}$ of low/high shelving boost.

In your presets, use the Block 1 output level trim to normalize all voices to an even target RMS level:

| Profile ID | Pickup Configuration | Raw Offset | Recommended Block 1 Trim |
| :--- | :--- | :--- | :--- |
| **`01_modern_jazz_active`** | Modern Active Jazz (Sadowsky 2-Band) | $+2.0\text{ dB}$ | $-2.0\text{ dB}$ (Controls active boost) |
| **`02_jazz_bass_pair`** | Vintage 60s Jazz Bass Pair (Parallel) | $-0.5\text{ dB}$ | $+0.5\text{ dB}$ |
| **`02b_jazz_bass_pair_22nf`** | Vintage 60s J-Pair (22nF ToneStyler) | $-0.5\text{ dB}$ | $+0.5\text{ dB}$ |
| **`02c_jazz_bridge_growl_bias`** | Jaco Bridge-Biased Jazz Pair (100%/75%) | $-1.2\text{ dB}$ | $+1.2\text{ dB}$ (Compensates neck pot decoupling) |
| **`03_jazz_bridge_60s`** | 60s Jazz Bridge Single-Coil | $-2.5\text{ dB}$ | $+2.5\text{ dB}$ (Compensates single-coil drop) |
| **`04_modern_p_ceramic`** | Modern Split-Coil P (Ceramic 500k) | $+1.5\text{ dB}$ | $0.0\text{ dB}$ (Reference Baseline) |
| **`05_vintage_62_p_alnico`** | Vintage '62 Split-Coil P (Alnico V 250k) | $+0.5\text{ dB}$ | $+1.0\text{ dB}$ |
| **`05b_vintage_62_p_22nf`** | Vintage '62 P (22nF ToneStyler) | $+0.0\text{ dB}$ | $+1.0\text{ dB}$ |
| **`05c_vintage_62_p_47nf`** | Vintage P (47nF ToneStyler Motown) | $-1.0\text{ dB}$ | $+1.0\text{ dB}$ |
| **`05d_vintage_50s_p_100nf`** | Vintage '50s P (100nF ToneStyler) | $-1.5\text{ dB}$ | $+1.5\text{ dB}$ |
| **`07_modern_pj_active`** | Modern Active P/J (Sadowsky/Spector 2-Band) | $+2.0\text{ dB}$ | $-2.0\text{ dB}$ (Controls active boost) |
| **`08_vintage_pj_passive`** | Vintage '80s Passive P/J (Dual-Volume) | $+0.5\text{ dB}$ | $+0.5\text{ dB}$ |
| **`09_stingray_mm_parallel`** | Music Man MM (Active 2-Band Humbucker)| $+2.5\text{ dB}$ | $-1.5\text{ dB}$ (Controls active boost) |
| **`09b_stingray_mm_series`** | Music Man MM (Series Humbucker Mid-Punch)| $+4.8\text{ dB}$ | $-3.5\text{ dB}$ (Controls series boost surge) |
| **`10_rickenbacker_bridge_hpf`**| Rickenbacker Bridge (4.7nF HPF) | $-1.5\text{ dB}$ | $+2.0\text{ dB}$ (Compensates series HPF cut) |
| **`11_pmm_hybrid_series`** | P/MM Hybrid (Series Sum 500k) | $+5.8\text{ dB}$ | $-4.0\text{ dB}$ (Prevents clipping downstream drives)|
| **`12_mudbucker_ultra_series`**| Mudbucker Ultra Series | $+6.2\text{ dB}$ | $-4.5\text{ dB}$ (Controls high-inductance surge) |
| **`13_dingwall_multiscale_bridge`**| Dingwall Multi-Scale Bridge | $+1.0\text{ dB}$ | $+0.5\text{ dB}$ |
| **`14_upright_bridge_transducer`**| Upright Acoustic Bridge Transducer | $0.0\text{ dB}$ | $0.0\text{ dB}$ (Transparent unity acoustic baseline) |
| **`15_source_direct`** | Source Direct (Dynamic Studio DI) | $0.0\text{ dB}$ | $0.0\text{ dB}$ (Transparent unity gain) |
| **`16_active_character`** | Studio Active Buffer (Zero Cable Loading) | $+0.5\text{ dB}$ | $-0.5\text{ dB}$ (Unity gain buffer) |

---

## 4. Footswitching & Bank Organization

Group the pickup profiles into dedicated 3-button banks on the Anagram hardware:

### Bank 1: Modern & Vintage Jazz Foundations
* **Footswitch A:** `01_modern_jazz_active.nam` (Modern Active Jazz - Sadowsky 2-Band)
* **Footswitch B:** `02_jazz_bass_pair.nam` (Vintage 60s Jazz Bass Pair)
* **Footswitch C:** `03_jazz_bridge_60s.nam` (60s Jazz Bridge)

### Bank 2: Precision Bass Foundations
* **Footswitch A:** `04_modern_p_ceramic.nam` (Modern Split-Coil P - Boutique 500k)
* **Footswitch B:** `05_vintage_62_p_alnico.nam` (Vintage '62 P Alnico V - Tone Open)
* **Footswitch C:** `05c_vintage_62_p_47nf.nam` (P-Bass 47nF ToneStyler Motown Flatwound)

### Bank 3: P/J Hybrid & Music Man Active
* **Footswitch A:** `07_modern_pj_active.nam` (Modern Active P/J - Sadowsky/Spector 2-Band)
* **Footswitch B:** `08_vintage_pj_passive.nam` (Vintage '80s Passive P/J)
* **Footswitch C:** `09_stingray_mm_parallel.nam` (Music Man Active 2-Band Humbucker Parallel)

### Bank 4: Series Punch & Maximum Inductance
* **Footswitch A:** `09b_stingray_mm_series.nam` (Music Man MM Series Humbucker Mid-Punch)
* **Footswitch B:** `11_pmm_hybrid_series.nam` (P/MM Series Sum)
* **Footswitch C:** `12_mudbucker_ultra_series.nam` (Gibson Mudbucker Series)

### Bank 5: Multi-Scale, Acoustic & Vintage Filtered
* **Footswitch A:** `10_rickenbacker_bridge_hpf.nam` (Rickenbacker 4.7nF HPF)
* **Footswitch B:** `13_dingwall_multiscale_bridge.nam` (Dingwall Multi-Scale Bridge)
* **Footswitch C:** `14_upright_bridge_transducer.nam` (Upright Acoustic Bridge Transducer)

### Bank 6: Pure Dynamics & Specialized Voicings
* **Footswitch A:** `02c_jazz_bridge_growl_bias.nam` (Jaco Bridge-Biased Vocal Growl)
* **Footswitch B:** `std_15_src_direct.nam` (Source Direct - Dynamic Studio DI)
* **Footswitch C:** `16_active_character.nam` (Active Studio Buffer - Zero Cable Loading)

---

## 4. Importing Files via Darkglass Suite

1. Connect your Darkglass Anagram to your computer via USB-C.
2. Open the **Darkglass Suite** application.
3. Navigate to the **NAM / Neural Capture** library.
4. Drag and drop trained `models/*.nam` captures into your user model library.
5. In your preset chain on the pedalboard, assign **Block 1** to your imported NAM capture.

---

## 5. Acoustic Upright Dual-Stage Architecture (Block 1 NAM + Block 3 3 Sigma IR)

When targeting an authentic upright double bass tone from a fretless electric bass (such as the 32" Fretless strung with **La Bella Low Tension Flats**), Allomorph splits the acoustic transformation into two specialized stages:

```
[32" Fretless Bass w/ La Bella LTF]
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ Block 1: Allomorph NAM (`14_upright_bridge_transducer`)│
│   • Mathematical de-combing of EMG spatial aperture   │
│   • Leaky velocity-to-force integration (+6 dB/oct tilt)│
│   • Non-linear soft-knee bridge compliance (tanh)      │
│   • Subsonic stage rumble filter (32 Hz)               │
│   • Anti-double-damping deconvolution for flatwounds   │
└────────────────────────────────────────────────────────┘
                 │ (Pure simulated Realist/Underwood bridge force signal)
                 ▼
┌────────────────────────────────────────────────────────┐
│ Block 2: Transparent Acoustic Preamp / Optical Comp    │
│   • Subtle optical leveling (2:1 ratio)                │
└────────────────────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ Block 3: Cab IR Loader (3 Sigma Upright Bass IR)       │
│   • Full 3/4 acoustic body & spruce soundboard cavity  │
│   • Helmholtz air resonance (~60 Hz)                   │
└────────────────────────────────────────────────────────┘
                 │
                 ▼
[Stereo XLR Outputs to FOH / Audio Interface]
```

### Why Both Blocks Are Necessary:
1. **An IR is Linear Time-Invariant (LTI):** It cannot deconvolve magnetic pickup comb notches, nor can it replicate the non-linear mechanical rocking of a double bass bridge under pizzicato attack. Feeding electric magnetic pickups straight into an acoustic IR sounds like an electric bass inside a hollow box.
2. **Block 1 Converts Pickup Physics:** Allomorph's NAM model transforms the magnetic velocity-sensing signal into a mechanical bridge force sensor, complete with dynamic compliance compression.
3. **Block 3 Radiates the Soundboard:** The 3 Sigma IR receives the exact force signal it was designed for, radiating it through a spruce top and resonant double-bass body.
4. **Anti-Double-Damping:** Because the 32" fretless is strung with La Bella Low Tension Flats, Allomorph's differential string engine automatically adjusts its acoustic damping curve, preventing the dull, muffled tone that occurs when a static acoustic low-pass filter is applied to already-dark flatwound strings.

---

## 6. Future Milestone: Native Anagram Marketplace Block

While Allomorph currently deploys via the Anagram's stock Neural Amp Loader block, an upcoming roadmap goal is releasing an official **Anagram Marketplace Custom Block** (`marketplace.anagram.shop`):
* **All-in-One Voice Selector:** Instant rotary switching across all 21 pickup topologies and acoustic transducers directly within a single block.
* **Integrated Gain Normalization:** Automatically balances active boost, series boost, and single-coil level drop under the hood to ensure unity gain into Block 2.
* **Dynamic Control Emulation:** Real-time on-screen controls for volume pot loading ($500\text{ k}\Omega$ vs. $250\text{ k}\Omega$), active preamp boost, treble bleed networks, and cable capacitance ($750\text{ pF}$) loading.
