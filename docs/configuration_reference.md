# Passivizer Configuration Reference

This guide provides a comprehensive specification of all configuration files in **Passivizer**, their schemas, data types, physical units, mathematical implications, and constraints.

---

## 1. Overview of Configuration Files

Passivizer organizes instrument models, target voices, and physical scale wave speeds under the `config/` directory:

```
config/
├── instruments/              # Physical source instruments (the bass in the player's hands)
│   ├── 30in_emg_mmtw.toml    # 30" Short scale with EMG MMTW dual-mode pickup
│   ├── 32in_custom_pmm.toml  # 32" Medium scale with Reverse PX + MMTWX + ABCX active blend
│   ├── 32in_fretless_pmm.toml # 32" Fretless Medium scale with Reverse PX + MMTWX
│   ├── 34in_active_p.toml    # 34" Standard scale Active Precision Bass (EMG PX)
│   ├── 34in_active_jazz.toml # 34" Standard scale Active Jazz Bass (EMG JX pair)
│   ├── 34in_active_pj.toml   # 34" Standard scale Active P/J Bass (EMG PX + JX)
│   ├── 34in_standard_p.toml  # 34" Standard Fender Precision Bass (passive datum)
│   └── 34in_standard_jazz.toml # 34" Standard Fender Jazz Bass (passive datum)
├── scales.toml               # Physical scale lengths, wave speeds, and string dispersion
└── voices.toml               # Master target passive pickup voices & SPICE netlist links
```

---

## 2. Instrument Configuration Schema (`config/instruments/*.toml`)

An instrument configuration represents a **physical source bass** whose active signal is fed into Passivizer. It defines the instrument's vibrating scale length, string wave speeds, onboard pickups, physical coil locations, and the mapping from target voices to physical switch positions.

### Root Table Parameters

| Field | Type | Units | Required | Description |
| :--- | :--- | :--- | :---: | :--- |
| `id` | `string` | — | **Yes** | Unique identifier (e.g. `"30in_emg_mmtw"`). Used by CLI `--instrument <id>`. |
| `name` | `string` | — | **Yes** | Human-readable label (e.g. `"30\" Short Scale MM (EMG MMTW)"`). Embedded in NAM metadata. |
| `scale_length_in` | `float` | Inches | **Yes** | Vibrating string scale length in inches (e.g. `30.0`, `32.0`, `34.0`). |
| `scale_length_m` | `float` | Meters | **Yes** | Scale length in meters ($L_{\text{m}} = L_{\text{in}} \times 0.0254$). |
| `string_wave_speeds`| `array[float]`| m/s | **Yes** | Array of 4 (or 5) wave speeds from low to high string ($v = 2 \cdot L \cdot f_0$). |
| `default_pickup` | `string` | — | **Yes** | Pickup key within `[pickups]` used when no voice mapping or override is provided. |

#### Example:
```toml
id = "30in_emg_mmtw"
name = "30\" Short Scale MM (EMG MMTW)"
scale_length_in = 30.0
scale_length_m = 0.762
string_wave_speeds = [62.79, 83.82, 111.89, 149.35]
default_pickup = "mmtw_dual"
```

---

### Pickup Definitions (`[pickups.<pickup_id>]`)

Each entry defines a **physically selectable state** on the instrument (e.g., solo neck pickup, solo bridge dual-coil, single-coil split mode, or center-detent active blend).

> [!IMPORTANT]
> **Active Electronics Constraint:**
> All defined pickups must reflect **physically real switch/potentiometer states** on the actual instrument. For example:
> * Active pickups (EMG) cannot be wired in series. Active blends (e.g. EMG ABCX) operate strictly in **parallel**.
> * An EMG MMTW push/pull switch activates coils **L1 + L2** (dual-coil) or **L2 + L3** (bridge single-coil). There is no neck-coil-only mode.

| Field | Type | Units | Default | Description |
| :--- | :--- | :--- | :---: | :--- |
| `name` | `string` | — | Required | Descriptive label of the pickup / switch mode. |
| `position_from_bridge_m` | `float` | Meters | Required | Centerline distance from bridge saddle ($x = \text{datum}_{\text{mm}} / 1000$). |
| `aperture_width_in` | `float` | Inches | Required | Total magnetic sensing aperture width ($w$). |
| `coil_spacing_in` | `float` | Inches | `0.0` | Center-to-center distance ($d$) between dual coils. `0.0` for single-coils. |
| `type` | `string` | — | Required | Pickup architecture: `"single_coil"`, `"dual_coil_parallel"`, `"split_coil"`, or `"composite"`. |
| `resonant_frequency_hz` | `float` | Hz | Optional | Internal electrical resonant peak frequency ($f_r$) of the active preamp. |
| `q_factor` | `float` | — | `1.35` | Quality factor ($Q$) of the internal active resonant bump. |
| `coils` | `array[table]`| — | Optional | Array of individual physical coils for precise multi-coil/staggered acoustic modeling. |
| `components` | `array[table]`| — | Optional | Array of sub-pickups for active parallel blends (used when `type = "composite"`). |

