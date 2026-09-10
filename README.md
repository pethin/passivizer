# Allomorph

**Allomorph** is an analog modeling and digital twin pipeline that transforms bass pickup and transducer signals—across active, passive, and acoustic piezo topologies—into authentic digital twin voices of iconic high-impedance **passive pickup circuits, active preamps, and acoustic instruments**.

Designed specifically for NAM-capable pedalboards like the **Darkglass Anagram**, HeadRush, hardware IR loaders, and DAW plugin hosts, Allomorph produces both:
1. **Minimum-Phase Impulse Responses (IRs):** High-precision 48 kHz / 24-bit FIR filters for fast, zero-latency pickup re-voicing on standard IR loaders.
2. **Neural Amp Modeler (NAM) Profiles:** Nano/Feather/A2 neural captures trained on native WAV SPICE circuit simulations to capture dynamic magnetic saturation, eddy-current damping, volume pot loading, and treble-bleed interactions.

---

## The Philosophy: Universal Transducer Transformation

In modern bass signal chains, trying to convert a passive bass to sound active with digital EQ/IRs runs into fundamental mathematical limits: high-frequency content has already been attenuated by the passive coil's 12 dB/octave low-pass filter. Boosting those missing frequencies elevates noise and introduces comb-filtering artifacts.

**Allomorph provides bidirectional, universal transformation:**
* **Active Sources (e.g. EMG X-Series @ 18V):** Deliver a flat, wideband (20 Hz – 20+ kHz), high-headroom, low-noise signal with near-zero inductive peaking, allowing Allomorph to carve out the exact physical and electrical transfer function of any vintage passive pickup without boosting background hiss.
* **Passive Sources (e.g. Precision, Jazz, Mustang):** Re-voiced through true differential circuit deconvolution ($H_{\text{diff}} = H_{\text{tgt}} / H_{\text{src}}$), morphing physical vintage coils into modern active buffers, hot overwound humbuckers, or alternate scale placements.
* **Acoustic & Piezo Transducers:** Bridge force transducers and body cavity resonances faithfully emulated without artificial magnetic assumptions.

---

## Why Not Just an Impulse Response (IR)?

While an Impulse Response (IR) or FIR filter can reproduce a static frequency curve, physical guitar and bass pickups and transducers are fundamentally **non-linear, dynamic, reactive electro-mechanical systems**. Relying solely on a linear IR misses the core physical behavior and tactile response of a real instrument:

1. **Linear Time-Invariance (LTI) vs. Analog Dynamic "Give":**
   * An IR is strictly linear and time-invariant: plucking pianissimo ($pp$) or digging in with aggressive slap or heavy pick strokes ($ff$) produces the identical transfer function.
   * Real passive magnetic pickups exhibit dynamic core excursion non-linearities and flux compression when strings swing close to the pole pieces. Allomorph models this dynamic non-linearity via vector soft-knee saturation ($V_{\text{sat}} \cdot \tanh(v / V_{\text{sat}})$), reproducing the $1.5\text{--}2.5\text{ dB}$ of tactile compression, bloom, and dynamic "give" experienced when digging into real copper coils.

2. **Pre-Conditioning Downstream Distortion Stages:**
   * In a digital modeler like the **Darkglass Anagram**, Allomorph sits in **Block 1**, directly feeding high-gain preamps and overdrives (Microtubes B7K, Vintage Ultra, Alpha·Omega).
   * A linear IR passes high-headroom active transients through uncompressed, causing subsequent overdrive stages to clip on artificial, brittle spikes. An Allomorph neural model pre-conditions the signal with true passive saturation and impedance damping, ensuring downstream distortion blocks saturate smoothly and musically.

3. **Eddy Currents & Time-Domain Energy Storage:**
   * Metal components (pole pieces, baseplates, covers) generate circulating eddy currents that produce frequency-dependent damping ($R_{\text{eddy}}$) and subtle phase lag during rapid string transients.
   * An IR treats this as a stationary frequency cut. A **Neural Amp Modeler (NAM)** neural network captures the dynamic time-domain energy storage and release of the complete reactive RLC network.

