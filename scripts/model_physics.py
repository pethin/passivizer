"""
Passivizer - Physical & Acoustic Modeling Engine
Computes magnetic aperture sinc windows, dual-coil humbucker comb filtering,
scale-length wave-speed conversions, and string tension filters using NumPy.
Synthesizes minimum-phase causal FIR filters for NAM audio pre-filtering.
"""

import cmath
import math
import os
import tomllib
import wave
from pathlib import Path
import numpy as np

FS = 48000
NUM_TAPS = 4096
NYQ = FS / 2.0
FREQS = [i * (NYQ / (NUM_TAPS - 1)) for i in range(NUM_TAPS)]

def _fft(x):
    """NumPy-backed 1D forward FFT preserving backwards-compatible list-of-complex interface."""
    return list(np.fft.fft(np.asarray(x, dtype=complex)))

def _ifft(x):
    """NumPy-backed 1D inverse FFT preserving backwards-compatible list-of-complex interface."""
    return list(np.fft.ifft(np.asarray(x, dtype=complex)))

def synthesize_minimum_phase_fir(magnitude_curve, num_taps=NUM_TAPS, normalize=True):
    """
    Synthesizes a causal, minimum-phase FIR filter from a desired magnitude
    curve using the homomorphic real-cepstrum Hilbert transform.
    Vectorized with NumPy FFT, executing in < 0.1 ms.
    """
    mag = np.asarray(magnitude_curve, dtype=np.float64)
    n_fft = max(8192, 2 * num_taps)
    half = n_fft // 2

    # Linear interpolation of input magnitude curve to half + 1 points
    m_in = len(mag)
    orig_indices = np.linspace(0, half, m_in)
    target_indices = np.arange(half + 1)
    mag_grid = np.interp(target_indices, orig_indices, mag)
    # Extrapolate DC bin if dropping into deep transmission zero to avoid cepstral delta spike
    if mag_grid[0] < mag_grid[1] * 0.5:
        mag_grid[0] = mag_grid[1]
    mag_grid = np.maximum(mag_grid, 1e-4)

    # Build full symmetric log-magnitude spectrum
    log_mag = np.log(mag_grid)
    full_log_mag = np.concatenate([log_mag, log_mag[half - 1 : 0 : -1]])

    # Real cepstrum via IFFT
    c = np.fft.ifft(full_log_mag).real

    # Minimum-phase causal folding (Hilbert transform operator in cepstral domain)
    c_hat = np.zeros(n_fft, dtype=np.float64)
    c_hat[0] = c[0]
    c_hat[half] = c[half]
    c_hat[1:half] = 2.0 * c[1:half]

    # Complex minimum-phase frequency spectrum H_min = exp(FFT(c_hat))
    spec = np.fft.fft(c_hat)
    h_min_spec = np.exp(spec)

    # Causal impulse response h[n] = Re(IFFT(H_min))
    h = np.fft.ifft(h_min_spec).real
    fir = h[:num_taps].copy()

    # Smooth tail (final 15%) with a cosine taper to eliminate truncation artifacts
    taper_len = int(num_taps * 0.15)
    start_taper = num_taps - taper_len
    w = 0.5 * (1.0 + np.cos(np.pi * np.arange(taper_len) / taper_len))
    fir[start_taper:] *= w

    if not normalize:
        return fir.tolist()

    # Peak normalization to -0.1 dBFS (0.99)
    max_peak = np.max(np.abs(fir))
    if max_peak > 0:
        fir = (fir / max_peak) * 0.99
    return fir.tolist()

def write_wav_24bit(filepath, samples, sample_rate=FS):
    """Exports a 48 kHz / 24-bit mono PCM WAV file."""
    try:
        from pedalboard.io import AudioFile
        import numpy as np
        arr = np.array([samples], dtype=np.float32)
        with AudioFile(filepath, "w", samplerate=sample_rate, num_channels=1, bit_depth=24) as f:
            f.write(arr)
    except (ImportError, Exception):
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(3)  # 3 bytes = 24-bit PCM
            wf.setframerate(sample_rate)
            scaled = np.clip(np.asarray(samples, dtype=np.float32) * 8388607.0, -8388608.0, 8388607.0).astype(np.int32)
            raw_bytes = scaled.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
            wf.writeframes(raw_bytes)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
INSTRUMENTS_DIR = CONFIG_DIR / "instruments"
SCALES_FILE = CONFIG_DIR / "scales.toml"
VOICES_FILE = CONFIG_DIR / "voices.toml"

def load_scales(config_path=None):
    """Loads scale lengths and wave speeds from TOML."""
    path = Path(config_path) if config_path else SCALES_FILE
    with open(path, "rb") as f:
        data = tomllib.load(f)
    scales = {}
    for sid, scfg in data.get("scales", {}).items():
        scales[sid] = {
            "name": scfg.get("name", sid),
            "scale_m": scfg.get("scale_length_m", scfg.get("scale_length_in", 34.0) * 0.0254),
            "scale_length_in": scfg.get("scale_length_in", 34.0),
            "speeds": scfg.get("string_wave_speeds", [])
        }
    return scales

def load_instrument(identifier_or_path):
    """
    Loads an instrument configuration from a file path, known ID, or shorthand alias.
    Aliases: '30in' -> '30in_emg_mm', '32in' -> '32in_custom_pmm', '34in' -> '34in_standard_p'.
    """
    if isinstance(identifier_or_path, dict):
        return identifier_or_path

    aliases = {
        "30in": "30in_emg_mmtw",
        "30in_mm": "30in_emg_mmtw",
        "30in_mmtw": "30in_emg_mmtw",
        "30in_emg_mm": "30in_emg_mmtw",
        "30in_emg_mmtw": "30in_emg_mmtw",
        "32in": "32in_custom_pmm",
        "32in_fretless": "32in_fretless_pmm",
        "fretless": "32in_fretless_pmm",
        "34in": "34in_standard_p",
        "standard_p": "34in_standard_p",
        "34in_standard_jazz": "34in_standard_jazz",
        "standard_jazz": "34in_standard_jazz",
        "34in_standard_pj": "34in_standard_pj",
        "standard_pj": "34in_standard_pj",
        "34in_pj": "34in_standard_pj",
        "pj": "34in_standard_pj",
        "34in_active_stingray": "34in_active_stingray",
        "active_stingray": "34in_active_stingray",
        "stingray": "34in_active_stingray",
        "ray": "34in_active_stingray",
        "34in_active_soapbar": "34in_active_soapbar",
        "active_soapbar": "34in_active_soapbar",
        "soapbar": "34in_active_soapbar",
        "30in_mustang_pj": "30in_mustang_pj",
        "mustang_pj": "30in_mustang_pj",
        "30in_mustang": "30in_mustang_pj",
        "mustang": "30in_mustang_pj",
        "30in_standard_mustang": "30in_mustang_pj",
        "standard_mustang": "30in_mustang_pj",
        "37in_multiscale_dingwall": "37in_multiscale_dingwall",
        "multiscale_dingwall": "37in_multiscale_dingwall",
        "dingwall": "37in_multiscale_dingwall",
        "combustion": "37in_multiscale_dingwall",
        "34in_dingwall_sp1": "34in_dingwall_sp1",
        "dingwall_sp1": "34in_dingwall_sp1",
        "sp1": "34in_dingwall_sp1"
    }
    raw = str(identifier_or_path).strip()
    key = aliases.get(raw, raw)

    path = Path(key)
    if not path.exists():
        if (INSTRUMENTS_DIR / f"{key}.toml").exists():
            path = INSTRUMENTS_DIR / f"{key}.toml"
        elif (INSTRUMENTS_DIR / key).exists():
            path = INSTRUMENTS_DIR / key
        else:
            raise FileNotFoundError(f"Instrument configuration not found: '{identifier_or_path}' (searched in {INSTRUMENTS_DIR})")

    with open(path, "rb") as f:
        return tomllib.load(f)