---

### Sub-Coil Modeling (`coils = [...]`)

When a pickup consists of multiple or staggered coils (such as a split-coil Precision Bass or a dual-coil Music Man), the `coils` array models the spatial standing-wave envelope for each coil individually.

| Field | Type | Units | Default | Description |
| :--- | :--- | :--- | :---: | :--- |
| `strings` | `array[string]` | — | `["all"]` | String bindings for this coil half: `["all"]`, `["E", "A"]`, or `["D", "G"]`. |
| `position_from_bridge_m` | `float` | Meters | Required | Physical distance from bridge saddle to this individual coil center. |
| `aperture_width_in` | `float` | Inches | Required | Magnetic aperture width of this specific coil. |
| `weight` | `float` | — | `1.0` | Amplitude contribution (e.g. `0.5` for two coils in parallel). |
| `polarity` | `float` | — | `1.0` | Phase polarity (`1.0` for in-phase, `-1.0` for reverse phase). |

#### Example: EMG MMTW Dual-Coil vs. Single-Coil
```toml
[pickups.mmtw_dual]
name = "EMG MMTW Dual-Coil (Centerline)"
position_from_bridge_m = 0.0775
aperture_width_in = 1.50
coil_spacing_in = 0.90
type = "dual_coil_parallel"
resonant_frequency_hz = 2500.0
q_factor = 1.35
coils = [
    { strings = ["all"], position_from_bridge_m = 0.08893, aperture_width_in = 0.75, weight = 0.5 },
    { strings = ["all"], position_from_bridge_m = 0.06607, aperture_width_in = 0.75, weight = 0.5 }
]

[pickups.mmtw_single]
name = "EMG MMTW Single-Coil (Bridge Coil)"
position_from_bridge_m = 0.06607
aperture_width_in = 0.75
coil_spacing_in = 0.0
type = "single_coil"
resonant_frequency_hz = 3500.0
q_factor = 1.40
coils = [
    { strings = ["all"], position_from_bridge_m = 0.06607, aperture_width_in = 0.75, weight = 1.0 }
]
```

#### Example: Reverse Split-Coil Precision Pickup
```toml
[pickups.px]
name = "Reverse EMG PX Split-Coil (Neck)"
position_from_bridge_m = 0.1228
aperture_width_in = 1.10
coil_spacing_in = 0.0
type = "split_coil"
resonant_frequency_hz = 3200.0
q_factor = 1.40
coils = [
    # D/G coil is staggered further towards the neck (136.8mm)
    { strings = ["D", "G"], position_from_bridge_m = 0.1368, aperture_width_in = 1.10, weight = 1.0 },
    # E/A coil is staggered closer towards the bridge (108.8mm)
    { strings = ["E", "A"], position_from_bridge_m = 0.1088, aperture_width_in = 1.10, weight = 1.0 }
]
```

---

### Composite Active Blends (`type = "composite"`)

For instruments with an active blend control (like the **EMG ABCX**), the blend is modeled as an active parallel mix of individual pickups defined within the same file.

| Field | Type | Description |
| :--- | :--- | :--- |
| `components` | `array[table]` | List of sub-pickups and their blend proportions. |
| `components[i].pickup` | `string` | ID of the sub-pickup defined in `[pickups]`. |
| `components[i].weight` | `float` | Weighting factor (e.g. `0.5` for center detent). |

#### Example:
```toml
[pickups.blend_parallel]
name = "EMG PX + MMTWX Parallel (Center Detent)"
position_from_bridge_m = 0.0868
aperture_width_in = 0.88
coil_spacing_in = 0.0
type = "composite"
components = [
    { pickup = "px", weight = 0.5 },
    { pickup = "mmtwx_dual", weight = 0.5 }
]
```

---

### Voice Mapping (`[pickup_mapping]`)

The `[pickup_mapping]` table routes each of the 11 target passive profiles to the optimal physical pickup setting on the player's instrument:

