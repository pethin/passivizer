# Passivizer

**Passivizer** is an analog modeling and digital twin pipeline that transforms active, wideband, low-impedance bass pickup signals—specifically **EMG X-Series (18V)**—into accurate emulations of high-impedance **passive pickup circuits**.

Designed specifically for NAM-capable pedalboards like the **Darkglass Anagram**, HeadRush, hardware IR loaders, and DAW plugin hosts, Passivizer produces both:
1. **Minimum-Phase Impulse Responses (IRs):** High-precision 48 kHz / 24-bit FIR filters for fast, zero-latency pickup re-voicing on standard IR loaders.
2. **Neural Amp Modeler (NAM) Profiles:** Nano/Feather/A2 neural captures trained on native WAV SPICE circuit simulations to capture dynamic magnetic saturation, eddy-current damping, volume pot loading, and treble-bleed interactions.

---

## The Philosophy: Why "Active to Passive"?

In modern bass signal chains, trying to convert a passive bass to sound active with digital EQ/IRs runs into fundamental mathematical limits: high-frequency content has already been attenuated by the passive coil's 12 dB/octave low-pass filter. Boosting those missing frequencies elevates noise and introduces comb-filtering artifacts.

**Passivizer flips this relationship:**
* **Source (EMG X-Series @ 18V):** Delivers a flat, wideband (20 Hz – 20+ kHz), high-headroom, low-noise signal with near-zero inductive peaking.
* **Target (Passive Circuit):** Fundamentally subtractive, resonant, and capacitive. 

Because the active source delivers an unclipped, full-bandwidth signal, Passivizer can carve out the exact physical and electrical transfer function of any passive pickup without boosting background hiss or running into phase smearing.

---

## Why Not Just an Impulse Response (IR)?

While an Impulse Response (IR) or FIR filter can reproduce a static frequency curve, physical passive guitar and bass pickups are fundamentally **non-linear, dynamic, reactive electro-mechanical transducers**. Relying solely on a linear IR misses the core physical behavior and tactile response of a real instrument:

1. **Linear Time-Invariance (LTI) vs. Analog Dynamic "Give":**
   * An IR is strictly linear and time-invariant: plucking pianissimo ($pp$) or digging in with aggressive slap or heavy pick strokes ($ff$) produces the identical transfer function.
   * Real passive magnetic pickups exhibit dynamic core excursion non-linearities and flux compression when strings swing close to the pole pieces. Passivizer models this dynamic non-linearity via vector soft-knee saturation ($V_{\text{sat}} \cdot \tanh(v / V_{\text{sat}})$), reproducing the $1.5\text{--}2.5\text{ dB}$ of tactile compression, bloom, and dynamic "give" experienced when digging into real copper coils.

2. **Pre-Conditioning Downstream Distortion Stages:**
   * In a digital modeler like the **Darkglass Anagram**, Passivizer sits in **Block 1**, directly feeding high-gain preamps and overdrives (Microtubes B7K, Vintage Ultra, Alpha·Omega).
   * A linear IR passes high-headroom active transients through uncompressed, causing subsequent overdrive stages to clip on artificial, brittle spikes. A Passivizer neural model pre-conditions the signal with true passive saturation and impedance damping, ensuring downstream distortion blocks saturate smoothly and musically.

3. **Eddy Currents & Time-Domain Energy Storage:**
   * Metal components (pole pieces, baseplates, covers) generate circulating eddy currents that produce frequency-dependent damping ($R_{\text{eddy}}$) and subtle phase lag during rapid string transients.
   * An IR treats this as a stationary frequency cut. A **Neural Amp Modeler (NAM)** neural network captures the dynamic time-domain energy storage and release of the complete reactive RLC network.

4. **Multi-Coil Spatial Phase Summing:**
   * Instruments with multiple coils or pickups (Jazz Bass pairs, P/J, StingRay dual coils) feature complex spatial cancellation patterns that vary with string amplitude and string displacement. NAM neural models capture compound phase interactions and harmonic cancellation across the full frequency spectrum without comb-filtering artifacts or phase smearing.