def load_all_instruments(instruments_dir=None):
    """Loads all instrument definitions found in instruments_dir."""
    idir = Path(instruments_dir) if instruments_dir else INSTRUMENTS_DIR
    instruments = {}
    if idir.exists():
        for p in sorted(idir.glob("*.toml")):
            with open(p, "rb") as f:
                cfg = tomllib.load(f)
                inst_id = cfg.get("id", p.stem)
                instruments[inst_id] = cfg
    return instruments

def load_voices_config(voices_path=None):
    """Loads all target voices and their acoustic parameters from TOML."""
    path = Path(voices_path) if voices_path else VOICES_FILE
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("voices", {})

def get_source_pickup(instrument, voice_id):
    """
    Determines which pickup on the source instrument should be used for the target voice.
    Checks explicit pickup_mapping, falls back to default_pickup, or selects first pickup.
    """
    pickups = instrument.get("pickups", {})
    if not pickups:
        raise ValueError(f"Instrument '{instrument.get('id', 'unknown')}' has no pickups defined.")

    # 1. Explicit voice mapping
    mapping = instrument.get("pickup_mapping", {})
    if voice_id in mapping and mapping[voice_id] in pickups:
        p = pickups[mapping[voice_id]].copy()
        p["id"] = mapping[voice_id]
        return p

    # 2. Default pickup declared on instrument
    default_key = instrument.get("default_pickup")
    if default_key and default_key in pickups:
        p = pickups[default_key].copy()
        p["id"] = default_key
        return p

    # 3. Fallback to first available pickup
    first_key = next(iter(pickups.keys()))
    p = pickups[first_key].copy()
    p["id"] = first_key
    return p

STRINGS_FILE = CONFIG_DIR / "strings.toml"

def load_strings_config(config_path=None):
    """Loads physical string catalog from TOML."""
    path = Path(config_path) if config_path else STRINGS_FILE
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("strings", {})

def get_instrument_string(instrument):
    """Resolves string configuration dictionary for a source instrument."""
    inst = load_instrument(instrument) if not isinstance(instrument, dict) else instrument
    s_block = inst.get("strings", {})
    preset = s_block.get("preset", "roundwound_nickel_standard")
    base = STRINGS.get(preset, STRINGS.get("roundwound_nickel_standard", {})).copy()
    base.update(s_block)
    return base

def get_voice_string(voice_cfg):
    """Resolves target string configuration dictionary for a target voice."""
    preset = voice_cfg.get("target_string", "roundwound_nickel_standard")
    return STRINGS.get(preset, STRINGS.get("roundwound_nickel_standard", {})).copy()

def compute_differential_string_transfer(freqs, src_string, tgt_string):
    """
    Computes differential transfer function between source instrument strings
    and target voicing goal strings using NumPy:
      H_string_transfer(f) = H_damp_ratio(f) * H_bloom_diff(f)
    Prevents double-damping when source bass already uses flatwounds, while
    providing authentic acoustic upright/fanned-fret damping and bloom.
    """
    f = np.asarray(freqs, dtype=np.float64)

    f_damp_src = float(src_string.get("damping_cutoff_hz", 8500.0))
    n_src = float(src_string.get("damping_order", 1.0))

    f_damp_tgt = float(tgt_string.get("damping_cutoff_hz", 8500.0))
    n_tgt = float(tgt_string.get("damping_order", 1.0))

    # Calculate magnitude damping curves
    src_mag = 1.0 / np.sqrt(1.0 + (f / f_damp_src) ** (2.0 * n_src))
    tgt_mag = 1.0 / np.sqrt(1.0 + (f / f_damp_tgt) ** (2.0 * n_tgt))

    ratio = tgt_mag / np.maximum(src_mag, 1e-6)
    r_db = 20.0 * np.log10(np.maximum(ratio, 1e-6))
    g_max_db = 8.0
    g_min_db = -36.0
    r_soft_db = np.where(
        r_db > 0.0,
        g_max_db * np.tanh(r_db / g_max_db),
        g_min_db * np.tanh(r_db / g_min_db),
    )
    h_damp_ratio = 10.0 ** (r_soft_db / 20.0)

    bloom_src = float(src_string.get("bloom_db", 0.0))
    bloom_tgt = float(tgt_string.get("bloom_db", 0.0))
    delta_bloom_db = bloom_tgt - bloom_src

    g_bloom = 10.0 ** (delta_bloom_db / 20.0)
    h_bloom = np.sqrt((g_bloom ** 2 + (f / 90.0) ** 2) / (1.0 + (f / 90.0) ** 2))

    return h_damp_ratio * h_bloom

# Global registries initialized from modular configuration files
SCALES = load_scales()
VOICES = load_voices_config()
INSTRUMENTS = load_all_instruments()
STRINGS = load_strings_config()

def resolve_voices(voice_arg):
    """
    Parses a voice argument into a list of valid target voice IDs.
    Supports:
      - 'all' -> all configured voices in VOICES
      - Comma-separated list: '01_jazz_bass_pair,03_modern_p_ceramic'
      - Single voice ID: '03_modern_p_ceramic'
      - Partial / prefix matching: '01', '03'
    """
    if not voice_arg or str(voice_arg).strip().lower() == "all":
        return list(VOICES.keys())

    tokens = [v.strip() for v in str(voice_arg).split(",") if v.strip()]
    resolved = []
    for token in tokens:
        if token in VOICES:
            if token not in resolved:
                resolved.append(token)
        else:
            matches = [vid for vid in VOICES if vid.startswith(token) or token in vid]
            if matches:
                for m in matches:
                    if m not in resolved:
                        resolved.append(m)
            else:
                print(f"Warning: Unknown voice identifier '{token}'.")
    return resolved if resolved else list(VOICES.keys())