```toml
[pickup_mapping]
"01_jazz_bass_pair" = "blend_parallel"   # Center detent active blend
"02_jazz_bridge_60s" = "mmtwx_single"    # Solo bridge single-coil
"03_modern_p_ceramic" = "px"             # Solo neck split-coil
"04_vintage_62_p_alnico" = "px"          # Solo neck split-coil
"05_p_bass_47nf_rolloff" = "px"          # Solo neck split-coil
"06_pj_hybrid_parallel" = "blend_parallel"
"07_stingray_mm_parallel" = "mmtwx_dual" # Solo bridge dual-coil
"08_rickenbacker_bridge_hpf" = "mmtwx_single"
"09_pmm_hybrid_series" = "blend_parallel" # Physical parallel blend -> SPICE series twin
"10_mudbucker_ultra_series" = "px"       # Solo neck pickup -> SPICE mudbucker twin
"11_dingwall_multiscale_bridge" = "mmtwx_dual"
```

---

## 3. Scale Lengths & Wave Speeds (`config/scales.toml`)

`config/scales.toml` defines the standard physical scales used for target acoustic scaling and wave speed calculations:

$$v_s = 2 \cdot L \cdot f_{0,s}$$

| Key | Type | Units | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | — | Display label of the scale standard. |
| `scale_length_in` | `float` | Inches | Vibrating string length. |
| `scale_length_m` | `float` | Meters | Vibrating string length in meters. |
| `string_wave_speeds` | `array[float]` | m/s | Array of wave speeds for standard bass tuning ($E_1=41.2\text{ Hz}$, $A_1=55.0\text{ Hz}$, $D_2=73.4\text{ Hz}$, $G_2=98.0\text{ Hz}$). |

#### Supported Scales:
* **`30in`:** Short scale ($L = 0.762\text{ m}$, $v = [62.79, 83.82, 111.89, 149.35]\text{ m/s}$)
* **`32in`:** Medium scale ($L = 0.8128\text{ m}$, $v = [66.98, 89.41, 119.35, 159.31]\text{ m/s}$)
* **`34in`:** Standard long scale ($L = 0.8636\text{ m}$, $v = [71.16, 95.00, 126.81, 169.27]\text{ m/s}$)
* **`multiscale`:** Fanned-fret Dingwall scale ($34''\text{--}37''$, $v = [77.44, 98.50, 131.00, 169.27]\text{ m/s}$)

---

## 4. Target Voice Definitions (`config/voices.toml`)

`config/voices.toml` links each of the 12 digital twin voices to its WAV SPICE netlist (`circuits/*.cir`) and acoustic parameters. Passivizer's built-in WAV SPICE simulator directly parses and evaluates these netlists on audio streams:

| Field | Type | Units | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | — | Full display name (e.g. `"03. Modern Split-Coil P (Ceramic)"`). |
| `circuit` | `string` | Path | Relative path to standalone SPICE netlist (`circuits/03_modern_p_ceramic.cir`). |
| `topology` | `string` | — | Circuit topology classification (e.g. `"Split-Coil Ceramic"`). |
| `description` | `string` | — | Tonal character, reference pickup model, and hardware notes. |
| `fr` | `float` | Hz | Target electrical resonant peak frequency under load (composite/single pickup). |
| `Q` | `float` | — | Target electrical quality factor under pot and cable load (composite/single pickup). |
| `gain_db` | `float` | dB | Output gain trim for volume normalization. |
| `scale` | `string` | Key | Target scale key in `scales.toml` (`"34in"` or `"multiscale"`). |
| `hpf` | `float` | Hz | *(Optional)* High-pass filter cutoff frequency (e.g. $150.0\text{ Hz}$ for Rickenbacker). |
| `coils` | `array[table]` | — | **Flattened Coil Array:** Physical sensing coils with string bindings and positions. |
| `pickups` | `array-of-tables` | — | *(Optional)* **Multi-Pickup Array:** Independent pickups with individual resonant frequencies and quality factors. |

### Multi-Pickup Definitions (`[[voices.<id>.pickups]]`)

For instruments combining multiple pickups (such as P/J, Jazz Bass pairs, and P/MM), each pickup is modeled with its own independent electrical RLC resonant peak ($f_r$, $Q$), blend weight, and physical coils:

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | `"Pickup"` | Display name for the pickup (e.g. `"Precision Split-Coil (Neck)"`). |
| `type` | `string` | `"single_coil"` | Classification (`"split_coil"`, `"single_coil"`, `"dual_coil_parallel"`). |
| `fr` | `float` | **Required** | Standalone electrical resonant frequency in Hz under load. |
| `Q` | `float` | `1.5` | Quality factor under pot and cable load. |
| `weight` | `float` | `1.0` | Relative blend/sum weight (e.g. `0.5` for 50/50 parallel blend). |
| `polarity` | `float` | `1.0` | Phase polarity (`+1.0` in-phase, `-1.0` reverse). |
| `coils` | `array[table]` | **Required** | Sensing coils belonging to this specific pickup. |

### Target Voice Multi-Pickup Examples