> [!NOTE]
> Passivizer *can* synthesize zero-latency minimum-phase FIR impulse responses for ultra-lightweight linear filtering. However, its flagship pipeline trains lightweight **NAM neural models** (Architecture 2 / Nano/Feather) to preserve the full dynamic touch sensitivity, bloom, and analog feel of physical passive circuits.

---

## Modeling Architecture

Passivizer models the complete electro-acoustic path in four distinct layers:

```
[String Vibration]
        │
        ▼
1. Magnetic Aperture & Spatial Comb Filtering
   ├── Coil Sensing Width (w): High-frequency sinc filtering across multi-string wave speeds
   └── Dual-Coil Spacing (d): Humbucker spatial phase cancellation
        │
        ▼
2. Coil RLC Network (Passive Digital Twin)
   ├── Coil Inductance (L) & DC Resistance (R_dc)
   ├── Inter-Winding Self-Capacitance (C_coil)
   └── Eddy-Current Core Damping (R_eddy) in pole pieces & blades
        │
        ▼
3. On-Instrument Control Circuit
   ├── Master Volume Potentiometer (500k audio taper)
   ├── Hybrid Treble-Bleed Network (1.0 nF || 150 kΩ + 20 kΩ)
   └── Optional Capacitive C-Switch Bank
        │
        ▼
4. Output Environment
   ├── Instrument Cable Capacitance (~750 pF for standard 15-ft cable)
   └── Receiver Input Impedance (1 MΩ || 30 pF Darkglass Anagram input stage)
```

### Scale-Length & Multi-Scale Transformation
Passivizer converts the lower tension and warm low-mid "bloom" of **30" short-scale** and **32" medium-scale** instruments into the focused, piano-like authority of full-scale and fanned-fret instruments:
* **Wave-Speed Scaling ($\kappa_v$):** Up-shifts aperture and comb-filter null frequencies by $+13.3\%$ (for 34") and $+23.3\%$ (for 37" multi-scale).
* **String Tension Filtering:** Tightens tubby $180\text{--}250\text{ Hz}$ boom while adding laser-tight sub-bass ($40\text{--}80\text{ Hz}$) and metallic Dingwall-style clank ($2.5\text{--}3.8\text{ kHz}$).
* **Spatial Placement Tracking:** Relocates pickups from short-scale bridge datums to standard 34" and 37" sweet spots.

---

## Target Voice Catalog (12 Master Passive Configurations & Acoustic Transducers)