def resolve_pickup_coils(pickup_dict, instrument=None):
    """
    Resolves an instrument pickup configuration into a canonical list of coil dicts.
    Handles:
      - Composite pickups ('components' referencing other pickups with weights)
      - Explicit coil arrays ('coils' with per-string bindings)
      - Dual-coil humbuckers with coil spacing 'd'
      - Single-coil / split-coil fallbacks
    Each returned coil has:
      - position_from_bridge_m: float
      - aperture_width_in: float
      - weight: float
      - polarity: float
      - strings: list of str (e.g. ['E', 'A'], ['D', 'G'], or ['all'])
    """
    # 1. Composite blend / sum
    if pickup_dict.get("type") == "composite" or "components" in pickup_dict:
        resolved = []
        components = pickup_dict.get("components", [])
        pickups_map = instrument.get("pickups", {}) if instrument else {}
        for comp in components:
            p_ref = comp.get("pickup")
            c_weight = comp.get("weight", 1.0)
            c_pol = comp.get("polarity", 1.0)
            if p_ref in pickups_map:
                sub_coils = resolve_pickup_coils(pickups_map[p_ref], instrument)
                for sc in sub_coils:
                    sc_copy = sc.copy()
                    sc_copy["weight"] = sc.get("weight", 1.0) * c_weight
                    sc_copy["polarity"] = sc.get("polarity", 1.0) * c_pol
                    resolved.append(sc_copy)
            elif "position_from_bridge_m" in comp:
                resolved.append({
                    "position_from_bridge_m": comp["position_from_bridge_m"],
                    "aperture_width_in": comp.get("aperture_width_in", 0.75),
                    "weight": c_weight,
                    "polarity": c_pol,
                    "strings": comp.get("strings", ["all"])
                })
        if resolved:
            return resolved

    # 2. Explicit coils list
    if "coils" in pickup_dict and pickup_dict["coils"]:
        coils = []
        for c in pickup_dict["coils"]:
            coils.append({
                "position_from_bridge_m": c["position_from_bridge_m"],
                "aperture_width_in": c.get("aperture_width_in", pickup_dict.get("aperture_width_in", 0.75)),
                "weight": c.get("weight", 1.0),
                "polarity": c.get("polarity", 1.0),
                "strings": c.get("strings", ["all"])
            })
        return coils

    # 3. Dual-coil humbucker via coil_spacing_in
    pos_m = pickup_dict.get("position_from_bridge_m", 0.08)
    w_in = pickup_dict.get("aperture_width_in", 0.75)
    d_in = pickup_dict.get("coil_spacing_in", 0.0)
    d_m = d_in * 0.0254
    if d_in > 0:
        return [
            {
                "position_from_bridge_m": pos_m - d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"]
            },
            {
                "position_from_bridge_m": pos_m + d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"]
            }
        ]

    # 4. Standard single coil
    return [
        {
            "position_from_bridge_m": pos_m,
            "aperture_width_in": w_in,
            "weight": 1.0,
            "polarity": 1.0,
            "strings": ["all"]
        }
    ]

def resolve_voice_pickups(voice_cfg):
    """
    Resolves a target voice configuration into a canonical list of pickup dicts.
    Handles:
      - Multi-pickup voices with explicit 'pickups = [...]' array
      - Single-pickup voices with top-level 'fr', 'Q', 'coils'
      - Legacy voices with 'pos_34', 'w', 'd'
    Returns a list of dicts:
      [
        {
          "name": str,
          "type": str,
          "fr": float,
          "Q": float,
          "weight": float,
          "polarity": float,
          "coils": list[dict]
        },
        ...
      ]
    """
    if "pickups" in voice_cfg and voice_cfg["pickups"]:
        resolved = []
        for p in voice_cfg["pickups"]:
            p_coils = []
            for c in p.get("coils", []):
                p_coils.append({
                    "position_from_bridge_m": float(c["position_from_bridge_m"]),
                    "aperture_width_in": float(c.get("aperture_width_in", 0.75)),
                    "weight": float(c.get("weight", 1.0)),
                    "polarity": float(c.get("polarity", 1.0)),
                    "strings": list(c.get("strings", ["all"])),
                })
            resolved.append({
                "name": str(p.get("name", "Pickup")),
                "type": str(p.get("type", "single_coil")),
                "fr": float(p.get("fr", voice_cfg.get("fr", 3000.0))),
                "Q": float(p.get("Q", voice_cfg.get("Q", 1.5))),
                "weight": float(p.get("weight", 1.0)),
                "polarity": float(p.get("polarity", 1.0)),
                "coils": p_coils,
            })
        if resolved:
            return resolved

    # Fallback for single-pickup voices: wrap top-level voice coils/fr/Q
    return [
        {
            "name": str(voice_cfg.get("name", "Target Pickup")),
            "type": str(voice_cfg.get("topology", "single")),
            "fr": float(voice_cfg.get("fr", 3000.0)),
            "Q": float(voice_cfg.get("Q", 1.5)),
            "weight": 1.0,
            "polarity": 1.0,
            "coils": resolve_voice_coils(voice_cfg, _from_pickups=False),
        }
    ]

def resolve_voice_coils(voice_cfg, _from_pickups=True):
    """Resolves target voice configuration into a canonical list of coil dicts."""
    if _from_pickups and "pickups" in voice_cfg and voice_cfg["pickups"]:
        all_coils = []
        for p in voice_cfg["pickups"]:
            p_weight = float(p.get("weight", 1.0))
            p_pol = float(p.get("polarity", 1.0))
            for c in p.get("coils", []):
                all_coils.append({
                    "position_from_bridge_m": float(c["position_from_bridge_m"]),
                    "aperture_width_in": float(c.get("aperture_width_in", 0.75)),
                    "weight": float(c.get("weight", 1.0)) * p_weight,
                    "polarity": float(c.get("polarity", 1.0)) * p_pol,
                    "strings": list(c.get("strings", ["all"])),
                })
        if all_coils:
            return all_coils

    if "coils" in voice_cfg:
        normalized = []
        for c in voice_cfg["coils"]:
            normalized.append({
                "position_from_bridge_m": float(c["position_from_bridge_m"]),
                "aperture_width_in": float(c.get("aperture_width_in", 0.75)),
                "weight": float(c.get("weight", 1.0)),
                "polarity": float(c.get("polarity", 1.0)),
                "strings": list(c.get("strings", ["all"])),
            })
        return normalized
    pos_m = float(voice_cfg.get("pos_34", 0.088))
    w_in = float(voice_cfg.get("w", 0.75))
    d_in = float(voice_cfg.get("d", 0.0))
    d_m = d_in * 0.0254
    if d_in > 0:
        return [
            {
                "position_from_bridge_m": pos_m - d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"]
            },
            {
                "position_from_bridge_m": pos_m + d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"]
            }
        ]
    return [
        {
            "position_from_bridge_m": pos_m,
            "aperture_width_in": w_in,
            "weight": 1.0,
            "polarity": 1.0,
            "strings": ["all"]
        }
    ]

def compute_effective_position(coils):
    """Computes weighted average physical position from bridge in meters."""
    if not coils:
        return 0.08
    total_w = sum(c.get("weight", 1.0) for c in coils)
    if total_w == 0:
        return coils[0]["position_from_bridge_m"]
    return sum(c["position_from_bridge_m"] * c.get("weight", 1.0) for c in coils) / total_w

def is_voice_matching_source(instrument, voice_id, voice_cfg=None):
    """
    Determines if a target voice matches the source instrument's physical scale and pickup geometry,
    meaning zero spatial or acoustic transfer is required (identity transformation).
    Tuning- and string-count-agnostic: matches on physical scale length and coil geometry.
    """
    inst = load_instrument(instrument) if not isinstance(instrument, dict) else instrument
    vcfg = voice_cfg or VOICES.get(voice_id, {})

    src_scale_m = inst.get("scale_length_m", inst.get("scale_length_in", 34.0) * 0.0254)
    tgt_scale = vcfg.get("scale", "34in")
    tgt_scale_info = SCALES.get(tgt_scale, {})
    tgt_scale_m = tgt_scale_info.get("scale_m", tgt_scale_info.get("scale_length_m", 0.8636))

    # Scale match based on physical vibrating length (within 1.2 cm)
    if abs(src_scale_m - tgt_scale_m) > 0.012:
        return False

    src_p = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_p, inst)
    tgt_coils = resolve_voice_coils(vcfg)

    if len(src_coils) != len(tgt_coils):
        return False

    s_sort = sorted(src_coils, key=lambda c: c["position_from_bridge_m"])
    t_sort = sorted(tgt_coils, key=lambda c: c["position_from_bridge_m"])

    for sc, tc in zip(s_sort, t_sort):
        if abs(sc["position_from_bridge_m"] - tc["position_from_bridge_m"]) > 0.005:
            return False
        if abs(sc.get("aperture_width_in", 0.75) - tc.get("aperture_width_in", 0.75)) > 0.15:
            return False

    return True

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