4. **Multi-Coil Spatial Phase Summing:**
   * Instruments with multiple coils or pickups (Jazz Bass pairs, P/J, StingRay dual coils) feature complex spatial cancellation patterns that vary with string amplitude and string displacement. NAM neural models capture compound phase interactions and harmonic cancellation across the full frequency spectrum without comb-filtering artifacts or phase smearing.

> [!NOTE]
> Allomorph *can* synthesize zero-latency minimum-phase FIR impulse responses for ultra-lightweight linear filtering. However, its flagship pipeline trains lightweight **NAM neural models** (Architecture 2 / Nano/Feather) to preserve the full dynamic touch sensitivity, bloom, and analog feel of physical passive circuits.

---

## The Ideal Source Instrument: Single-Pickup Architecture (34" Scale)

While Allomorph supports multi-pickup and active-blend source instruments, the **optimal hardware platform** for driving all 14 digital twin voicings is a **single-pickup, zero-control bass**.
By installing a single active EMG pickup wired straight to the output jack, you establish an uncompromising reference baseline:

```
[12th Fret] ◄────────────── 338.3 mm ──────────────► [Pickup Center] ◄──── 93.5 mm ────► [Bridge Saddle]
```

### 1. The Single-Pickup Philosophy: Total Decoupling & Zero Comb Nulls
* **No Comb-Filtering Nulls to Invert:** Humbuckers with dual coils under the same string introduce physical phase cancellation notches ($f = v / 2d \approx 2.5\text{ kHz}$) that cannot be cleanly inverted in DSP without boosting noise. A single line of sensing per string provides a clean, notch-free transfer function that allows Allomorph to synthesize any target aperture or dual-coil comb filter effortlessly.
* **Total Preset Decoupling:** Eliminates the "hand-foot desync" problem. You never have to adjust physical knobs or flip coil switches to match patch changes on your pedalboard; stepping on a Darkglass Anagram footswitch transforms the tone entirely in software.

### 2. Recommended Pickup: EMG PX or EMG 35P4X (18V)
* **Split-Coil Geometry (Zero Comb Nulls):** The E/A and D/G strings each pass over only **one** isolated coil ($d = 0$). There is zero inter-coil phase cancellation along any string.
* **Hum-Canceling Common-Mode Rejection:** Reverse-wound, reverse-polarity split bobbins ensure 100% hum-free performance on a pot-free instrument.
* **Ceramic X-Series Preamp @ 18V:** Delivers an ultra-wide, linear frequency response ($f_r \approx 3.2\text{ kHz}$), near-zero core saturation, and $>8.5\text{V}_{\text{p-p}}$ dynamic headroom.
* **Form Factors:** Traditional two-piece split-P covers (**EMG PX**) or a single $3.50'' \times 1.50''$ rectangular soapbar (**EMG 35P4X** for 4-string, **40P5X** for 5-string).

### 3. Lutherie Datums: The $93.5\text{ mm}$ ($3.68''$) Acoustic Median
On a standard **34.0" scale length** ($863.6\text{ mm}$), **$93.5\text{ mm}$** is the exact mathematical median between a 60s Jazz Bridge ($63.5\text{ mm}$) and a standard Precision Bass ($125.0\text{ mm}$):

$$\bar{x} = \frac{63.5\text{ mm} + 125.0\text{ mm}}{2} = 94.25\text{ mm} \approx \mathbf{93.5\text{ mm}}$$

This median position achieves a **Reverse-P Dual-Datum Alignment**:

| Geometry | Measurement from Bridge Saddle | Measurement from 12th Fret | Notes |
| :--- | :--- | :--- | :--- |
| **Reverse-P: E/A Coil Half** | **$80.8\text{ mm}$** ($3.18''$) | **$351.0\text{ mm}$** ($13.82''$) | **Exact StingRay sweet spot!** Rearward placement keeps low E & A strings punchy, tight, and articulate. |
| **Reverse-P: D/G Coil Half** | **$106.2\text{ mm}$** ($4.18''$) | **$325.6\text{ mm}$** ($12.82''$) | **Within $4.8\text{ mm}$ of a vintage P-Bass!** Forward placement gives high D & G strings warm, singing body. |
| **Reverse-P Acoustic Centroid** | **$93.5\text{ mm}$** ($3.68''$) | **$338.3\text{ mm}$** ($13.32''$) | Perfect geometric acoustic balance across all 4 strings. |
| **Soapbar Center (EMG 35P4X)** | **$93.5\text{ mm}$** ($3.68''$) | **$338.3\text{ mm}$** ($13.32''$) | Casing cavity: $74.5\text{ mm}$ bridge edge, $112.5\text{ mm}$ neck edge. |