Passivizer includes pre-configured physical and electrical parameters for **12 distinct pickup topologies and transducers** including fanned-fret multi-scale and upright double bass (see [`docs/voice_catalog.md`](file:///Users/peter/Projects/pethin/passivizer/docs/voice_catalog.md) for full engineering specifications):

| # | Profile ID | Pickup Type | Topology | $L_{\text{eq}}$ | $f_r$ (Peak) | Circuit & Acoustic Character |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `01_jazz_bass_pair` | J-Bass Pair | Dual Parallel | $1.69\text{ H}$ | $3.9\text{ kHz}$ | Dual narrow single-coils in parallel; symmetrical wide-aperture $1\text{ kHz}$ hollow scoop with top sparkle. |
| **02** | `02_jazz_bridge_70s` | J-Bass Bridge | Single Coil | $3.60\text{ H}$ | $3.2\text{ kHz}$ | 70s bridge single-coil ($40.6\text{ mm}$ datum); focused $1.2\text{ kHz}$ harmonic bite with tight low end. |
| **03** | `03_modern_p_ceramic` | Split P-Bass | Single Split | $4.80\text{ H}$ | $2.2\text{ kHz}$ | Modern ceramic split-coil (Bartolini 8CBP style); high-inductance punch and fast pick transient attack. |
| **04** | `04_vintage_62_p_alnico` | Split P-Bass | Single Split | $3.80\text{ H}$ | $2.8\text{ kHz}$ | Classic Alnico V split-coil; lower eddy-current damping, open and dynamic woody resonance. |
| **05** | `05_p_bass_47nf_rolloff` | Split P-Bass | Split w/ 47nF | $4.80\text{ H}$ | $0.45\text{ kHz}$| Split-coil with passive tone rolled to 0; deep, fundamental-heavy pillowy sub-bass. |
| **06** | `06_pj_hybrid_parallel` | P + J Hybrid | Parallel Sum | $2.06\text{ H}$ | $3.6\text{ kHz}$ | Split P-neck and single-coil J-bridge summed in parallel; balanced low thump with bridge snap. |
| **07** | `07_stingray_mm_parallel` | MM Humbucker | Dual Parallel | $2.40\text{ H}$ | $3.5\text{ kHz}$ | Music Man dual-coil humbucker in parallel; $0.75''$ spacing comb filter with prominent $3.5\text{ kHz}$ clank. |
| **08** | `08_rickenbacker_bridge_hpf` | High-Pass Bridge | Series HPF | $3.80\text{ H}$ | $2.2\text{ kHz}$ | High-output bridge coil with vintage $4.7\text{ nF}$ series capacitor; tight high-pass cut below $150\text{ Hz}$. |
| **09** | `09_pmm_hybrid_series` | P + MM Hybrid | Series Sum | $7.20\text{ H}$ | $2.0\text{ kHz}$ | Split P and MM humbucker wired in series; massive $+5.8\text{ dB}$ inductive boost with $2.0\text{ kHz}$ focus. |
| **10** | `10_mudbucker_ultra_series` | Heavy Series MM | Ultra Series | $14.40\text{ H}$| $1.2\text{ kHz}$ | Overwound dual-coil series humbucker; subterranean low end with natural high-frequency rolloff. |
| **11** | `11_dingwall_multiscale_bridge` | Multi-Scale MM | Angled Parallel | $2.30\text{ H}$| $3.4\text{ kHz}$ | 34"-37" fanned-fret angled bridge sweet spot ($48.0\text{ mm}$) with high-tension wave-speed clank filter. |
| **12** | `12_upright_bridge_transducer` | Upright Transducer | Bridge Force | $1\ \mu\text{H}$ / Piezo | $4.5\text{ kHz}$ | Direct bridge force sensor (Underwood / Realist style); leaky integration, 32 Hz rumble cut, and soft-knee bridge compliance. |

---

## SPICE $\to$ NAM Pipeline & CLI Usage

Passivizer models acoustic aperture and scale tension in Python, executes the passive circuit digital twin directly using its native WAV SPICE simulator, and trains lightweight NAM (`.nam`) neural captures for Block 1 of the Darkglass Anagram:

### 1. Interactive Acoustic & Electrical Visualizer (`scripts/analyze_voices.py`)
Renders interactive frequency response curves in Altair (Vega-Lite), comparing all 12 target configurations against any source instrument. Outputs are organized into per-instrument standalone charts and a unified interactive portal:

```bash
# Generate interactive charts for all configured source instruments and refresh master portal:
uv run python scripts/analyze_voices.py

# Generate or refresh for a specific instrument (preserves all other instrument charts):
uv run python scripts/analyze_voices.py --instrument 32in_fretless
uv run python scripts/analyze_voices.py --instrument 30in
```
*Outputs: Master interactive portal at `docs/frequency_responses.html` (and `docs/frequency_responses/index.html`) with embedded tabbed navigation and spec breakdown, and per-instrument standalone visualizations in `docs/frequency_responses/<instrument_id>.html`.*

### 2. Native WAV SPICE Circuit Simulation (`scripts/simulate_circuits.py`)
Directly streams raw NAM calibration audio (`v1_1_1.wav`) through the entire physical digital twin in a single in-memory pass:
1. **Acoustic Aperture & Placement:** De-humbucking sinc aperture filtering, spatial standing-wave comb filtering, displacement tilt ($\Delta x$), and string tension filtering.
2. **Dynamic Non-Linear Compliance:** Soft-knee saturation ($V_{\text{sat}} \cdot \tanh(v / V_{\text{sat}})$).
3. **Passive Pickup Circuit Twin:** Exact closed-form nodal AC transfer functions, eddy-current damping, 500k volume pot divider, hybrid treble bleed, cable capacitance ($750\text{ pF}$), and pedalboard load ($1\text{ M}\Omega \parallel 30\text{ pF}$).

Passivizer features a built-in **WAV SPICE simulator** running natively on Apple Silicon (`arm64`). By evaluating exact analytical nodal equations and vector non-linearities directly in memory on the audio waveform, it eliminates external SPICE dependencies (such as LTspice or ngspice) and intermediate disk writes, executing in ~0.8s per voice (>1500x faster than traditional transient SPICE engines):

```bash
# Run unified WAV SPICE simulation from raw audio for a specific voice (~0.8s):
uv run python scripts/simulate_circuits.py --voice 03_modern_p_ceramic --instrument 30in

# Simulate all 12 voices:
uv run python scripts/simulate_circuits.py --voice all --instrument 30in

# Run via master pipeline:
uv run python main.py --stage sim --voice 03_modern_p_ceramic
```

*(Note: `scripts/prep_nam_audio.py` is retained for users who wish to inspect or export intermediate standalone aperture audio `audio/<instrument>/aperture_<voice>.wav`).*

### 3. NAM Neural Model Training (Architecture 2 / A2)
Trains a high-efficiency **NAM Architecture 2 (A2)** neural model on the input/output audio pair. A2 replaces legacy A1 models (nano/feather/standard) with a "slimmable" neural architecture designed specifically for low-power hardware like the Darkglass Anagram:

```bash
# Train NAM Architecture 2 (A2) model for Darkglass Anagram Block 1:
# The input is the raw bass calibration sweep (v1_1_1.wav) and the target is the simulated output:
nam train v1_1_1.wav audio/30in_emg_mmtw/out_03_modern_p_ceramic.wav ./models/30in_emg_mmtw/03_modern_p_ceramic.nam --architecture "A2"

# Alternatively, run via the automated Passivizer trainer:
uv run python main.py --stage train --instrument 30in --voice 03_modern_p_ceramic
```
*(In modern versions of `neural-amp-modeler` and the official Google Colab trainer, `--architecture A2` is the default. Note: NAM is trained end-to-end from the raw input `v1_1_1.wav` to capture the entire acoustic aperture, string tension, and electrical RLC behavior in a single unified model).*

### 4. Master Automation Runner (`scripts/run_pipeline.py` & `main.py`)
Execute the entire pipeline or specific stages with a single command:

```bash
# Run complete pipeline for 30" source instrument (using native VA circuit engine):
uv run python main.py --source-scale 30in

# Run only visualization:
uv run python main.py --stage viz

# Run audio pre-filtering for a specific voice:
uv run python main.py --stage prep --voice 07_stingray_mm_parallel

# Run circuit simulation stage:
uv run python main.py --stage sim --voice 07_stingray_mm_parallel
```

---

## Signal Flow on the Darkglass Anagram

```
[Bass: EMG PX / MMTWX @ 18V]
             │
             ▼
[Block 1: Passivizer NAM Preamp]
    └── Model: "07_stingray_mm_parallel.nam" (Nano/Feather neural capture)
             │
             ▼
[Block 2: Darkglass Preamp / Drive]
    └── Microtubes B7K, Vintage Ultra, or Alpha·Omega
             │
             ▼
[Block 3: Speaker Cabinet IR Loader]
    └── Ampeg 8x10, Darkglass 4x10, or custom speaker cab impulse
             │
             ▼
[Output to FOH / Audio Interface]
```

---

## Project Structure

```
passivizer/
├── README.md                              # Project vision, theory, architecture, and CLI guide
├── docs/                                  # In-depth technical guides
│   ├── configuration_reference.md         # Complete schema & field reference for TOML configurations
│   ├── voice_catalog.md                   # Complete passive pickup technical catalog & parameters
│   ├── circuit_theory.md                  # RLC, eddy current, and cable impedance math
│   ├── aperture_math.md                   # Magnetic aperture sinc, multi-string & scale physics
│   └── anagram_workflow.md                # Darkglass Anagram Block 1 routing & gain staging
├── circuits/                              # Standalone SPICE netlists (.cir)
│   ├── 01_jazz_bass_pair.cir              # Dual single-coils in parallel
│   ├── 02_jazz_bridge_70s.cir             # 70s bridge single-coil
│   ├── 03_modern_p_ceramic.cir            # Modern ceramic split-coil P
│   ├── 04_vintage_62_p_alnico.cir         # Vintage '62 Alnico V split-coil P
│   ├── 05_p_bass_47nf_rolloff.cir         # Split-coil P with 47nF tone shunt
│   ├── 06_pj_hybrid_parallel.cir          # P/J hybrid parallel
│   ├── 07_stingray_mm_parallel.cir        # Music Man parallel humbucker
│   ├── 08_rickenbacker_bridge_hpf.cir     # 4003 bridge with 4.7nF series HPF
│   ├── 09_pmm_hybrid_series.cir           # P/MM hybrid in series
│   ├── 10_mudbucker_ultra_series.cir      # Overwound series humbucker
│   └── 11_dingwall_multiscale_bridge.cir  # Multi-scale angled bridge position
├── config/                                # Modular TOML configuration files
│   ├── instruments/                       # Source bass geometries, pickups & routing
│   │   ├── 30in_emg_mmtw.toml             # 30" active EMG MMTW dual-mode bass
│   │   ├── 32in_custom_pmm.toml           # 32" custom PX + MMTWX bass
│   │   ├── 34in_standard_p.toml           # 34" standard P-bass template
│   │   └── 34in_standard_jazz.toml        # 34" standard Jazz bass template
│   ├── scales.toml                        # Scale lengths & baseline string wave speeds
│   └── voices.toml                        # Voice metadata linking to SPICE netlists
├── scripts/                               # Generation utilities (Python / uv)
│   ├── model_physics.py                   # Aperture sinc, scale wave speeds, and FIR engine
│   ├── analyze_voices.py                  # Polars + Altair frequency curve visualizer
│   ├── prep_nam_audio.py                  # Aperture & scale tension pre-filtering for NAM
│   ├── simulate_circuits.py               # Native Apple Silicon WAV SPICE circuit engine
│   └── run_pipeline.py                    # Master end-to-end automated runner
├── tests/                                 # Pytest test suite (47 tests)
└── models/                                # Exported .nam neural models
```

---

## Roadmap

### Completed Milestones
- [x] **Electro-Acoustic Physical Modeling:** Magnetic aperture sinc filtering, spatial comb nulls, scale-length wave-speed scaling ($30''/32'' \to 34''/37''$), and differential string tension modeling.
- [x] **Native WAV SPICE Simulator:** High-performance Apple Silicon engine (`scripts/simulate_circuits.py`) solving analytical nodal RLC equations and $\tanh$ soft-knee saturation directly on audio at >1500x speed.
- [x] **12 Passive Voice Profiles & Transducers:** Single-coil, split-coil, series/parallel dual-coils, fanned multi-scale, and double-bass bridge piezo force transducers.
- [x] **Interactive Visualization Portal:** Polars + Altair frequency response portal with spec sheets and per-instrument interactive charts (`docs/frequency_responses.html`).
- [x] **Automated NAM Training Pipeline:** End-to-end Architecture 2 (A2) neural model training targeting Darkglass Anagram Block 1.
- [x] **Automated Test Suite:** Comprehensive 47-test pytest verification covering physical filters, nodal transfer functions, FIR DSP, and audio simulation.

### Upcoming Objectives
- [ ] **Hardware Reference Calibration:** Dry-DI spectral matching and A/B verification against physical vintage instruments (1962 P-Bass, 1975 Jazz Bass, 1979 StingRay).
- [ ] **In-Browser Audio Player:** Interactive audio preview player embedded directly into the Altair documentation portal.
- [ ] **Anagram Marketplace Native Block:** Develop a dedicated, all-in-one "Passivizer" custom block for the Darkglass Anagram Marketplace (`marketplace.anagram.shop`), featuring rotary voice switching across all 12 pickup configurations, automatic gain normalization, and interactive volume/cable load controls in a single native Block 1 module.
