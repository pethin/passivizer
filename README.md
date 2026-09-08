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

## Target Voice Catalog (10 Master Genre-Proof Profiles)

Passivizer includes pre-configured physical and electrical parameters for **10 distinct pickup topologies and combinations** engineered specifically to eliminate blindspots across **Jazz, Rock, Metal, Anisong, Pop, Stoner, Prog, J-Jazz, J-Rock, and J-Metal** (see [`docs/voice_catalog.md`](file:///Users/peter/Projects/pethin/passivizer/docs/voice_catalog.md) for full engineering specifications and band mix roles):

| # | Profile ID | Pickup Type | Topology | $L_{\text{eq}}$ | $f_r$ (Peak) | Primary Musical Genre & Character |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| **01** | `01_j_jazz_atelier_pair` | J-Bass Pair | Dual Parallel | $1.69\text{ H}$ | $3.9\text{ kHz}$ | **J-Jazz / Anisong / Pop Slap:** Atelier Z / Sadowsky Tokyo symmetrical 1 kHz scoop. |
| **02** | `02_jaco_fusion_bridge` | J-Bass Bridge | Single Coil | $3.60\text{ H}$ | $3.2\text{ kHz}$ | **Jazz / J-Fusion Soloing:** Maximum staccato articulation, 1.2 kHz fingerstyle burp. |
| **03** | `03_jrock_modern_p` | Split P-Bass | Single Split | $4.80\text{ H}$ | $2.2\text{ kHz}$ | **J-Rock / Anisong Pick:** Bartolini 8CBP ceramic attack; cuts through dense distorted guitars. |
| **04** | `04_vintage_62_alnico_p` | Split P-Bass | Single Split | $3.80\text{ H}$ | $2.8\text{ kHz}$ | **Classic Rock / Pop / Blues:** Organic, dynamic, uncompressed woody breath. |
| **05** | `05_motown_neo_soul_dub` | Split P-Bass | Split w/ 47nF | $4.80\text{ H}$ | $0.45\text{ kHz}$| **Neo-Soul / Reggae / Dub:** Tone rolled to 0; deep, pillowy thumb-and-palm-mute thud. |
| **06** | `06_studio_workhorse_pj` | P + J Hybrid | Parallel Sum | $2.06\text{ H}$ | $3.6\text{ kHz}$ | **Everyday Rock / Studio Pop:** The #1 recorded hybrid: P-thump + J-snap. |
| **07** | `07_jmetal_prog_stingray` | MM Humbucker | Dual Parallel | $2.40\text{ H}$ | $3.5\text{ kHz}$ | **J-Metal / Prog / Djent:** StingRay clank into Darkglass drives; tight, fast lows. |
| **08** | `08_prog_rick_clank` | High-Pass Bridge | Series HPF | $3.80\text{ H}$ | $2.2\text{ kHz}$ | **Prog Rock Pick:** Chris Squire / Geddy Lee / Tool aggressive midrange pick crunch. |
| **09** | `09_power_trio_bulldozer` | P + MM Hybrid | Series Sum | $7.20\text{ H}$ | $2.0\text{ kHz}$ | **Hard Rock / Metal Solos:** $+5.8\text{ dB}$ low-mid wall that fills the mix for power trios. |
| **10** | `10_stoner_doom_mudbucker` | Heavy Series MM | Ultra Series | $14.40\text{ H}$| $1.2\text{ kHz}$ | **Stoner / Doom / Sludge:** Earth-shattering sub-bass; tames fuzz-pedal top-end fizz. |

---

## Two Output Pipelines & CLI Usage

### 1. The Fast Linear IR Pipeline (`scripts/generate_irs.py`)
Generates 2048-tap, minimum-phase Impulse Responses for loading directly into hardware IR blocks (e.g., the Darkglass Anagram's Cab/IR Loader block).
* **Zero Latency:** Instant preset switching at your feet.
* **Multi-String Wave Speed Integration:** Eliminates harsh aperture notches across strings.
* **Full Scale & Placement Conversion:** Maps from 30" or 32" bridge datums into standard 34" and 37" multi-scale tones.

```bash
# Generate IRs from your 30" single EMG MM bass into 34" / 37" target tones:
uv run python scripts/generate_irs.py --source-scale 30in

# When your 32" medium-scale P/MM bass is complete:
uv run python scripts/generate_irs.py --source-scale 32in
```
*Outputs: 48 kHz / 24-bit `.wav` files into `passivizer/irs/`.*

### 2. The SPICE $\to$ NAM Pipeline (`circuits/` & `scripts/prep_nam_audio.py`)
Generates Neural Amp Modeler (`.nam`) captures trained on electrical circuit simulations:
1. **Pre-Filter (`prep_nam_audio.py`):** Pre-filters the official NAM calibration file (`v1_1_1.wav`) using Spotify's `pedalboard` SIMD convolution engine, applying aperture de-humbucking, spatial displacement ($\Delta x$), and string tension filtering in under 200 ms.
2. **SPICE Simulation (`circuits/*.cir`):** Streams the pre-filtered audio through the digital twin of the passive coils, eddy currents, Dunlop 500k pot, treble bleed, and cable.
3. **NAM Neural Training:** Trains a lightweight `nano` architecture model on the input/output audio pair.

```bash
# Pre-filter audio for a specific voice (e.g., J-Rock P-Bass on 30" source):
uv run python scripts/prep_nam_audio.py --source-scale 30in --target-scale 34in --voice 03_jrock_modern_p

# Pre-filter for a 34"-37" Dingwall-style multi-scale metal clank:
uv run python scripts/prep_nam_audio.py --source-scale 30in --target-scale multiscale --voice 07_dingwall_ng_multiscale

# Run SPICE headless simulation (via LTspice):
/Applications/LTspice.app/Contents/MacOS/LTspice -b circuits/03_jrock_modern_p.cir

# Train lightweight nano model for Darkglass Anagram:
nam train v1_1_1_03_jrock_modern_p_30in_to_34in.wav out_03_jrock_modern_p.wav ./models/03_jrock_modern_p --architecture "nano"
```

### 3. Master Automation Runner (`scripts/run_pipeline.py`)
Run all stages (IR generation, Altair interactive chart rendering, and SPICE batch) in a single command:

```bash
# Run complete pipeline for 30" single EMG MM bass:
uv run python scripts/run_pipeline.py --source-scale 30in

# Generate only IRs and interactive frequency chart:
uv run python scripts/run_pipeline.py --source-scale 30in --stage all
```

---

## Signal Flow on the Darkglass Anagram

```
[Bass: EMG PX / MMTWX @ 18V]
             │
             ▼
[Block 1: Passivizer Block]
   ├── Mode A: IR Loader ("01_j_jazz_atelier_pair_30in_to_34in.wav")
   └── Mode B: NAM Preamp ("07_jmetal_prog_stingray.nam")
             │
             ▼
[Block 2: Darkglass Preamp / Drive]
   └── Microtubes B7K, Vintage Deluxe, or Alpha·Omega
             │
             ▼
[Block 3: Speaker Cabinet IR]
   └── Ampeg 8x10, Darkglass 4x10, or custom speaker impulse
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
│   ├── voice_catalog.md                   # Complete 10-voice technical catalog & band roles
│   ├── circuit_theory.md                  # RLC, eddy current, and cable impedance math
│   ├── aperture_math.md                   # Magnetic aperture sinc, multi-string & scale physics
│   └── anagram_workflow.md                # Darkglass Anagram preset setup & gain staging
├── circuits/                              # 10 SPICE netlists & digital twins
│   ├── 01_j_jazz_atelier_pair.cir         # J-Jazz / Anisong Slap (Atelier Z / Sadowsky)
│   ├── 02_jaco_fusion_bridge.cir          # J-Fusion / Soloing Bark (Jaco 70s Bridge)
│   ├── 03_jrock_modern_p.cir              # J-Rock / Anisong Pick (Bartolini 8CBP)
│   ├── 04_vintage_62_alnico_p.cir         # Classic Rock / Blues (Vintage '62 Alnico P)
│   ├── 05_motown_neo_soul_dub.cir         # Neo-Soul / Reggae (Tone Rolled to 0 w/ 47nF)
│   ├── 06_studio_workhorse_pj.cir         # Everyday Rock / Pop (Studio P/J Parallel)
│   ├── 07_jmetal_prog_stingray.cir        # J-Metal / Prog / Djent (MM Parallel Clank)
│   ├── 08_prog_rick_clank.cir             # Prog Rock Pick (Rickenbacker 4003 Clank)
│   ├── 09_power_trio_bulldozer.cir        # Heavy Rock / Solos (P/MM Series Wall)
│   └── 10_stoner_doom_mudbucker.cir       # Stoner / Doom / Sludge (14.4H Fuzz Engine)
├── scripts/                               # Generation utilities (Python / uv)
│   ├── generate_irs.py                    # Linear minimum-phase IR generator with scale conversion
│   └── prep_nam_audio.py                  # Aperture & scale tension pre-filtering for NAM
├── irs/                                   # Exported WAV impulse responses (48kHz / 24-bit)
└── models/                                # Exported .nam neural models
```

---

## Roadmap

### Phase 1: Architecture & Modeling Definition
- [x] Project initialization with `uv`
- [x] Technical documentation suite (`docs/voice_catalog.md`, `circuit_theory.md`, `aperture_math.md`, `anagram_workflow.md`)
- [x] Master 10-voice genre-proof catalog spanning Jazz, Rock, Metal, Anisong, Pop, Stoner, Prog, J-Jazz, J-Rock, J-Metal

### Phase 2: SPICE Circuit Digital Twins
- [x] 10 Parameterized SPICE netlists with Dunlop pot, hybrid treble bleed, and cable loading (`circuits/*.cir`)
- [x] Specialty circuit digital twins: Rickenbacker $4.7\text{ nF}$ series HPF & Motown $47\text{ nF}$ tone shunt

### Phase 3: Spatial Placement & Scale-Length Engine
- [x] Integration of 30" EMG MM datum ($77.5\text{ mm}$ from bridge) and 32" P/MM datums
- [x] Scale-length wave-speed scaling ($\kappa_v$) for 30"/32" $\to$ 34" and 37" Multi-Scale conversion
- [x] String tension & piano-clank filter modeling ($H_{\text{tension}}$)
- [x] Pre-filtering utility for NAM audio (`scripts/prep_nam_audio.py`)
- [x] Linear minimum-phase 48kHz / 24-bit IR generator (`scripts/generate_irs.py`)

### Phase 4: Pipeline Automation & Verification (Upcoming)
- [ ] Install project Python dependencies (`uv add polars altair pedalboard`)
- [ ] Automated end-to-end runner (`scripts/run_pipeline.py`) to execute batch SPICE runs and NAM rendering
- [ ] Pre-generate standard 48kHz / 24-bit IR release bundles into `irs/` for both 30" and 32" instruments

### Phase 5: Darkglass Ecosystem Integration (Upcoming)
- [ ] Darkglass Suite preset pack bundle (`.darkglass` XML format) connecting with `~/Projects/pethin/anagram-presets/`
- [ ] A/B verification and dry-DI calibration against reference recordings