STRING_FUNDAMENTALS = {
    "B": 30.868,
    "E": 41.203,
    "A": 55.000,
    "D": 73.416,
    "G": 97.999,
    "C": 130.813,
}

INHARMONICITY_ANCHORS_F0 = np.array([27.50, 30.87, 41.20, 55.00, 73.42, 98.00, 130.81, 196.00], dtype=np.float64)
INHARMONICITY_ANCHORS_BS = np.array([0.000028, 0.000025, 0.000020, 0.000012, 0.000006, 0.000003, 0.0000015, 0.0000008], dtype=np.float64)
MEAN_BASS_F0 = 66.9045  # Mean open-string fundamental frequency (E1=41.203, A1=55.000, D2=73.416, G2=97.999)

def pitch_to_note_name(f0: float) -> str:
    """Converts fundamental frequency f0 to equal-temperament note name (A4 = 440 Hz)."""
    if f0 <= 0:
        return "C"
    midi_num = 69.0 + 12.0 * math.log2(f0 / 440.0)
    note_idx = int(round(midi_num)) % 12
    return NOTE_NAMES[note_idx]

def get_inharmonicity_for_f0(f0: float) -> float:
    """
    Returns the physical string stiffness / inharmonicity parameter B_s
    interpolated smoothly in log-frequency space.
    """
    log_f0 = np.log2(np.clip(f0, 20.0, 300.0))
    log_anchors = np.log2(INHARMONICITY_ANCHORS_F0)
    b_s = float(np.interp(log_f0, log_anchors, INHARMONICITY_ANCHORS_BS))
    return b_s

def generate_wave_speed_continuum(scale_length_m: float = 0.8636, num_points: int = 24):
    """
    Generates a dense, continuous log-spaced continuum of wave speeds spanning
    the full operating register of an electric bass for a given scale length:
    v(f0) = 2 * L * f0
    From f_min = 27.5 Hz (Low A / Low B, covering Drop A, Drop C, Drop D, Standard E)
    to f_max = 105.0 Hz (covering open strings up through G on 4- and 5-string basses).

    Returns a list of dicts:
      [
        {
          "f0": float,
          "v0": float,
          "register": "lower" if i < num_points // 2 else "upper",
          "weight": float,
        },
        ...
      ]
    Ensures complete invariance to tunings, string counts (4/5/6-string), and string gauges.
    """
    f_min = 30.87
    f_max = 100.00
    log_f = np.linspace(np.log2(f_min), np.log2(f_max), num_points)
    f0_arr = 2.0 ** log_f
    v0_arr = 2.0 * float(scale_length_m) * f0_arr

    continuum = []
    half = num_points // 2
    for i, (f0, v0) in enumerate(zip(f0_arr, v0_arr)):
        reg = "lower" if i < half else "upper"
        continuum.append({
            "f0": float(f0),
            "v0": float(v0),
            "register": reg,
            "weight": 1.0 / num_points,
        })
    return continuum

def resolve_scale_length(string_speeds, scale_length_m=None):
    """Resolves the effective vibrating scale length in meters."""
    if scale_length_m is not None and scale_length_m > 0:
        return scale_length_m
    for s_info in SCALES.values():
        speeds = s_info.get("speeds", [])
        if len(speeds) == len(string_speeds) and np.allclose(speeds, string_speeds, rtol=0.005):
            return s_info.get("scale_m", s_info.get("scale_length_m", 0.8636))
    if len(string_speeds) == 5:
        if np.allclose(string_speeds[:4], SCALES.get("30in", {}).get("speeds", []), rtol=0.005):
            return 0.762
        if np.allclose(string_speeds[:4], SCALES.get("32in", {}).get("speeds", []), rtol=0.005):
            return 0.8128
    return 0.8636

def infer_string_names(string_speeds, scale_length_m: float = None):
    """Infers note names for each string in string_speeds based on physical tuning physics."""
    n = len(string_speeds)
    if scale_length_m is not None and scale_length_m > 0:
        l_eff = scale_length_m
    else:
        if n == 4:
            for s_key in ["30in", "32in", "34in", "multiscale", "upright"]:
                if np.allclose(string_speeds, SCALES.get(s_key, {}).get("speeds", []), rtol=0.005):
                    return ["E", "A", "D", "G"]
        elif n == 5:
            if np.allclose(string_speeds, [53.28, 71.16, 95.0, 126.81, 169.27], rtol=0.005):
                return ["B", "E", "A", "D", "G"]
            if np.allclose(string_speeds, [58.02, 75.88, 99.19, 129.60, 169.27], rtol=0.005):
                return ["B", "E", "A", "D", "G"]
            if np.allclose(string_speeds, SCALES.get("multiscale_super", {}).get("speeds", []), rtol=0.005):
                return ["B", "E", "A", "D", "G"]
            if np.allclose(string_speeds, [71.16, 95.0, 126.81, 169.27, 225.69], rtol=0.005):
                return ["E", "A", "D", "G", "C"]
            if np.allclose(string_speeds, [62.79, 83.82, 111.89, 149.35, 199.36], rtol=0.005):
                return ["E", "A", "D", "G", "C"]
        elif n == 6:
            if np.allclose(string_speeds, [53.28, 71.16, 95.0, 126.81, 169.27, 225.69], rtol=0.005):
                return ["B", "E", "A", "D", "G", "C"]

        l_eff = resolve_scale_length(string_speeds, scale_length_m)

    names = []
    for v in string_speeds:
        f0 = v / (2.0 * l_eff)
        names.append(pitch_to_note_name(f0))
    return names

def get_coil_register(coil) -> str:
    """
    Identifies whether a coil half is 'lower' (bass strings register),
    'upper' (treble strings register), or 'all' across the string bed.
    """
    reg = coil.get("register")
    if reg in ["lower", "bass", "low"]:
        return "lower"
    if reg in ["upper", "treble", "high"]:
        return "upper"
    if reg == "all":
        return "all"

    strings = coil.get("strings", ["all"])
    if "all" in strings:
        return "all"

    strings_set = set(strings)
    # Standard musical string numbering:
    # 1 = highest pitch (G on 4-string, C on 6-string), 2 = D -> upper / treble register
    # 3 = A, 4 = E, 5 = Low B, 6 = Low F# -> lower / bass register
    lower_markers = {"E", "A", "B", "low", "lower", "bass", 3, 4, 5, 6, "3", "4", "5", "6"}
    upper_markers = {"D", "G", "C", "high", "upper", "treble", 1, 2, "1", "2"}

    has_lower = bool(strings_set & lower_markers)
    has_upper = bool(strings_set & upper_markers)

    if has_lower and not has_upper:
        return "lower"
    elif has_upper and not has_lower:
        return "upper"
    return "all"