* **Why this position outclasses all others:** 
  1. The low E and A strings are physically sampled right where a Music Man StingRay senses, ensuring tight sub-bass, punchy low-mids, and zero flub.
  2. The high D and G strings are physically sampled within $5\text{ mm}$ of an authentic 1962 Fender P-Bass, ensuring rich fundamental bloom and eliminating high-register "plinkiness."
  3. Because the pickup is equidistant between bridge single-coils ($63.5\text{ mm}$) and neck split-coils ($125.0\text{ mm}$), the DSP acoustic tilt adjustments in Allomorph are kept to an absolute minimum ($\le 1.8\text{ dB}$ in either direction).

### 4. Zero-Control Electrical Wiring (Direct-to-Jack)
* **Wiring:** Connect the EMG pickup signal wire directly to the stereo 1/4" output jack Tip, battery negative to Ring (for automatic power switching on cable insertion), and pickup/battery ground to Sleeve.
* **Power:** Two 9V batteries wired in series (**18V**) for maximum linear headroom.
* **Zero Loading:** Eliminates potentiometer wiper resistance, pot capacitance loading, and accidental level bumps, ensuring $100\%$ consistent calibration into Block 1 every time you plug in.

---

## Modeling Architecture

Allomorph models the complete electro-acoustic path in four distinct layers:

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
Allomorph converts the lower tension and warm low-mid "bloom" of **30" short-scale** and **32" medium-scale** instruments into the focused, piano-like authority of full-scale and fanned-fret instruments:
* **Wave-Speed Scaling ($\kappa_v$):** Up-shifts aperture and comb-filter null frequencies by $+13.3\%$ (for 34") and $+23.3\%$ (for 37" multi-scale).
* **String Tension Filtering:** Tightens tubby $180\text{--}250\text{ Hz}$ boom while adding laser-tight sub-bass ($40\text{--}80\text{ Hz}$) and metallic Dingwall-style clank ($2.5\text{--}3.8\text{ kHz}$).
* **Spatial Placement Tracking:** Relocates pickups from short-scale bridge datums to standard 34" and 37" sweet spots.

---

### Target Voice Catalog (21 Master Configurations & Acoustic Transducers)

