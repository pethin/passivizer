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
│ Block 1: Passivizer Pickup Emulation                   │
│   ├── Choice A: NAM Preamp ("03_modern_p_ceramic.nam") │
│   └── Choice B: IR Loader ("03_modern_p_ceramic.wav")  │
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
> Overdrive, distortion, and preamp stages react directly to the input frequency envelope and pickup resonant peaks. By placing the Passivizer model in Block 1, subsequent drive engines distort the *passive* resonant peak and roll-off, rather than distorting an unshaped wideband active signal.

---

## 2. Gain Staging & Volume Normalization

Passive multi-coil instruments often present notable level disparities:
* Splitting an MM humbucker to a single coil drops output level by $\sim 3	ext{--}4	ext{ dB}$.
* Switching pickups into Series configuration produces an inductive voltage surge of $+4	ext{ to }+6	ext{ dB}$.

In your presets, use the Block 1 output level trim to normalize all voices to an even target RMS level:

| Profile ID | Pickup Configuration | Raw Offset | Recommended Block 1 Trim |
| :--- | :--- | :--- | :--- |
| **`01_jazz_bass_pair`** | Jazz Bass Pair (Parallel) | $-0.5	ext{ dB}$ | $+0.5	ext{ dB}$ |
| **`02_jazz_bridge_70s`** | 70s Jazz Bridge Single-Coil | $-2.5	ext{ dB}$ | $+2.5	ext{ dB}$ (Compensates single-coil drop) |
| **`03_modern_p_ceramic`** | Modern Split-Coil P (Ceramic) | $+1.5	ext{ dB}$ | $0.0	ext{ dB}$ (Reference Baseline) |
| **`04_vintage_62_p_alnico`** | Vintage '62 Split-Coil P (Alnico V) | $+0.5	ext{ dB}$ | $+1.0	ext{ dB}$ |
| **`05_p_bass_47nf_rolloff`** | Split-Coil P (47nF Tone Rolloff) | $-1.0	ext{ dB}$ | $+1.0	ext{ dB}$ |
| **`06_pj_hybrid_parallel`** | P/J Hybrid (Parallel) | $+0.8	ext{ dB}$ | $+0.5	ext{ dB}$ |
| **`07_stingray_mm_parallel`** | Music Man MM (Parallel Humbucker)| $0.0	ext{ dB}$ | $+1.5	ext{ dB}$ |
| **`08_rickenbacker_bridge_hpf`**| Rickenbacker Bridge (4.7nF HPF) | $-1.5	ext{ dB}$ | $+2.0	ext{ dB}$ (Compensates series HPF cut) |
| **`09_pmm_hybrid_series`** | P/MM Hybrid (Series Sum) | $+5.8	ext{ dB}$ | $-4.0	ext{ dB}$ (Prevents clipping downstream drives)|
| **`10_mudbucker_ultra_series`**| Mudbucker Ultra Series | $+6.2	ext{ dB}$ | $-4.5	ext{ dB}$ (Controls high-inductance surge) |
| **`11_dingwall_multiscale_bridge`**| Dingwall Multi-Scale Bridge | $+1.0	ext{ dB}$ | $+0.5	ext{ dB}$ |

---

## 3. Footswitching & Bank Organization

Group the pickup profiles into dedicated 3-button banks on the Anagram hardware:

### Bank 1: Single-Coil & Split Foundations
* **Footswitch A:** `01_jazz_bass_pair.wav` (Jazz Bass Pair)
* **Footswitch B:** `03_modern_p_ceramic.wav` (Modern Split-Coil P)
* **Footswitch C:** `02_jazz_bridge_70s.wav` (70s Jazz Bridge)

### Bank 2: Dual-Coil & Series Topologies
* **Footswitch A:** `07_stingray_mm_parallel.wav` (Music Man Parallel Humbucker)
* **Footswitch B:** `09_pmm_hybrid_series.wav` (P/MM Series Sum)
* **Footswitch C:** `10_mudbucker_ultra_series.wav` (Mudbucker Series)

### Bank 3: Vintage & Filtered Topologies
* **Footswitch A:** `06_pj_hybrid_parallel.wav` (P/J Hybrid Parallel)
* **Footswitch B:** `04_vintage_62_p_alnico.wav` (Vintage '62 P Alnico V)
* **Footswitch C:** `08_rickenbacker_bridge_hpf.wav` (Rickenbacker 4.7nF HPF)

---

## 4. Importing Files via Darkglass Suite

1. Connect your Darkglass Anagram to your computer via USB-C.
2. Open the **Darkglass Suite** application.
3. **For IRs:** Navigate to the **IR Manager** tab, drag and drop `irs/*.wav` into user slots.
4. **For NAM Models:** Navigate to the **NAM / Neural Capture** library, drag and drop `models/*.nam` into your model library.
5. In your preset chain on the pedalboard, assign Block 1 to your imported IR or NAM capture.