def compute_dispersive_wave_speed(freqs, v0: float, string_name: str = None, f0: float = None, scale_length_m: float = None) -> np.ndarray:
    """
    Computes frequency-dependent transverse wave speed v(f) accounting for flexural bending stiffness:
    v(f) = v0 * sqrt(1 + B_s * (f / f0)^2 / (1 + (f / 3500)^2))
    Captures authentic physical string inharmonicity and overtone dispersion on thick bass strings,
    preventing artificial sterile harmonic alignment in multi-pickup phase summing.
    Tuning- and gauge-agnostic: derives fundamental frequency f0 = v0 / (2 * L) and inharmonicity B_s(f0) directly.
    """
    f = np.asarray(freqs, dtype=np.float64)
    if f0 is None or f0 <= 0:
        if string_name in STRING_FUNDAMENTALS and scale_length_m is None:
            f0_std = STRING_FUNDAMENTALS[string_name]
            l_check = 0.8636
            if abs((v0 / (2.0 * l_check)) - f0_std) / f0_std < 0.15:
                f0 = f0_std
        if f0 is None:
            l_eff = scale_length_m if (scale_length_m is not None and scale_length_m > 0) else 0.8636
            f0 = max(v0 / (2.0 * l_eff), 15.0)

    b_s = get_inharmonicity_for_f0(f0)
    f_disp_max = 3500.0
    disp_factor = 1.0 + b_s * ((f / f0) ** 2) / (1.0 + (f / f_disp_max) ** 2)
    return v0 * np.sqrt(disp_factor)

def numpy_pickup_acoustic_response(freqs, coils, scale_length_m: float = None, string_speeds=None, string_names=None):
    """
    Computes compound spatial aperture and multi-coil response for an arbitrary
    array of N physical coils across the continuous wave-speed continuum of the instrument.
    Completely tuning-agnostic, gauge-agnostic, and string-count-agnostic.
    Respects geometric register half bindings for split-coil pickups (e.g. P-Bass).
    """
    f = np.asarray(freqs, dtype=np.float64)

    # Handle argument flexibility if callers pass (freqs, coils, string_speeds)
    if isinstance(scale_length_m, (list, tuple, np.ndarray)):
        string_speeds = scale_length_m
        scale_length_m = 0.8636

    l_eff = float(scale_length_m) if (scale_length_m is not None and not isinstance(scale_length_m, (list, tuple, np.ndarray)) and scale_length_m > 0) else 0.8636

    if string_speeds is not None and len(string_speeds) > 0 and len(string_speeds) != 24:
        continuum = []
        n_str = len(string_speeds)
        half = n_str // 2 if n_str > 2 else 1
        for s_idx, v in enumerate(string_speeds):
            f0 = max(v / (2.0 * l_eff), 15.0)
            if string_names and s_idx < len(string_names):
                s_name = string_names[s_idx]
                if s_name in [1, 2, "1", "2", "D", "G", "C", "high", "upper", "treble"]:
                    reg = "upper"
                elif s_name in [3, 4, 5, 6, "3", "4", "5", "6", "E", "A", "B", "low", "lower", "bass"]:
                    reg = "lower"
                else:
                    reg = "lower" if s_idx < half else "upper"
            else:
                reg = "lower" if s_idx < half else "upper"
            continuum.append({"f0": f0, "v0": float(v), "register": reg, "weight": 1.0 / n_str})
    else:
        continuum = generate_wave_speed_continuum(l_eff, num_points=24)

    acc = np.zeros_like(f, dtype=np.float64)
    total_pt_weight = 0.0

    for pt in continuum:
        f0 = pt["f0"]
        v = pt["v0"]
        pt_reg = pt["register"]
        pt_weight = pt.get("weight", 1.0)

        v_disp = compute_dispersive_wave_speed(f, v, f0=f0, scale_length_m=l_eff)

        # Select coils that match this continuum point's register
        active = []
        for c in coils:
            coil_reg = get_coil_register(c)
            if coil_reg == "all" or coil_reg == pt_reg:
                active.append(c)

        if not active:
            active = coils

        total_w = sum(abs(c.get("weight", 1.0)) for c in active) or 1.0
        center_pos = sum(c["position_from_bridge_m"] * abs(c.get("weight", 1.0)) for c in active) / total_w

        # Complex phasor sum relative to active coil centroid
        coil_sum = np.zeros_like(f, dtype=np.complex128)
        p_incoh = np.zeros_like(f, dtype=np.float64)

        for c in active:
            pos_m = c["position_from_bridge_m"]
            w_m = c.get("aperture_width_in", 0.75) * 0.0254
            weight = c.get("weight", 1.0)
            polarity = c.get("polarity", 1.0)

            delta_x = pos_m - center_pos
            phase = 2.0 * math.pi * f * delta_x / v_disp
            ap_w = 1.0 / np.sqrt(1.0 + (1.0 / 3.0) * (np.pi * w_m * f / v_disp) ** 2)
            w_eff = weight * ap_w

            coil_sum += w_eff * polarity * np.exp(-1j * phase)
            p_incoh += w_eff ** 2

        p_coh = np.abs(coil_sum) ** 2

        if len(active) > 1:
            delta_x_span = max(c["position_from_bridge_m"] for c in active) - min(c["position_from_bridge_m"] for c in active)
            if delta_x_span > 0.002:
                eps_quad = 0.18
                p_coh_reg = p_coh + (eps_quad ** 2) * p_incoh
                dc_incoh = sum(abs(c.get("weight", 1.0)) ** 2 for c in active)
                dc_norm = math.sqrt(total_w ** 2 + (eps_quad ** 2) * dc_incoh) / total_w

                f_start = v / delta_x_span
                f_end = 1.8 * v / delta_x_span
                t = np.clip((f - f_start) / (f_end - f_start), 0.0, 1.0)
                gamma = 0.5 * (1.0 + np.cos(np.pi * t))
                m_blend = np.sqrt(gamma * p_coh_reg + (1.0 - gamma) * p_incoh) / dc_norm
            else:
                m_blend = np.abs(coil_sum)
        else:
            m_blend = np.abs(coil_sum)

        acc += pt_weight * m_blend
        total_pt_weight += pt_weight

    return acc / total_pt_weight if total_pt_weight > 0 else acc

def numpy_pickup_macro_aperture(freqs, coils, scale_length_m: float = None, string_speeds=None, string_names=None):
    """
    Computes the macro sensing aperture response (smooth spatial low-pass envelope
    of the individual coil aperture) averaged across the continuous wave-speed continuum,
    without inter-coil phase cancellation nulls or unphysical sinc sidelobes.
    Used for safe, non-inverting deconvolution of multi-coil source pickups.
    """
    f = np.asarray(freqs, dtype=np.float64)
    w_in = coils[0].get("aperture_width_in", 0.75) if coils else 0.75
    w_m = w_in * 0.0254

    if isinstance(scale_length_m, (list, tuple, np.ndarray)):
        string_speeds = scale_length_m
        scale_length_m = 0.8636

    l_eff = float(scale_length_m) if (scale_length_m is not None and not isinstance(scale_length_m, (list, tuple, np.ndarray)) and scale_length_m > 0) else 0.8636

    if string_speeds is not None and len(string_speeds) > 0 and len(string_speeds) != 24:
        continuum = [{"f0": max(v / (2.0 * l_eff), 15.0), "v0": float(v), "weight": 1.0 / len(string_speeds)} for v in string_speeds]
    else:
        continuum = generate_wave_speed_continuum(l_eff, num_points=24)

    acc = np.zeros_like(f, dtype=np.float64)
    total_w = 0.0
    for pt in continuum:
        f0 = pt["f0"]
        v = pt["v0"]
        weight = pt.get("weight", 1.0)
        v_disp = compute_dispersive_wave_speed(f, v, f0=f0, scale_length_m=l_eff)
        acc += weight * (1.0 / np.sqrt(1.0 + (1.0 / 3.0) * (np.pi * w_m * f / v_disp) ** 2))
        total_w += weight
    return acc / total_w if total_w > 0 else acc

