# Allomorph Configuration Reference

This guide provides a comprehensive specification of all configuration files in **Allomorph**, their schemas, data types, physical units, mathematical implications, and constraints.

---

## 1. Overview of Configuration Files

Allomorph organizes instrument models, target voices, and physical scale wave speeds under the `config/` directory:

```
config/
├── instruments/              # Physical source instruments (the bass in the player's hands)
│   ├── 30in_emg_mmtw.toml    # 30" Short scale with EMG MMTW dual-mode pickup
│   ├── 30in_mustang_pj.toml  # 30" Short scale Fender Mustang Bass PJ (passive split-P + single J)
│   ├── 32in_custom_pmm.toml  # 32" Medium scale with Reverse PX + MMTWX + ABCX active blend
│   ├── 32in_fretless_pmm.toml # 32" Fretless Medium scale with PCSX + MMTWX
│   ├── 34in_standard_p.toml  # 34" Standard Fender Precision Bass (passive datum)
│   ├── 34in_standard_jazz.toml # 34" Standard Fender Jazz Bass (passive datum)
│   ├── 34in_standard_pj.toml # 34" Standard P/J Bass (Fender PJ / Yamaha BB style)
│   ├── 34in_active_stingray.toml # 34" Standard Active StingRay (Music Man MM)
│   ├── 34in_active_soapbar.toml  # 34" Standard Active Dual-Soapbar (Ibanez SR / Yamaha TRBX)
│   ├── 34in_dingwall_sp1.toml    # 32"-35" Dingwall SP1 5-String (Dual-P + FD3n)
│   └── 37in_multiscale_dingwall.toml # 34"-37" Multi-Scale Dingwall 5-String Combustion / NG (FD3n)
├── preamps.toml              # Reusable active preamp catalog (Sadowsky, StingRay, Aguilar, Dingwall)
├── scales.toml               # Physical scale lengths, wave speeds, and string dispersion
├── strings.toml              # Physical string core/wrap presets
└── voices/                   # Master target passive pickup voices & embedded [circuit] tables
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
| `pole_type` | `string` | — | `"rod"` | Spatial pole geometry: `"rod"` (2D cylindrical pole disc) or `"blade"` (1D bar slit). |
| `magnet_type` | `string` | — | `"alnico_v"` | Core magnet alloy: `"alnico_v"`, `"alnico_ii"`, `"alnico_iii"`, `"ceramic"`, `"hybrid"`, `"neodymium"`, `"piezo"`, `"active"`, or `"ideal"` (pure linear reference). |
| `circuit` | `table` | — | Optional | Embedded declarative SPICE netlist table (`[pickups.<id>.circuit]`) defining RLC parameters. |
| `resonant_frequency_hz` | `float` | Hz | Optional | Internal electrical resonant peak frequency ($f_r$) of the active preamp. |
| `q_factor` | `float` | — | `1.35` | Quality factor ($Q$) of the internal active resonant bump. |
| `coils` | `array[table]`| — | Optional | Array of individual physical coils for precise multi-coil/staggered acoustic modeling. |
| `components` | `array[table]`| — | Optional | Array of sub-pickups for active parallel blends (used when `type = "composite"`). |

---

### Sub-Coil Modeling (`coils = [...]`)

When a pickup consists of multiple or staggered coils (such as a split-coil Precision Bass or a dual-coil Music Man), the `coils` array models the spatial standing-wave envelope for each coil individually.

| Field | Type | Units | Default | Description |
| :--- | :--- | :--- | :---: | :--- |
| `strings` | `array[string\|int]` | — | `["all"]` | String bindings for this coil half: `["all"]`, `["E", "A"]`, `["D", "G"]`, or register halves `[1, 2]` (treble) and `[3, 4]` (bass). |
| `position_from_bridge_m` | `float` | Meters | Required | Physical distance from bridge saddle to this individual coil center. |
| `aperture_width_in` | `float` | Inches | Required | Magnetic aperture width of this specific coil. |
| `weight` | `float` | — | `1.0` | Amplitude contribution (e.g. `0.5` for two coils in parallel). |
| `polarity` | `float` | — | `1.0` | Phase polarity (`1.0` for in-phase, `-1.0` for reverse phase). |
| `pole_type` | `string` | — | `"rod"` | Coil-specific spatial geometry override: `"rod"` or `"blade"`. |

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
* **`multiscale`:** Fanned-fret Dingwall scale ($34''\text{--}37''$, $L = 0.9398\text{ m}$, $v = [77.44, 98.50, 131.00, 169.27]\text{ m/s}$)
* **`multiscale_super`:** Compact fanned-fret Dingwall SP1 5-string ($32''\text{--}35''$, $L = 0.889\text{ m}$, $v = [54.88, 71.69, 93.60, 122.14, 159.31]\text{ m/s}$)
* **`upright`:** Standard 3/4 acoustic double bass ($41.5'' = 1.0541\text{ m}$, $v = [86.86, 115.95, 154.76, 206.59]\text{ m/s}$)

---

## 4. Target Voice Definitions (`config/voices/*.toml`)

`config/voices/*.toml` defines each of the 23 digital twin voices with its embedded declarative SPICE `[circuit]` table, acoustic coil geometry, physical strings, and non-linear magnetic properties. Allomorph's built-in WAV SPICE simulator directly parses and evaluates these netlists on audio streams:

| Field | Type | Units | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | — | Full display name (e.g. `"04. Modern Split-Coil P (Ceramic)"`). |
| `circuit` | `table` | — | Embedded declarative SPICE netlist table defining RLC components, active buffers, pots, and preamps. |
| `topology` | `string` | — | Circuit topology classification (`"Split-Coil Ceramic"`, `"Dual Single-Coil Active Buffer"`, etc.). |
| `description` | `string` | — | Tonal character, reference pickup model, and hardware notes. |
| `fr` | `float` | Hz | Target electrical resonant peak frequency under load (composite/single pickup). |
| `Q` | `float` | — | Target electrical quality factor under pot and cable load (composite/single pickup). |
| `gain_db` | `float` | dB | Output gain trim for volume normalization. |
| `scale` | `string` | Key | Target scale key in `scales.toml` (`"34in"`, `"multiscale"`, or `"upright"`). |
| `magnet_type` | `string` | Key | Core magnet metallurgy: `"alnico_v"`, `"alnico_ii"`, `"alnico_iii"`, `"ceramic"`, `"hybrid"`, `"neodymium"`, `"piezo"`, `"active"`, or `"ideal"`. |
| `alpha` | `float` | — | *(Optional)* Quadratic asymmetry coefficient override for 2nd-harmonic bloom. |
| `alpha3` | `float` | — | *(Optional)* Cubic dipole proximity factor override for 3rd-harmonic punch. |
| `k_sag` | `float` | — | *(Optional)* Dynamic Lenz-law core flux sag damping factor. |
| `k_eddy` | `float` | — | *(Optional)* Dynamic eddy-current core de-Qing factor. |
| `eta_hyst` | `float` | — | *(Optional)* Dahl magnetic domain-wall pinning hysteresis coupling factor. |
| `target_string` | `string` | Key | Goal string preset from `config/strings.toml` (e.g. `"flatwound_vintage_heavy"`). |
| `sensor_type` | `string` | `"magnetic"` | Physical sensor taxonomy: `"magnetic"`, `"bridge_force"`, or `"direct"`. |
| `no_eq` | `bool` | `false` | Set `true` in voice or circuit for pure non-linear dynamics with exact $0.00\text{ dB}$ flat transfer. |
| `preserve_aperture` | `bool` | `false` | Set `true` to preserve source instrument physical aperture (e.g. Character Voicings `15_neutral_character`, `15b_active_character`, `15c_passive_character`). |
| `hpf` | `float` | Hz | *(Optional)* High-pass filter cutoff frequency (e.g. $150.0\text{ Hz}$ for Rickenbacker). |
| `coils` | `array[table]` | — | **Flattened Coil Array:** Physical sensing coils with string bindings, positions, and pole types. |
| `pickups` | `array-of-tables` | — | *(Optional)* **Multi-Pickup Array:** Independent pickups with individual resonant frequencies, quality factors, and magnet metallurgies. |

### Multi-Pickup Definitions (`[[voices.<id>.pickups]]`)

For instruments combining multiple pickups (such as P/J, Jazz Bass pairs, and P/MM), each pickup is modeled with its own independent electrical RLC resonant peak ($f_r$, $Q$), blend weight, magnet metallurgy, and physical coils:

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | `"Pickup"` | Display name for the pickup (e.g. `"Modern Jazz Single-Coil (Neck)"`). |
| `type` | `string` | `"single_coil"` | Classification (`"split_coil"`, `"single_coil"`, `"dual_coil_parallel"`). |
| `magnet_type`| `string` | `"alnico_v"` | Pickup-specific magnet metallurgy. |
| `fr` | `float` | **Required** | Standalone electrical resonant frequency in Hz under load. |
| `Q` | `float` | `1.5` | Quality factor under pot and cable load. |
| `weight` | `float` | `1.0` | Relative blend/sum weight (e.g. `0.5` for 50/50 parallel blend). |
| `polarity` | `float` | `1.0` | Phase polarity (`+1.0` in-phase, `-1.0` reverse). |
| `coils` | `array[table]` | **Required** | Sensing coils belonging to this specific pickup. |

### Target Voice Multi-Pickup Examples

#### 1. Modern Active Jazz Bass Pair (`01_modern_jazz_active`)
```toml
# config/voices/01_modern_jazz_active.toml
name = "01. Modern Active Jazz Bass Pair"
topology = "Dual Single-Coil Active Buffer"
blend_mode = "parallel"
magnet_type = "alnico_v"
alpha = 0.25
fr = 4800.0  # High resonant peak due to zero cable capacitive loading on coils
Q = 1.6
gain_db = 1.0
scale = "34in"
coils = [
    { strings = ["all"], position_from_bridge_m = 0.1556, aperture_width_in = 0.75, weight = 0.5 }, # 60s Neck Single-Coil
    { strings = ["all"], position_from_bridge_m = 0.0635, aperture_width_in = 0.75, weight = 0.5 }  # 60s Bridge Single-Coil
]

[circuit]
topology = "parallel"
active = true
preamp = "sadowsky_2band"
Rvol = 500000.0

[circuit.neck]
L = 3.2
Rdc = 7200.0
Reddy = 135000.0
Ccoil = 7e-11

[circuit.bridge]
L = 3.6
Rdc = 7800.0
Reddy = 125000.0
Ccoil = 7e-11
```

[[voices.01_modern_jazz_active.pickups]]
name = "Modern Jazz Single-Coil (Neck)"
type = "single_coil"
magnet_type = "alnico_v"
fr = 5200.0
Q = 1.7
weight = 0.5
coils = [
    { strings = ["all"], position_from_bridge_m = 0.1556, aperture_width_in = 0.75, weight = 1.0 }
]

[[voices.01_modern_jazz_active.pickups]]
name = "Modern Jazz Single-Coil (Bridge)"
type = "single_coil"
magnet_type = "alnico_v"
fr = 4500.0
Q = 1.6
weight = 0.5
coils = [
    { strings = ["all"], position_from_bridge_m = 0.0635, aperture_width_in = 0.75, weight = 1.0 }
]
```

#### 2. Vintage 1960s Jazz Bass Pair (`02_jazz_bass_pair`)
```toml
# config/voices/02_jazz_bass_pair.toml
name = "02. Vintage 60s Jazz Bass Pair (Parallel)"
topology = "Dual Single-Coil Parallel"
blend_mode = "parallel"
magnet_type = "alnico_v"
alpha = 0.26
fr = 2700.0
Q = 1.4
gain_db = -0.5
scale = "34in"
coils = [
    { strings = ["all"], position_from_bridge_m = 0.1556, aperture_width_in = 0.75, weight = 0.5 },
    { strings = ["all"], position_from_bridge_m = 0.0635, aperture_width_in = 0.75, weight = 0.5 }
]

[circuit]
topology = "parallel"
Rvol = 125000.0
Rtone = 250000.0
Ctone = 47e-9

[circuit.neck]
L = 3.2
Rdc = 7200.0
Reddy = 135000.0
Ccoil = 7e-11

[circuit.bridge]
L = 3.6
Rdc = 7800.0
Reddy = 125000.0
Ccoil = 7e-11

[[voices.02_jazz_bass_pair.pickups]]
name = "Vintage 60s Jazz Single-Coil (Neck)"
type = "single_coil"
fr = 3100.0
Q = 1.5
weight = 0.5
coils = [
    { strings = ["all"], position_from_bridge_m = 0.1556, aperture_width_in = 0.75, weight = 1.0 }
]

[[voices.02_jazz_bass_pair.pickups]]
name = "Vintage 60s Jazz Single-Coil (Bridge)"
type = "single_coil"
fr = 2800.0
Q = 1.4
weight = 0.5
coils = [
    { strings = ["all"], position_from_bridge_m = 0.0635, aperture_width_in = 0.75, weight = 1.0 }
]
```

---

## 5. Physical String Catalog Reference (`config/strings.toml`)

`config/strings.toml` defines the mechanical, viscoelastic, and acoustic properties of physical string sets. These parameters govern high-frequency mechanical damping, inharmonicity/tension class, dynamic bridge compliance, and low-frequency body bloom:

| Field | Type | Units | Description |
| :--- | :--- | :--- | :--- |
| `name` | `string` | — | Full human-readable display label (e.g. `"La Bella Low Tension Flats LTF-4A"`). |
| `type` | `string` | — | Construction classification: `"roundwound"`, `"flatwound"`, `"double_bass"`. |
| `wrap` | `string` | — | Outer wrap alloy: `"nickel"`, `"stainless"`, `"stainless_flat"`, `"chrome_steel"`. |
| `core` | `string` | — | Core wire geometry: `"hex"`, `"round"`, `"spiral_rope"`. |
| `tension_lbs` | `float` | lbs | Total 4-string set tension at pitch. |
| `damping_cutoff_hz` | `float` | Hz | Viscoelastic high-frequency mechanical roll-off corner frequency ($f_d$). |
| `damping_order` | `float` | — | High-frequency damping filter order ($n$). |
| `bloom_db` | `float` | dB | Resonant acoustic low-end cavity and body bloom ($60\text{--}100\text{ Hz}$). |
| `pluck_excursion_factor` | `float`| Ratio | Physical plucking excursion multiplier relative to standard roundwound baseline ($1.0$). Lower tension strings exhibit higher excursion ($1.25\times$). |
| `k_long` | `float` | — | Longitudinal core wire percussive clank coupling factor ($0.00\text{ to }0.35$). |

### Built-In String Presets:

1. **`roundwound_nickel_standard` (Global Default Baseline):**
   * Standard D'Addario EXL / Ernie Ball Slinky $.045\text{--}.105$.
   * $155.0\text{ lbs}$ tension, $f_d = 8500\text{ Hz}, n = 1.0, \text{bloom} = 0.0\text{ dB}, k_{\text{long}} = 0.20$.
2. **`roundwound_nickel_6string` (Extended 6-String Baseline):**
   * Universal 6-string D'Addario EXL170-6 / Ernie Ball Slinky $.032\text{--}.130$.
   * $230.0\text{ lbs}$ tension, $f_d = 8500\text{ Hz}, n = 1.0, \text{bloom} = 0.0\text{ dB}, k_{\text{long}} = 0.20$.
3. **`roundwound_stainless_clank` (Multi-Scale / Dingwall):**
   * Dingwall Custom $.045\text{--}.130$ high-tension stainless steel.
   * $180.0\text{ lbs}$ tension, $f_d = 12000\text{ Hz}, n = 1.0, \text{bloom} = -1.0\text{ dB}, k_{\text{long}} = 0.35$ (massive metallic clank).
4. **`flatwound_low_tension` (Smooth Fretless Thump):**
   * La Bella Low Tension Flats LTF-4A $.043\text{--}.100$ round core.
   * $132.0\text{ lbs}$ low tension, $f_d = 2800\text{ Hz}, n = 1.8, \text{bloom} = +1.8\text{ dB}$, excursion factor $1.25\times$.
5. **`flatwound_vintage_heavy` (Motown / Jamerson 1954 Spec):**
   * La Bella 760M $.052\text{--}.110$ heavy hex core.
   * $195.0\text{ lbs}$ heavy tension, $f_d = 1800\text{ Hz}, n = 2.0, \text{bloom} = +2.4\text{ dB}, k_{\text{long}} = 0.05$.
6. **`double_bass_spirocore` (3/4 Upright Orchestral/Pizz):**
   * Thomastik-Infeld Spirocore / D'Addario Helicore Pizzicato $41.5''$ spiral rope core.
   * $265.0\text{ lbs}$ massive tension, $f_d = 3800\text{ Hz}, n = 2.0, \text{bloom} = +2.8\text{ dB}$, bridge rocking compliance $0.42\text{V}$.

---

## 6. How to Add a Custom Instrument

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
   pole_type = "blade"
   magnet_type = "ceramic"
   resonant_frequency_hz = 2800.0
   q_factor = 1.35
   coils = [
       { strings = ["all"], position_from_bridge_m = 0.0645, aperture_width_in = 0.60, weight = 0.5, pole_type = "blade" },
       { strings = ["all"], position_from_bridge_m = 0.0455, aperture_width_in = 0.60, weight = 0.5, pole_type = "blade" }
   ]
   ```
4. Run validation and preview:
   ```bash
   uv run python main.py --stage viz --instrument my_custom_5str
   ```