Allomorph includes pre-configured physical and electrical parameters for **21 distinct pickup topologies, active buffers, and transducers** including active 2-band preamps, Stellartone ToneStyler discrete capacitive switching, fanned-fret multi-scale, and upright double bass (see [`docs/voice_catalog.md`](file:///Users/peter/Projects/pethin/passivizer/docs/voice_catalog.md) for full engineering specifications):

| # | Profile ID | Pickup Type | Topology | Harness / Controls | $L_{\text{eq}}$ | $f_r$ (Peak) | Circuit & Acoustic Character |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `01_modern_jazz_active` | Modern Active Jazz | Active 2-Band | Sadowsky 2-Band ($R_{\text{in}}=1\text{M}\Omega, R_{\text{out}}=100\,\Omega$) | $1.69\text{ H}$ (isolated) | $7.8\text{ kHz}$ | Isolated 60s J-pair with Sadowsky active 2-band boost; wideband sparkle with $+4\text{ dB}$ bass/treble. |
| **02** | `02_jazz_bass_pair` | Vintage 60s J-Bass Pair | Dual Parallel | Vintage $2\times 250\text{k}\Omega$ Vol ($125\text{k}\Omega$ net), $250\text{k}\Omega$ Tone, $47\text{nF}$ | $1.69\text{ H}$ | $2.7\text{ kHz}$ | Dual narrow single-coils in parallel; 60s $92.1\text{ mm}$ ($3\frac{5}{8}''$) aperture scoop with woody resonance. |
| **02b**| `02b_jazz_bass_pair_22nf`| 60s J-Bass Pair (22nF) | Dual Parallel | Vintage $2\times 250\text{k}\Omega$ Vol, 22nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$) | $1.69\text{ H}$ | $762\text{ Hz}$ | Vocal midrange honk ($762\text{ Hz}$ peak, $-3\text{ dB}$ at $1225\text{ Hz}$); pure capacitive shunt preserves Jaco bridge growl with zero wiper mud. |
| **02c**| `02c_jazz_bridge_growl_bias`| Jaco Biased J-Pair (100%/75%) | Dual Parallel Decoupled | Bridge 100% ($0\,\Omega$), Neck 75% ($55\text{k}\Omega$ wiper decoupling), $250\text{k}\Omega$ Tone | $1.69\text{ H}$ | $3.4\text{ kHz}$ | Signature Jaco Pastorius vocal bridge growl; $55\text{k}\Omega$ neck decoupling shifts notch to $550\text{--}800\text{ Hz}$ with $3.4\text{ kHz}$ bite. |
| **03** | `03_jazz_bridge_60s` | 60s J-Bass Bridge | Single Coil | Vintage $250\text{k}\Omega$ Vol, $250\text{k}\Omega$ Tone, $47\text{nF}$ | $3.60\text{ H}$ | $2.8\text{ kHz}$ | 60s bridge single-coil ($63.5\text{ mm}$ datum); focused midrange bite, authentic Jaco growl. |
| **04** | `04_modern_p_ceramic` | Modern Split P | Single Split | Boutique $500\text{k}\Omega$ Vol/Tone, $22\text{nF}$ Cap, Treble Bleed | $4.80\text{ H}$ | $2.4\text{ kHz}$ | Modern ceramic split-coil (Bartolini 8CBP); punchy attack with extended clarity from 500k harness. |
| **05** | `05_vintage_62_p_alnico` | Vintage '62 P (Tone Open)| Single Split | Vintage CTS $250\text{k}\Omega$ Vol/Tone Open, $47\text{nF}$ PIO Cap | $3.80\text{ H}$ | $2.1\text{ kHz}$ | Classic Alnico V split-coil wide open; touch-sensitive dynamic response, woody organic bloom ($4.0\text{ kHz}$ cutoff). |
| **05b**| `05b_vintage_62_p_22nf` | Vintage '62 P (22nF) | Single Split | 22nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$) | $3.80\text{ H}$ | $440\text{ Hz}$ | Modern Fender spec; punchy $440\text{ Hz}$ low-mid resonant focus (+1.5 dB), $-3\text{ dB}$ cutoff at $750\text{ Hz}$. |
| **05c**| `05c_vintage_62_p_47nf` | Vintage '62 P (47nF) | Single Split | 47nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$), Flatwound Heavy | $3.80\text{ H}$ | $450\text{ Hz}$ | Authentic Jamerson Motown flatwound thump; 47nF ToneStyler pure capacitive shunt with pillowy low-end warmth. |
| **05d**| `05d_vintage_50s_p_100nf`| Vintage '50s P (100nF) | Single Split | 100nF ToneStyler Pure Shunt ($R_{\text{tone}}=3.3\,\Omega$) | $3.80\text{ H}$ | Sub-bass | Original 1951–1959 Fullerton factory paper-in-oil spec; massive sub-bass shelf rolloff ($-3\text{ dB}$ at $240\text{ Hz}$, deep Motown / reggae dub thump). |
| **07** | `07_modern_pj_active` | Modern Active P/J | Active 2-Band | Sadowsky/Spector 2-Band ($R_{\text{in}}=1\text{M}\Omega, R_{\text{out}}=100\,\Omega$) | $2.06\text{ H}$ (isolated) | $7.6\text{ kHz}$ | Active 2-band boost with isolated ceramic P/J coils; punchy sub-bass fundamental, wideband sparkle, and aggressive clank. |
| **08** | `08_vintage_pj_passive` | Vintage '80s Passive P/J | Parallel Sum | Dual $250\text{k}\Omega$ Vol ($125\text{k}\Omega$ net), $250\text{k}\Omega$ Tone, $47\text{nF}$ | $1.85\text{ H}$ | $2.8\text{ kHz}$ | Vintage Alnico V split-P and 60s J-bridge in parallel; authentic '80s Fender Special / Yamaha BB thump with woody mid-punch. |
| **09** | `09_stingray_mm_parallel` | Music Man StingRay | Active MM Buffer | Music Man 2-Band ($R_{\text{in}}=1\text{M}\Omega, R_{\text{out}}=100\,\Omega$) | $2.40\text{ H}$ (isolated) | $7.2\text{ kHz}$ | Authentic active 2-band MM humbucker; cable isolation, comb notch at $2.5\text{ kHz}$, metallic clank. |
| **09b**| `09b_stingray_mm_series` | Music Man MM (Series) | Active Series Buffer | Music Man 2-Band Preamp Buffer | $4.80\text{ H}$ (isolated) | $2.1\text{ kHz}$ | Dual-coil humbucker in series with active buffer; aggressive $2.1\text{ kHz}$ mid-punch delivering commanding authority. |
| **10** | `10_rickenbacker_bridge_hpf` | High-Pass Bridge | Series HPF | Factory Rickenbacker $330\text{k}\Omega$ Vol/Tone, $4.7\text{nF}$ Series Cap | $3.80\text{ H}$ | $2.2\text{ kHz}$ | High-output bridge coil with vintage $4.7\text{ nF}$ series capacitor; tight high-pass cut below $150\text{ Hz}$. |
| **11** | `11_pmm_hybrid_series` | P + MM Hybrid | Series Sum | Modern $500\text{k}\Omega$ Vol/Tone, $47\text{nF}$ Cap | $7.20\text{ H}$ | $1.6\text{ kHz}$ | Split P and MM humbucker wired in series; $+5.8\text{ dB}$ inductive boost with $1.6\text{ kHz}$ punch. |
| **12** | `12_mudbucker_ultra_series` | Heavy Series MM | Ultra Series | Gibson $500\text{k}\Omega$ Vol/Tone, $22\text{nF}$ Cap | $14.40\text{ H}$| $1.2\text{ kHz}$ | Overwound dual-coil series humbucker; subterranean low end with natural high-frequency rolloff. |
| **13** | `13_dingwall_multiscale_bridge` | Multi-Scale MM | Angled Parallel | Dingwall $500\text{k}\Omega$ Vol/Tone, $47\text{nF}$ Cap | $2.30\text{ H}$| $3.4\text{ kHz}$ | 34"-37" fanned-fret angled bridge sweet spot ($48.0\text{ mm}$) with high-tension wave-speed clank filter. |
| **14** | `14_upright_bridge_transducer` | Upright Transducer | Bridge Force | Direct $100\text{ M}\Omega$ Buffer, $15\text{ nF}$ Subsonic Cap | — | $4.5\text{ kHz}$ | Direct bridge force sensor (Underwood / Realist style); leaky integration, 32 Hz rumble cut, bridge compliance. |
| **15** | `15_passive_character` | Passive Character (Flat EQ)| Passive Dynamic Twin | Transparent Bypass ($100\text{ M}\Omega$ Load) | $3.60\text{ H}$ | Dynamic | Pure passive Alnico V dynamic feel, back-EMF braking, and quack without EQ coloring; preserves active bass onboard filters. |
| **16** | `16_active_character` | Studio Active Buffer | Active Cable Isolator | Studio Ultra-High-Z Buffer ($10\text{ M}\Omega \to 50\,\Omega$) | $0.00\text{ H}$ | Wideband | Studio active buffer isolating coils from 750pF cable capacitance; delivers wideband hi-fi sparkle and punchy transient headroom. |

---

## SPICE $\to$ NAM Pipeline & CLI Usage

Allomorph models acoustic aperture and scale tension in Python, executes the passive circuit digital twin directly using its native WAV SPICE simulator, and trains lightweight NAM (`.nam`) neural captures for Block 1 of the Darkglass Anagram:

### 1. Interactive Acoustic & Electrical Visualizer (`scripts/analyze_voices.py`)
Renders interactive frequency response curves in Altair (Vega-Lite), comparing all 21 target configurations against any source instrument. Outputs are organized into per-instrument standalone charts and a unified interactive portal:

```bash
# Generate interactive charts for all configured source instruments and refresh master portal:
uv run python scripts/analyze_voices.py

# Generate or refresh for a specific instrument (preserves all other instrument charts):
uv run python scripts/analyze_voices.py --instrument 32in_fretless
uv run python scripts/analyze_voices.py --instrument 30in
```
*Outputs: Master interactive portal at `docs/frequency_responses.html` (and `docs/frequency_responses/index.html`) with embedded tabbed navigation and spec breakdown, and per-instrument standalone visualizations in `docs/frequency_responses/<instrument_id>.html`.*

### 2. Native WAV SPICE Circuit Simulation (`scripts/simulate_circuits.py`)
Directly streams raw NAM calibration audio (`T3K-sweep-v3.wav` / `v3_0_0.wav` / `input.wav`) through the entire physical digital twin in a single in-memory pass:
1. **Acoustic Aperture & Placement:** De-humbucking sinc aperture filtering, spatial standing-wave comb filtering, displacement tilt ($\Delta x$), and string tension filtering.
2. **Dynamic Non-Linear Compliance:** Soft-knee saturation ($V_{\text{sat}} \cdot \tanh(v / V_{\text{sat}})$), Lenz flux sag, Dahl hysteresis, back-EMF, and dynamic reluctance quack.
3. **Passive Pickup Circuit Twin:** Exact closed-form nodal AC transfer functions, eddy-current damping, authentic volume/tone pot dividers, active preamp buffers, hybrid treble bleed, cable capacitance ($750\text{ pF}$), and pedalboard load ($1\text{ M}\Omega \parallel 30\text{ pF}$).

Allomorph features a built-in **WAV SPICE simulator** running natively on Apple Silicon (`arm64`). By evaluating exact analytical nodal equations and vector non-linearities directly in memory on the audio waveform, it eliminates external SPICE dependencies (such as LTspice or ngspice) and intermediate disk writes, executing in ~0.8s per voice (>1500x faster than traditional transient SPICE engines):

```bash
# Run unified WAV SPICE simulation from raw audio for a specific voice (~0.8s):
uv run python scripts/simulate_circuits.py --voice 04_modern_p_ceramic --instrument 30in

# Simulate all 21 voices in parallel across multi-core CPU (-j / --jobs):
uv run python scripts/simulate_circuits.py --voice all --instrument 30in -j 8

# Rapid prototyping run on first 2 seconds (96,000 samples):
uv run python scripts/simulate_circuits.py --voice 09_stingray_mm_parallel --max-samples 96000

# Run via master pipeline:
uv run python main.py --stage sim --voice 04_modern_p_ceramic
```

*(Note: `scripts/prep_nam_audio.py` is retained for users who wish to inspect or export intermediate standalone aperture audio `audio/<instrument>/aperture_<voice>.wav`).*

### 3. NAM Neural Model Training (Architecture 2 / A2)
Trains a high-efficiency **NAM Architecture 2 (A2)** neural model on the input/output audio pair. A2 replaces legacy A1 models (nano/feather/standard) with a "slimmable" neural architecture designed specifically for low-power hardware like the Darkglass Anagram:

```bash
# Train NAM Architecture 2 (A2) model for Darkglass Anagram Block 1:
# The input is the raw bass calibration sweep (T3K-sweep-v3.wav) and the target is the simulated output:
nam train T3K-sweep-v3.wav audio/30in_emg_mmtw/out_04_modern_p_ceramic.wav ./models/30in_emg_mmtw/04_modern_p_ceramic.nam --architecture "A2"

# Run via the automated Allomorph trainer (defaults to studio reference goal ESR <= 0.0005 with 100 max epochs):
uv run python main.py --stage train --instrument 30in --voice 04_modern_p_ceramic

# Customize goal ESR or disable early stopping:
uv run python main.py --stage train --instrument 30in --voice 04_modern_p_ceramic --goal-esr 0.0002
uv run python main.py --stage train --instrument 30in --voice 04_modern_p_ceramic --no-goal-esr --epochs 100
```
*(In modern versions of `neural-amp-modeler` and the official Google Colab trainer, `--architecture A2` is the default. Allomorph enables goal-driven early stopping by default (`--goal-esr 0.0005`, $\approx -33\text{ dB}$ ESR), halting training as soon as transparent studio reference fidelity is reached).*

### 4. Master Automation Runner (`scripts/run_pipeline.py` & `main.py`)
Execute the entire pipeline or specific stages with a single command:

```bash
# Run complete pipeline for 30" source instrument (using native VA circuit engine):
uv run python main.py --instrument 30in

# Run only visualization:
uv run python main.py --stage viz

# Run audio pre-filtering for a specific voice:
uv run python main.py --stage prep --voice 07_stingray_mm_parallel

# Run circuit simulation stage (with automatic output level normalization based on input sweep dBFS):
uv run python main.py --stage sim --voice 07_stingray_mm_parallel

# Or run native circuit simulation directly with automatic sweep level normalization:
uv run python scripts/simulate_circuits.py --instrument 30in --voice all --normalize auto
```

---

### Signal Flow on the Darkglass Anagram

```
[Bass: Active / Passive / Piezo]
             │
             ▼
[Block 1: Allomorph NAM Preamp]
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
allomorph/
├── README.md                              # Project vision, theory, architecture, and CLI guide
├── docs/                                  # In-depth technical guides
│   ├── architectural_guardrails.md        # Master mathematical reference handbook & derivations
│   ├── dsp_simulation_engine.md           # Virtual Analog SIMD simulation engine & Numba JIT
│   ├── configuration_reference.md         # Complete schema & field reference for TOML configurations
│   ├── voice_catalog.md                   # Complete passive pickup technical catalog & parameters
│   ├── circuit_theory.md                  # RLC, eddy current, and cable impedance math
│   ├── aperture_math.md                   # Magnetic aperture sinc, multi-string & scale physics
│   └── anagram_workflow.md                # Darkglass Anagram Block 1 routing & gain staging
├── circuits/                              # Standalone SPICE netlists (.cir)
│   ├── sources/                           # Active, passive, and commercial source instrument netlists
│   ├── 01_modern_jazz_active.cir          # Sadowsky active 2-band isolated Jazz pair
│   ├── 02_jazz_bass_pair.cir              # Dual single-coils in parallel (tone open)
│   ├── 02b_jazz_bass_pair_22nf.cir        # Vintage J-pair with 22nF ToneStyler
│   ├── 02c_jazz_bridge_growl_bias.cir     # Jaco bridge-biased Jazz pair (55k pot decoupling)
│   ├── 03_jazz_bridge_60s.cir             # 60s bridge single-coil
│   ├── 04_modern_p_ceramic.cir            # Modern ceramic split-coil P (500k)
│   ├── 05_vintage_62_p_alnico.cir         # Vintage '62 Alnico V split-P (tone open)
│   ├── 05b_vintage_62_p_22nf.cir          # Vintage '62 split-P with 22nF ToneStyler
│   ├── 05c_vintage_62_p_47nf.cir          # Vintage '62 split-P with 47nF ToneStyler (Motown)
│   ├── 05d_vintage_50s_p_100nf.cir        # Vintage '50s split-P with 100nF ToneStyler
│   ├── 07_modern_pj_active.cir            # Modern active P/J
│   ├── 08_vintage_pj_passive.cir          # Vintage '80s passive P/J
│   ├── 09_stingray_mm_parallel.cir        # Music Man parallel humbucker
│   ├── 09b_stingray_mm_series.cir         # Music Man series humbucker with active buffer
│   ├── 10_rickenbacker_bridge_hpf.cir     # 4003 bridge with 4.7nF series HPF
│   ├── 11_pmm_hybrid_series.cir           # P/MM hybrid in series
│   ├── 12_mudbucker_ultra_series.cir      # Overwound series humbucker
│   ├── 13_dingwall_multiscale_bridge.cir  # Multi-scale angled bridge position
│   ├── 14_upright_bridge_transducer.cir   # Upright piezo bridge transducer
│   ├── 15_passive_character.cir           # Pure passive dynamic feel without EQ coloring
│   └── 16_active_character.cir            # Studio active buffer digital twin (cable isolation)
├── config/                                # Modular TOML configuration files
│   ├── instruments/                       # Source bass geometries, pickups & routing
│   │   ├── 30in_emg_mmtw.toml             # 30" active EMG MMTW dual-mode bass
│   │   ├── 32in_custom_pmm.toml           # 32" custom PX + MMTWX bass
│   │   ├── 34in_standard_p.toml           # 34" standard P-bass template
│   │   └── 34in_standard_jazz.toml        # 34" standard Jazz bass template
│   ├── scales.toml                        # Scale lengths & baseline string wave speeds
│   ├── strings.toml                       # Physical string core/wrap mechanical presets
│   └── voices.toml                        # Voice metadata linking to SPICE netlists
├── scripts/                               # Generation utilities (Python / uv)
│   ├── model_physics.py                   # Aperture sinc, scale wave speeds, and FIR engine
│   ├── analyze_voices.py                  # Polars + Altair frequency curve visualizer
│   ├── prep_nam_audio.py                  # Aperture & scale tension pre-filtering for NAM
│   ├── simulate_circuits.py               # Native Apple Silicon WAV SPICE circuit engine
│   └── run_pipeline.py                    # Master end-to-end automated runner
├── tests/                                 # Pytest test suite (160 tests)
└── models/                                # Exported .nam neural models
```

---

## Roadmap

### Completed Milestones
- [x] **Electro-Acoustic Physical Modeling:** Magnetic aperture sinc filtering, spatial comb nulls, scale-length wave-speed scaling ($30''/32'' \to 34''/37''$), 2D rod apertures, saddle boundary layer stiffness, longitudinal clank, and differential string tension modeling.
- [x] **Native WAV SPICE Simulator:** High-performance Apple Silicon engine (`scripts/simulate_circuits.py`) solving analytical nodal RLC equations, Foster 2-stage core eddy diffusion, Dahl magnetic domain-wall pinning hysteresis, asymmetric magnet saturation compliance, sub-audible 8 Hz DC blocking, passive RLC Johnson noise dither, and automatic output level normalization based on input sweep dBFS at >1500x speed.
- [x] **21 Voice Profiles & Transducers:** Modern active 2-band Jazz, vintage single-coil, split-coil, series/parallel dual-coils, active Music Man, fanned multi-scale, upright double-bass bridge piezo force transducers, and flat dynamic twins.
- [x] **Interactive Visualization Portal:** Polars + Altair frequency response portal with spec sheets and per-instrument interactive charts (`docs/frequency_responses.html`).
- [x] **Automated NAM Training Pipeline:** End-to-end Architecture 2 (A2) neural model training targeting Darkglass Anagram Block 1.
- [x] **Automated Test Suite:** Comprehensive 160-test pytest verification covering physical filters, nodal transfer functions, FIR DSP, audio simulation, and architectural guardrails.

### Upcoming Objectives
- [ ] **Interactive A/B Audio Auditioning CLI:** Terminal and real-time audio auditioning tool (`scripts/preview_voices.py`) with seamless dry-to-wet switching, looping bass riffs, and instantaneous A/B comparison across pickup voices before neural training or pedalboard export.
- [ ] **Hardware Reference Calibration:** Dry-DI spectral matching and A/B verification against physical vintage instruments (1962 P-Bass, 1975 Jazz Bass, 1979 StingRay).
- [ ] **In-Browser Audio Player:** Interactive audio preview player embedded directly into the Altair documentation portal.
- [ ] **Anagram Marketplace Native Block:** Develop a dedicated, all-in-one "Allomorph" custom block for the Darkglass Anagram Marketplace (`marketplace.anagram.shop`), featuring rotary voice switching across all 21 pickup configurations, automatic gain normalization, and interactive volume/cable load controls in a single native Block 1 module.

---

## Contributing

We welcome community contributions, netlists, and optimizations! Because Allomorph uses a dual-licensing model, all contributors must agree to the [Contributor License Agreement](CLA.md) via standard commit sign-off (`git commit -s`).

Please see [`CONTRIBUTING.md`](CONTRIBUTING.md) for full development setup, coding guidelines, and pull request instructions.

---

## License

This project and its distributed assets are licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE).

### Scope & Permissions
- **Permitted Uses:** Free to use, study, modify, and distribute for personal study, experimentation, sound design, and noncommercial music production.
- **Coverage:** This license applies to all source code, SPICE netlists, configuration schemas, compiled/trained neural models (`.nam`), and synthesized impulse responses (`.wav`) generated by or distributed with Allomorph.
- **Commercial Restrictions:** Commercial use, sale, bundling into commercial plugins/pedalboards, or monetization of the software, neural profiles, or impulse responses is strictly prohibited without prior written permission and a commercial license from the author.
- **Commercial Licensing Inquiries:** Contact **Peter Nguyen** (<peter@phn.dev>).