def numpy_aperture(freqs, w_in, d_in, speeds=None, scale_length_m=0.8636):
    """Computes multi-string aperture sinc + dual-coil comb using NumPy across the wave-speed continuum."""
    f = np.asarray(freqs, dtype=np.float64)
    w_m = w_in * 0.0254
    d_m = d_in * 0.0254
    if speeds is None:
        continuum = generate_wave_speed_continuum(scale_length_m)
        speeds = [pt["v0"] for pt in continuum]
    acc = np.zeros_like(f, dtype=np.float64)
    for v in speeds:
        sinc_v = np.abs(np.sinc(w_m * f / v)) + 0.05
        comb_v = np.abs(np.cos(np.pi * d_m * f / v)) + 0.05 if d_in > 0 else 1.0
        acc += (sinc_v * comb_v)
    return acc / len(speeds)

def numpy_position(freqs, pos_m, speeds=None, scale_length_m=0.8636):
    """Computes spatial standing wave envelope using NumPy across the wave-speed continuum."""
    f = np.asarray(freqs, dtype=np.float64)
    if speeds is None:
        continuum = generate_wave_speed_continuum(scale_length_m)
        speeds = [pt["v0"] for pt in continuum]
    acc = np.zeros_like(f, dtype=np.float64)
    for v in speeds:
        arg_p = f * (2.0 * math.pi * pos_m / v)
        acc += (np.abs(np.sin(arg_p)) + 0.15)
    return acc / len(speeds)

def numpy_pickup_electrical_response(freqs, fr, q):
    """
    Computes 2nd-order electrical low-pass magnitude response using NumPy.
    |H_elec(f)| = 1 / sqrt((1 - (f/fr)^2)^2 + (f / (q * fr))^2)
    """
    f = np.asarray(freqs, dtype=np.float64)
    if fr is None or fr <= 0.0 or q is None or q <= 0.0:
        return np.ones_like(f, dtype=np.float64)
    x = f / float(fr)
    denom = np.sqrt((1.0 - x ** 2) ** 2 + (x / float(q)) ** 2)
    return 1.0 / denom

def numpy_pickup_anti_resonance(freqs, fr, q_src, q_target=1.0):
    """
    Computes 2nd-order biquad anti-resonance filter using NumPy.
    |H_anti(f)| = sqrt((1 - (f/fr)^2)^2 + (f / (q_src * fr))^2) / sqrt((1 - (f/fr)^2)^2 + (f / (q_target * fr))^2)
    """
    f = np.asarray(freqs, dtype=np.float64)
    if fr is None or fr <= 0.0 or q_src is None or q_src <= 0.0:
        return np.ones_like(f, dtype=np.float64)
    x = f / float(fr)
    num = np.sqrt((1.0 - x ** 2) ** 2 + (x / float(q_src)) ** 2)
    den = np.sqrt((1.0 - x ** 2) ** 2 + (x / float(q_target)) ** 2)
    return num / den

def resolve_pickup_electrical_response_np(freqs, pickup_cfg, inst_cfg):
    """Resolves electrical frequency response for a source pickup using NumPy."""
    f = np.asarray(freqs, dtype=np.float64)
    p_type = pickup_cfg.get("type", "single_coil")
    if p_type == "composite":
        components = pickup_cfg.get("components", [])
        if not components:
            return np.ones_like(f, dtype=np.float64)
        total_w = sum(c.get("weight", 1.0) for c in components)
        if total_w <= 0.0:
            return np.ones_like(f, dtype=np.float64)
        acc = np.zeros_like(f, dtype=np.float64)
        for comp in components:
            sub_id = comp["pickup"]
            sub_w = comp.get("weight", 1.0)
            sub_p = inst_cfg["pickups"][sub_id]
            sub_elec = resolve_pickup_electrical_response_np(f, sub_p, inst_cfg)
            acc += sub_elec * (sub_w / total_w)
        return acc

    fr = pickup_cfg.get("resonant_frequency_hz")
    q = pickup_cfg.get("q_factor", 1.35)
    return numpy_pickup_electrical_response(f, fr, q)

def resolve_pickup_electrical_deconvolution_np(freqs, pickup_cfg, inst_cfg, q_target=1.0):
    """Resolves anti-resonance flattening filter for a source pickup using NumPy."""
    f = np.asarray(freqs, dtype=np.float64)
    p_type = pickup_cfg.get("type", "single_coil")
    if p_type == "composite":
        components = pickup_cfg.get("components", [])
        has_fr = any(
            inst_cfg.get("pickups", {}).get(c.get("pickup", ""), {}).get("resonant_frequency_hz")
            for c in components
        )
        if not has_fr:
            return np.ones_like(f, dtype=np.float64)
        total_w = sum(c.get("weight", 1.0) for c in components)
        if total_w <= 0.0:
            return np.ones_like(f, dtype=np.float64)
        acc = np.zeros_like(f, dtype=np.float64)
        for comp in components:
            sub_id = comp["pickup"]
            sub_w = comp.get("weight", 1.0)
            sub_p = inst_cfg["pickups"][sub_id]
            sub_deconv = resolve_pickup_electrical_deconvolution_np(f, sub_p, inst_cfg, q_target=q_target)
            acc += sub_deconv * (sub_w / total_w)
        return acc

    fr = pickup_cfg.get("resonant_frequency_hz")
    if fr is None or fr <= 0.0:
        return np.ones_like(f, dtype=np.float64)
    q_src = pickup_cfg.get("q_factor", 1.35)
    return numpy_pickup_anti_resonance(f, fr, q_src, q_target=q_target)

# Clean canonical aliases for active vectorized DSP functions
pickup_acoustic_response = numpy_pickup_acoustic_response
aperture_response = numpy_aperture
position_envelope = numpy_position
pickup_electrical_response = numpy_pickup_electrical_response
pickup_anti_resonance = numpy_pickup_anti_resonance
resolve_pickup_electrical_response = resolve_pickup_electrical_response_np
resolve_pickup_electrical_deconvolution = resolve_pickup_electrical_deconvolution_np

