# Darkglass Anagram Integration & Routing Architecture

This document provides a reference for deploying **Passivizer** IRs and NAM models onto the **Darkglass Anagram** pedalboard.

---

## 1. Optimal Block Layout

The Darkglass Anagram allows up to 24 simultaneous blocks in series or parallel. To maintain authentic passive circuit loading behavior, the Passivizer model should always occupy **Block 1 (immediately following the hardware input stage)**:

```
[Hardware 1/4" Input]
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ Block 1: Passivizer Pickup Emulation (NAM Preamp)      │
│   └── Neural Model: "03_modern_p_ceramic.nam" (A2)     │
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
> Overdrive, distortion, and preamp stages react directly to the input frequency envelope and pickup resonant peaks. By placing the Passivizer NAM model in Block 1, subsequent drive engines distort the *passive* resonant peak and roll-off, rather than distorting an unshaped wideband active signal.

---

## 2. Gain Staging & Volume Normalization

Passive multi-coil instruments often present notable level disparities:
* Splitting an MM humbucker to a single coil drops output level by $\sim 3\text{--}4\text{ dB}$.
* Switching pickups into Series configuration produces an inductive voltage surge of $+4\text{ to }+6\text{ dB}$.

In your presets, use the Block 1 output level trim to normalize all voices to an even target RMS level:

| Profile ID | Pickup Configuration | Raw Offset | Recommended Block 1 Trim |
| :--- | :--- | :--- | :--- |
| **`01_jazz_bass_pair`** | Jazz Bass Pair (Parallel) | $-0.5\text{ dB}$ | $+0.5\text{ dB}$ |
| **`02_jazz_bridge_70s`** | 70s Jazz Bridge Single-Coil | $-2.5\text{ dB}$ | $+2.5\text{ dB}$ (Compensates single-coil drop) |
| **`03_modern_p_ceramic`** | Modern Split-Coil P (Ceramic) | $+1.5\text{ dB}$ | $0.0\text{ dB}$ (Reference Baseline) |
| **`04_vintage_62_p_alnico`** | Vintage '62 Split-Coil P (Alnico V) | $+0.5\text{ dB}$ | $+1.0\text{ dB}$ |
| **`05_p_bass_47nf_rolloff`** | Split-Coil P (47nF Tone Rolloff) | $-1.0\text{ dB}$ | $+1.0\text{ dB}$ |
| **`06_pj_hybrid_parallel`** | P/J Hybrid (Parallel) | $+0.8\text{ dB}$ | $+0.5\text{ dB}$ |
| **`07_stingray_mm_parallel`** | Music Man MM (Parallel Humbucker)| $0.0\text{ dB}$ | $+1.5\text{ dB}$ |
| **`08_rickenbacker_bridge_hpf`**| Rickenbacker Bridge (4.7nF HPF) | $-1.5\text{ dB}$ | $+2.0\text{ dB}$ (Compensates series HPF cut) |
| **`09_pmm_hybrid_series`** | P/MM Hybrid (Series Sum) | $+5.8\text{ dB}$ | $-4.0\text{ dB}$ (Prevents clipping downstream drives)|
| **`10_mudbucker_ultra_series`**| Mudbucker Ultra Series | $+6.2\text{ dB}$ | $-4.5\text{ dB}$ (Controls high-inductance surge) |
| **`11_dingwall_multiscale_bridge`**| Dingwall Multi-Scale Bridge | $+1.0\text{ dB}$ | $+0.5\text{ dB}$ |
| **`12_upright_bridge_transducer`**| Upright Acoustic Bridge Transducer | $0.0\text{ dB}$ | $0.0\text{ dB}$ (Transparent unity acoustic baseline) |

---

## 3. Footswitching & Bank Organization

Group the pickup profiles into dedicated 3-button banks on the Anagram hardware:

### Bank 1: Single-Coil & Split Foundations
* **Footswitch A:** `01_jazz_bass_pair.nam` (Jazz Bass Pair)
* **Footswitch B:** `03_modern_p_ceramic.nam` (Modern Split-Coil P)
* **Footswitch C:** `02_jazz_bridge_70s.nam` (70s Jazz Bridge)

### Bank 2: Dual-Coil & Series Topologies
* **Footswitch A:** `07_stingray_mm_parallel.nam` (Music Man Parallel Humbucker)
* **Footswitch B:** `09_pmm_hybrid_series.nam` (P/MM Series Sum)
* **Footswitch C:** `10_mudbucker_ultra_series.nam` (Mudbucker Series)

### Bank 3: Vintage & Filtered Topologies
* **Footswitch A:** `06_pj_hybrid_parallel.nam` (P/J Hybrid Parallel)
* **Footswitch B:** `04_vintage_62_p_alnico.nam` (Vintage '62 P Alnico V)
* **Footswitch C:** `08_rickenbacker_bridge_hpf.nam` (Rickenbacker 4.7nF HPF)

### Bank 4: Modern & Acoustic Special Topologies
* **Footswitch A:** `11_dingwall_multiscale_bridge.nam` (Dingwall Multi-Scale Bridge)
* **Footswitch B:** `12_upright_bridge_transducer.nam` (Upright Acoustic Bridge Transducer)
* **Footswitch C:** `05_p_bass_47nf_rolloff.nam` (P-Bass 47nF Tone Rolloff / Motown Dub)

---

## 4. Importing Files via Darkglass Suite

1. Connect your Darkglass Anagram to your computer via USB-C.
2. Open the **Darkglass Suite** application.
3. Navigate to the **NAM / Neural Capture** library.
4. Drag and drop trained `models/*.nam` captures into your user model library.
5. In your preset chain on the pedalboard, assign **Block 1** to your imported NAM capture.

---

## 5. Acoustic Upright Dual-Stage Architecture (Block 1 NAM + Block 3 3 Sigma IR)

When targeting an authentic upright double bass tone from a fretless electric bass (such as the 32" Fretless strung with **La Bella Low Tension Flats**), Passivizer splits the acoustic transformation into two specialized stages:

```
[32" Fretless Bass w/ La Bella LTF]
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ Block 1: Passivizer NAM (`12_upright_bridge_transducer`)│
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
2. **Block 1 Converts Pickup Physics:** Passivizer's NAM model transforms the magnetic velocity-sensing signal into a mechanical bridge force sensor, complete with dynamic compliance compression.
3. **Block 3 Radiates the Soundboard:** The 3 Sigma IR receives the exact force signal it was designed for, radiating it through a spruce top and resonant double-bass body.
4. **Anti-Double-Damping:** Because the 32" fretless is strung with La Bella Low Tension Flats, Passivizer's differential string engine automatically adjusts its acoustic damping curve, preventing the dull, muffled tone that occurs when a static acoustic low-pass filter is applied to already-dark flatwound strings.

---

## 6. Future Milestone: Native Anagram Marketplace Block

While Passivizer currently deploys via the Anagram's stock Neural Amp Loader block, an upcoming roadmap goal is releasing an official **Anagram Marketplace Custom Block** (`marketplace.anagram.shop`):
* **All-in-One Voice Selector:** Instant rotary switching across all 12 passive pickup topologies and acoustic transducers directly within a single block.
* **Integrated Gain Normalization:** Automatically balances the $+5.8\text{ dB}$ series boost and $-2.5\text{ dB}$ single-coil level drop under the hood to ensure unity gain into Block 2.
* **Dynamic Control Emulation:** Real-time on-screen controls for volume pot loading ($500\text{ k}\Omega$ vs. $250\text{ k}\Omega$), treble bleed networks, and cable capacitance ($750\text{ pF}$) loading.