#### 1. Compound 3-Coil P/J Hybrid (Dual Resonances)
```toml
[voices.06_pj_hybrid_parallel]
name = "06. P/J Hybrid (Parallel)"
circuit = "circuits/06_pj_hybrid_parallel.cir"
topology = "P/J Parallel Sum"
blend_mode = "parallel"
fr = 3600.0  # Composite equivalent resonant peak
Q = 1.4
gain_db = 0.8
scale = "34in"
coils = [
    { strings = ["E", "A"], position_from_bridge_m = 0.1390, aperture_width_in = 1.00, weight = 0.5 },
    { strings = ["D", "G"], position_from_bridge_m = 0.1110, aperture_width_in = 1.00, weight = 0.5 },
    { strings = ["all"],    position_from_bridge_m = 0.0406, aperture_width_in = 0.75, weight = 0.5 }
]

[[voices.06_pj_hybrid_parallel.pickups]]
name = "Precision Split-Coil (Neck)"
type = "split_coil"
fr = 2200.0
Q = 1.8
weight = 0.5
coils = [
    { strings = ["E", "A"], position_from_bridge_m = 0.1390, aperture_width_in = 1.00, weight = 1.0 },
    { strings = ["D", "G"], position_from_bridge_m = 0.1110, aperture_width_in = 1.00, weight = 1.0 }
]

[[voices.06_pj_hybrid_parallel.pickups]]
name = "70s Jazz Single-Coil (Bridge)"
type = "single_coil"
fr = 3200.0
Q = 1.6
weight = 0.5
coils = [
    { strings = ["all"], position_from_bridge_m = 0.0406, aperture_width_in = 0.75, weight = 1.0 }
]
```

#### 2. Dual Single-Coil Jazz Bass Pair
```toml
[voices.01_jazz_bass_pair]
name = "01. Jazz Bass Pair (Parallel)"
circuit = "circuits/01_jazz_bass_pair.cir"
topology = "Dual Single-Coil Parallel"
blend_mode = "parallel"
fr = 3900.0
Q = 1.3
gain_db = -0.5
scale = "34in"
coils = [
    { strings = ["all"], position_from_bridge_m = 0.1480, aperture_width_in = 0.75, weight = 0.5 },
    { strings = ["all"], position_from_bridge_m = 0.0406, aperture_width_in = 0.75, weight = 0.5 }
]

[[voices.01_jazz_bass_pair.pickups]]
name = "Jazz Single-Coil (Neck)"
type = "single_coil"
fr = 3600.0
Q = 1.5
weight = 0.5
coils = [
    { strings = ["all"], position_from_bridge_m = 0.1480, aperture_width_in = 0.75, weight = 1.0 }
]

[[voices.01_jazz_bass_pair.pickups]]
name = "70s Jazz Single-Coil (Bridge)"
type = "single_coil"
fr = 3200.0
Q = 1.6
weight = 0.5
coils = [
    { strings = ["all"], position_from_bridge_m = 0.0406, aperture_width_in = 0.75, weight = 1.0 }
]
```

*(Note: Single-pickup configurations specifying top-level `fr`, `Q`, and `coils` are automatically resolved into a canonical single-pickup structure by `resolve_voice_pickups()`.)*

---

## 5. How to Add a Custom Instrument

To model your own bass in Passivizer:

1. Create a new file: `config/instruments/my_bass.toml`.
2. Measure:
   * Scale length ($L_{\text{in}}$).
   * Pickup centerline distances from the bridge saddle in millimeters ($x_{\text{mm}}$).
   * Active pickup resonant frequency ($f_r$) from manufacturer spec sheets (if active).
3. Fill out the schema:
   ```toml
   id = "my_custom_5str"
   name = "Custom 35\" 5-String Soapbar"
   scale_length_in = 35.0
   scale_length_m = 0.889
   string_wave_speeds = [53.28, 71.16, 95.00, 126.81, 169.27]
   default_pickup = "bridge_dual"

   [pickups.bridge_dual]
   name = "Dual-Coil Soapbar (Bridge)"
   position_from_bridge_m = 0.055
   aperture_width_in = 1.25
   coil_spacing_in = 0.75
   type = "dual_coil_parallel"
   resonant_frequency_hz = 2800.0
   q_factor = 1.35
   coils = [
       { strings = ["all"], position_from_bridge_m = 0.0645, aperture_width_in = 0.60, weight = 0.5 },
       { strings = ["all"], position_from_bridge_m = 0.0455, aperture_width_in = 0.60, weight = 0.5 }
   ]
   ```
4. Run validation and preview:
   ```bash
   uv run python main.py --stage viz --instrument my_custom_5str
   ```