def compute_voice_prefilter_firs(voice_id, instrument="30in", src_scale=None, num_taps=NUM_TAPS):
    """
    Computes acoustic pre-filter FIRs for each pickup in a target voice configuration using NumPy.
    For single-pickup voices, returns a list with 1 FIR: [fir].
    For multi-pickup voices (e.g. Jazz pair, P/J, P/MM), returns a list of FIRs:
    [fir_pickup_0, fir_pickup_1, ...], enabling independent channel excitation in SPICE.
    """
    cfg = VOICES[voice_id]
    target_scale_key = cfg.get("scale", "34in")
    tgt = SCALES[target_scale_key]
    tgt_speeds = tgt["speeds"]

    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    src_scale_in = inst.get("scale_length_in", 34.0)
    src_scale_m = inst.get("scale_length_m", src_scale_in * 0.0254)
    tgt_scale_m = tgt.get("scale_m", tgt.get("scale_length_m", 0.8636))

    src_pickup = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_pickup, inst)
    src_pos_eff = compute_effective_position(src_coils)

    freqs = np.asarray(FREQS, dtype=np.float64)

    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, scale_length_m=src_scale_m)

    src_string = get_instrument_string(inst)
    tgt_string = get_voice_string(cfg)

    # Scale-Length Tension & Body Bloom Filter
    tgt_scale_in = 37.0 if target_scale_key in ["multiscale", "37in"] else 34.0
    if target_scale_key == "upright":
        # Upright string physics & body bloom: deep fundamental, woody low-mids
        # Modulated by differential bloom between target double-bass strings and source instrument strings
        delta_bloom = float(tgt_string.get("bloom_db", 2.8)) - float(src_string.get("bloom_db", 0.0))
        g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
        h_bloom = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        h_tension = h_bloom
    elif src_scale_in < tgt_scale_in:
        snap_db = min(3.5, 1.8 * (tgt_scale_in - src_scale_in) / 4.0)
        g_snap = 10.0 ** (snap_db / 20.0)
        h_tension = np.sqrt((1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2))
    else:
        h_tension = np.ones_like(freqs)

    sensor_type = cfg.get("sensor_type", "magnetic")
    pickups = resolve_voice_pickups(cfg)
    is_identity = (sensor_type != "bridge_force") and is_voice_matching_source(inst, voice_id, cfg)

    cir_rel = cfg.get("circuit")
    cir_path = (REPO_ROOT / cir_rel) if cir_rel else None
    has_multichannel_circuit = bool(cir_path and cir_path.exists() and len(pickups) > 1)

    # Resolve branch-matched source coils if source is a composite blend matching target branch count
    src_components = src_pickup.get("components", []) if src_pickup.get("type") == "composite" else []
    use_branch_matching = (len(src_components) == len(pickups) and len(pickups) > 1)

    # For passive or circuit-modeled source instruments, electrical deconvolution is handled directly in the differential SPICE engine
    has_src_circuit = bool(src_pickup.get("circuit"))
    is_passive = (inst.get("electronics") == "passive")
    h_elec_inv = np.ones_like(freqs) if (is_identity or is_passive or has_src_circuit) else resolve_pickup_electrical_deconvolution_np(freqs, src_pickup, inst)
    
    positions = [compute_effective_position(p["coils"]) for p in pickups]
    pos_max = max(positions) if positions else 0.0
    c_mean = 2.0 * tgt_scale_m * MEAN_BASS_F0
    raw_firs = []
    for i, p in enumerate(pickups):
        p_coils = p["coils"]
        tgt_pos_eff = positions[i]

        if use_branch_matching:
            comp_sub_id = src_components[i]["pickup"]
            comp_sub_p = inst["pickups"][comp_sub_id]
            b_src_coils = resolve_pickup_coils(comp_sub_p, inst)
            b_src_pos_eff = compute_effective_position(b_src_coils)
            b_src_acoustic = numpy_pickup_acoustic_response(freqs, b_src_coils, scale_length_m=src_scale_m)
        else:
            b_src_coils = src_coils
            b_src_pos_eff = src_pos_eff
            b_src_acoustic = h_src_acoustic

        if sensor_type == "bridge_force":
            # 1. Band-limited de-combing: smoothly tapers off after the source pickup's first
            # constructive peak (c_mean / x_src) to eliminate higher-order spatial comb ripples
            eps = 0.08
            h_decomb_raw = b_src_acoustic / (b_src_acoustic ** 2 + eps)
            mid_mask = (freqs >= 100.0) & (freqs <= 1000.0)
            h_decomb_raw = h_decomb_raw / np.median(h_decomb_raw[mid_mask])

            c_mean_src = 2.0 * src_scale_m * MEAN_BASS_F0
            pos_eff = max(b_src_pos_eff, 0.035)
            f_peak_src = c_mean_src / pos_eff
            f_taper_start = min(f_peak_src, 2500.0)
            f_taper_end = min(1.8 * f_taper_start, 4500.0)
            t = np.clip((freqs - f_taper_start) / (f_taper_end - f_taper_start), 0.0, 1.0)
            w = 0.5 * (1.0 + np.cos(np.pi * t))
            h_decomb = w * h_decomb_raw + (1.0 - w) * 1.0

            # 2. Pure acoustic spruce wood damping (monotonically falling above 3.8-4.2 kHz)
            is_flatwound = "flat" in src_string.get("type", "")
            f_damp = 4200.0 if is_flatwound else 3600.0
            h_damp = 1.0 / np.sqrt((1.0 - (freqs / f_damp) ** 2) ** 2 + 2.0 * (freqs / f_damp) ** 2)

            # 3. Subsonic rumble cut (32 Hz with smooth -16.5 dB DC shelf floor to prevent cepstral zero)
            g_sub = 0.15
            h_sub = np.sqrt((g_sub ** 2 * 32.0 ** 2 + freqs ** 2) / (32.0 ** 2 + freqs ** 2))

            h_acoustic_transfer = h_decomb * h_damp * h_sub

            # 4. Leaky velocity-to-force integrator (+6 dB/oct from 70 Hz to 250 Hz)
            h_tilt = np.sqrt((1.0 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 70.0) ** 2))
            h_tilt = h_tilt / np.max(h_tilt)
        elif is_identity:
            h_acoustic_transfer = np.ones_like(freqs)
            h_tilt = np.ones_like(freqs)
        else:
            h_tgt_acoustic = numpy_pickup_acoustic_response(freqs, p_coils, scale_length_m=tgt_scale_m)
            h_src_macro = numpy_pickup_macro_aperture(freqs, b_src_coils, scale_length_m=src_scale_m)
            eps = 0.01
            h_quotient = (h_tgt_acoustic * h_src_macro) / (h_src_macro ** 2 + eps ** 2)
            q_db = 20.0 * np.log10(np.maximum(h_quotient, 1e-6))
            g_max_db = 8.0
            g_min_db = -14.0
            q_soft_db = np.where(
                q_db > 0.0,
                g_max_db * np.tanh(q_db / g_max_db),
                g_min_db * np.tanh(q_db / g_min_db),
            )
            h_acoustic_transfer = 10.0 ** (q_soft_db / 20.0)

            eta_tgt = tgt_pos_eff / tgt_scale_m
            eta_src = b_src_pos_eff / src_scale_m
            delta_in = (eta_tgt - eta_src) * 34.0
            tilt_db = delta_in * 1.5
            g_low = 10.0 ** (tilt_db / 20.0)
            g_hi = 10.0 ** (-tilt_db / 20.0)
            h_low_tilt = np.sqrt((g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2))
            h_hi_tilt = np.sqrt((1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2))
            h_tilt = h_low_tilt * h_hi_tilt

        p_weight = 1.0 if has_multichannel_circuit else p.get("weight", 1.0)
        p_pol = p.get("polarity", 1.0)
        scale_fac = abs(p_weight * p_pol)

        # Differential string transfer for specialized target voicing strings (e.g. vintage flats, multiscale)
        if sensor_type != "bridge_force" and cfg.get("target_string") and cfg.get("target_string") != "roundwound_nickel_standard":
            h_str_diff = compute_differential_string_transfer(freqs, src_string, tgt_string)
        else:
            h_str_diff = np.ones_like(freqs)

        h_scale_tension = np.ones_like(freqs) if is_identity else h_tension
        prefilter_curve = scale_fac * h_acoustic_transfer * h_elec_inv * h_tilt * h_scale_tension * h_str_diff
        fir_raw = synthesize_minimum_phase_fir(prefilter_curve, num_taps=num_taps, normalize=False)

        # Spatial acoustic wave propagation delay for multi-pickup configurations
        if is_identity:
            tau_i = 0.0
        elif use_branch_matching:
            src_positions = [compute_effective_position(resolve_pickup_coils(inst["pickups"][c["pickup"]], inst)) for c in src_components]
            src_pos_max = max(src_positions) if src_positions else 0.0
            src_c_mean = 2.0 * src_scale_m * MEAN_BASS_F0
            tau_src_i = (src_pos_max - src_positions[i]) / src_c_mean if i < len(src_positions) else 0.0
            tau_tgt_i = (pos_max - positions[i]) / c_mean
            tau_i = max(0.0, tau_tgt_i - tau_src_i)
        elif len(pickups) > 1:
            tau_i = (pos_max - positions[i]) / c_mean
        else:
            tau_i = 0.0

        if tau_i > 0.0:
            n_fft_delay = 1 << (len(fir_raw) * 2 - 1).bit_length()
            H_fir = np.fft.rfft(fir_raw, n_fft_delay)
            f_bins = np.fft.rfftfreq(n_fft_delay, 1.0 / 48000.0)
            H_delayed = H_fir * np.exp(-1j * 2.0 * np.pi * f_bins * tau_i)
            fir_raw = np.fft.irfft(H_delayed, n_fft_delay)[:num_taps].tolist()

        raw_firs.append(fir_raw)

    global_peak = max(max(abs(x) for x in fir) for fir in raw_firs)
    if global_peak > 0:
        return [[(x / global_peak) * 0.99 for x in fir] for fir in raw_firs]
    return raw_firs

