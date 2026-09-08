# Passivizer

**Passivizer** is an analog modeling and digital twin pipeline that transforms active, wideband, low-impedance bass pickup signals—specifically **EMG X-Series (18V)**—into authentic emulations of high-impedance **passive pickup circuits**.

Designed specifically to feed modelers like the **Darkglass Anagram**, Helix, Quad Cortex, and DAW plugin hosts, Passivizer produces both:
1. **Minimum-Phase Impulse Responses (IRs):** High-precision 48 kHz / 24-bit FIR filters for fast, zero-latency pickup re-voicing.
2. **Neural Amp Modeler (NAM) Profiles:** Nano/Feather neural models trained on SPICE circuit simulations to capture dynamic magnetic saturation, eddy-current damping, volume pot loading, and treble-bleed interactions.

---

## The Philosophy: Why "Active to Passive"?

In modern bass signal chains, trying to convert a passive bass to sound active with digital EQ/IRs runs into fundamental mathematical limits: high-frequency content has already been attenuated by the passive coil's 12 dB/octave low-pass filter. Boosting those missing frequencies elevates noise and introduces comb-filtering artifacts.

**Passivizer flips this relationship:**
* **Source (EMG X-Series @ 18V):** Delivers a flat, wideband (20 Hz – 20+ kHz), high-headroom, low-noise signal with near-zero inductive peaking.
* **Target (Passive Circuit):** Fundamentally subtractive, resonant, and capacitive. 

Because the active source delivers an unclipped, full-bandwidth signal, Passivizer can carve out the exact physical and electrical transfer function of any passive pickup without boosting background hiss or running into phase smearing.

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
   ├── Master Volume Potentiometer (500k Dunlop audio taper)
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

## Target Voice Catalog (10 Master Passive Pickup Configurations + Multi-Scale)

Passivizer includes pre-configured physical and electrical parameters for **10 distinct pickup topologies and combinations** plus a fanned-fret multi-scale configuration (see [`docs/voice_catalog.md`](file:///Users/peter/Projects/pethin/passivizer/docs/voice_catalog.md) for full engineering specifications):

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

---

## SPICE $\to$ NAM Pipeline & CLI Usage

Passivizer models the acoustic aperture and scale tension in Python, feeds the pre-filtered signal into LTspice circuit digital twins, and trains lightweight NAM (`.nam`) neural captures for Block 1 of the Darkglass Anagram:

### 1. Interactive Acoustic & Electrical Visualizer (`scripts/analyze_voices.py`)
Renders interactive frequency response curves in Altair (Vega-Lite), comparing all 11 passive configurations against the source instrument:

```bash
# Generate interactive chart for 30" short-scale source bass:
uv run python scripts/analyze_voices.py --source-scale 30in

# Generate interactive chart for 32" medium-scale source bass:
uv run python scripts/analyze_voices.py --source-scale 32in
```
*Outputs: Standalone interactive HTML visualizer at `docs/frequency_responses.html`.*

### 2. Acoustic Pre-Filtering (`scripts/prep_nam_audio.py`)
Applies aperture de-humbucking, spatial displacement ($\Delta x$), and string tension filtering to NAM calibration audio (`v1_1_1.wav`) using Spotify's `pedalboard` SIMD convolution engine in under 200 ms:

```bash
# Pre-filter audio for Modern Ceramic P from a 30" source bass:
uv run python scripts/prep_nam_audio.py --source-scale 30in --voice 03_modern_p_ceramic

# Pre-filter audio for Dingwall Multi-Scale Bridge:
uv run python scripts/prep_nam_audio.py --source-scale 30in --voice 11_dingwall_multiscale_bridge
```
*Outputs: `circuits/v1_1_1_aperture.wav` ready to drive SPICE transient simulation.*

### 3. Headless SPICE Circuit Twin Simulation (`circuits/*.cir`)
Streams the acoustic pre-filtered audio through physical digital twins of passive pickup coils, eddy-current damping, Dunlop 500k volume pot, hybrid treble bleed, cable capacitance, and pedalboard input impedance:

```bash
# Run headless SPICE simulation via LTspice on macOS:
/Applications/LTspice.app/Contents/MacOS/LTspice -b circuits/03_modern_p_ceramic.cir
```

### 4. NAM Neural Model Training
Trains a lightweight `nano` or `feather` architecture model on the input/output audio pair for zero-latency, non-linear hardware execution:

```bash
# Train lightweight nano model for Darkglass Anagram Block 1:
nam train circuits/v1_1_1_aperture.wav circuits/03_modern_p_ceramic.wav ./models/03_modern_p_ceramic --architecture "nano"
```

### 5. Master Automation Runner (`scripts/run_pipeline.py` & `main.py`)
Execute the entire pipeline or specific stages with a single command:

```bash
# Run complete pipeline for 30" source instrument:
uv run python main.py --source-scale 30in

# Run only visualization:
uv run python main.py --stage viz

# Run audio pre-filtering for a specific voice:
uv run python main.py --stage prep --voice 07_stingray_mm_parallel
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
├── scripts/                               # Generation utilities (Python / uv)
│   ├── model_physics.py                   # Aperture sinc, scale wave speeds, and FIR engine
│   ├── analyze_voices.py                  # Polars + Altair frequency curve visualizer
│   ├── prep_nam_audio.py                  # Aperture & scale tension pre-filtering for NAM
│   └── run_pipeline.py                    # Master end-to-end automated runner
├── tests/                                 # Pytest test suite (16 tests)
└── models/                                # Exported .nam neural models
```

---

## Roadmap

### Phase 1: Architecture & Modeling Definition
- [x] Project initialization with `uv`
- [x] Technical documentation suite (`docs/voice_catalog.md`, `circuit_theory.md`, `aperture_math.md`, `anagram_workflow.md`)
- [x] Master passive pickup catalog covering single-coil, split-coil, dual-coil, series/parallel hybrids, and fanned multi-scale

### Phase 2: SPICE Circuit Digital Twins
- [x] 11 Parameterized SPICE netlists with Dunlop pot, hybrid treble bleed, and cable loading (`circuits/*.cir`)
- [x] Specialty circuit digital twins: Rickenbacker $4.7\text{ nF}$ series HPF, Motown $47\text{ nF}$ tone shunt, and Dingwall multi-scale bridge

### Phase 3: Spatial Placement & Scale-Length Engine
- [x] Integration of 30" EMG MM datum ($77.5\text{ mm}$ from bridge) and 32" P/MM datums
- [x] Scale-length wave-speed scaling ($\kappa_v$) for 30"/32" $\to$ 34" and 37" Multi-Scale conversion
- [x] String tension & piano-clank filter modeling ($H_{\text{tension}}$)
- [x] Pre-filtering utility for NAM audio (`scripts/prep_nam_audio.py`)
- [x] Pure-Python minimum-phase FIR synthesis engine (`scripts/model_physics.py`)

### Phase 4: Pipeline Automation & Verification
- [x] Install project Python dependencies with `uv` on Python 3.14 (`polars`, `altair`, `pedalboard`, `pytest`)
- [x] Automated end-to-end runner (`scripts/run_pipeline.py` & `main.py`) for Altair charts, audio pre-filtering, and SPICE simulations
- [x] Comprehensive `pytest` test suite (16 tests) for aperture sinc/comb math, minimum-phase FIR DSP, voice catalogs, visualizer, and audio pipeline (`uv run pytest`)

### Phase 5: Hardware & Modeler Integration (Upcoming)
- [ ] Darkglass Suite preset pack export bundle (`.darkglass` XML format)
- [ ] A/B verification and dry-DI calibration against reference recordings