def compute_aperture_prefilter_fir(voice_id, instrument="30in", src_scale=None, num_taps=NUM_TAPS):
    """
    Computes a single composite acoustic pre-filter FIR using NumPy.
    Retained for backward compatibility. For multi-pickup independent channels,
    use compute_voice_prefilter_firs().
    """
    cfg = VOICES[voice_id]
    pickups = resolve_voice_pickups(cfg)
    if len(pickups) == 1:
        firs = compute_voice_prefilter_firs(voice_id, instrument=instrument, src_scale=src_scale, num_taps=num_taps)
        return firs[0]

    target_scale_key = cfg.get("scale", "34in")
    tgt = SCALES[target_scale_key]

    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    src_scale_in = inst.get("scale_length_in", 34.0)
    src_scale_m = inst.get("scale_length_m", src_scale_in * 0.0254)
    tgt_scale_m = tgt.get("scale_m", tgt.get("scale_length_m", 0.8636))

    src_pickup = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_pickup, inst)
    tgt_coils = resolve_voice_coils(cfg)

    src_pos_eff = compute_effective_position(src_coils)
    tgt_pos_eff = compute_effective_position(tgt_coils)

    freqs = np.asarray(FREQS, dtype=np.float64)

    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, scale_length_m=src_scale_m)

    src_string = get_instrument_string(inst)
    tgt_string = get_voice_string(cfg)

    sensor_type = cfg.get("sensor_type", "magnetic")
    is_identity = (sensor_type != "bridge_force") and is_voice_matching_source(inst, voice_id, cfg)
    if sensor_type == "bridge_force":
        eps = 0.08
        h_decomb_raw = h_src_acoustic / (h_src_acoustic ** 2 + eps)
        mid_mask = (freqs >= 100.0) & (freqs <= 1000.0)
        h_decomb_raw = h_decomb_raw / np.median(h_decomb_raw[mid_mask])

        c_mean_src = 2.0 * src_scale_m * MEAN_BASS_F0
        pos_eff = max(src_pos_eff, 0.035)
        f_peak_src = c_mean_src / pos_eff
        f_taper_start = min(f_peak_src, 2500.0)
        f_taper_end = min(1.8 * f_taper_start, 4500.0)
        t = np.clip((freqs - f_taper_start) / (f_taper_end - f_taper_start), 0.0, 1.0)
        w = 0.5 * (1.0 + np.cos(np.pi * t))
        h_decomb = w * h_decomb_raw + (1.0 - w) * 1.0

        is_flatwound = "flat" in src_string.get("type", "")
        f_damp = 4200.0 if is_flatwound else 3600.0
        h_damp = 1.0 / np.sqrt((1.0 - (freqs / f_damp) ** 2) ** 2 + 2.0 * (freqs / f_damp) ** 2)

        g_sub = 0.15
        h_sub = np.sqrt((g_sub ** 2 * 32.0 ** 2 + freqs ** 2) / (32.0 ** 2 + freqs ** 2))

        h_acoustic_transfer = h_decomb * h_damp * h_sub

        h_tilt = np.sqrt((1.0 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 70.0) ** 2))
        h_tilt = h_tilt / np.max(h_tilt)
    elif is_identity:
        h_acoustic_transfer = np.ones_like(freqs)
        h_tilt = np.ones_like(freqs)
    else:
        h_tgt_acoustic = numpy_pickup_acoustic_response(freqs, tgt_coils, scale_length_m=tgt_scale_m)
        h_src_macro = numpy_pickup_macro_aperture(freqs, src_coils, scale_length_m=src_scale_m)
        eps = 0.01
        h_quotient = (h_tgt_acoustic * h_src_macro) / (h_src_macro ** 2 + eps ** 2)
        q_db = 20.0 * np.log10(np.maximum(h_quotient, 1e-6))
        g_max_db = 8.0
        g_min_db = -14.0
        q_soft_db = np.where(
            q_db > 0.0,
            g_max_db * np.tanh(q_db / g_max_db),
            g_min_db * np.tanh(q_db / g_min_db),
        )
        h_acoustic_transfer = 10.0 ** (q_soft_db / 20.0)
        eta_tgt = tgt_pos_eff / tgt_scale_m
        eta_src = src_pos_eff / src_scale_m
        delta_in = (eta_tgt - eta_src) * 34.0
        tilt_db = delta_in * 1.5
        g_low = 10.0 ** (tilt_db / 20.0)
        g_hi = 10.0 ** (-tilt_db / 20.0)
        h_low_tilt = np.sqrt((g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2))
        h_hi_tilt = np.sqrt((1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2))
        h_tilt = h_low_tilt * h_hi_tilt

    src_scale_in = inst.get("scale_length_in", 34.0)
    tgt_scale_in = 37.0 if target_scale_key in ["multiscale", "37in"] else 34.0
    if is_identity:
        h_tension = np.ones_like(freqs)
    elif target_scale_key == "upright":
        # Upright string physics & body bloom: deep fundamental, woody low-mids
        delta_bloom = float(tgt_string.get("bloom_db", 2.8)) - float(src_string.get("bloom_db", 0.0))
        g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
        h_bloom = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        h_tension = h_bloom
    elif src_scale_in < tgt_scale_in:
        snap_db = min(3.5, 1.8 * (tgt_scale_in - src_scale_in) / 4.0)
        g_snap = 10.0 ** (snap_db / 20.0)
        h_tension = np.sqrt((1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2))
    else:
        h_tension = np.ones_like(freqs)

    # Differential string transfer for specialized target voicing strings (e.g. vintage flats, multiscale)
    if sensor_type != "bridge_force" and cfg.get("target_string") and cfg.get("target_string") != "roundwound_nickel_standard":
        h_str_diff = compute_differential_string_transfer(freqs, src_string, tgt_string)
    else:
        h_str_diff = np.ones_like(freqs)

    has_src_circuit = bool(src_pickup.get("circuit"))
    is_passive = (inst.get("electronics") == "passive")
    h_elec_inv = np.ones_like(freqs) if (is_identity or is_passive or has_src_circuit) else resolve_pickup_electrical_deconvolution_np(freqs, src_pickup, inst)

    prefilter_curve = h_acoustic_transfer * h_elec_inv * h_tilt * h_tension * h_str_diff
    max_val = np.max(prefilter_curve)
    resp_norm = prefilter_curve / max_val if max_val > 0 else prefilter_curve

    return synthesize_minimum_phase_fir(resp_norm, num_taps=num_taps)


