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
            buf = bytearray()
            for s in samples:
                val = max(-8388608, min(8388607, int(s * 8388607.0)))
                buf.extend(val.to_bytes(3, byteorder="little", signed=True))
            wf.writeframes(buf)

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
        "34in_active_p": "34in_active_p",
        "active_p": "34in_active_p",
        "34in_active_jazz": "34in_active_jazz",
        "active_jazz": "34in_active_jazz",
        "active_j": "34in_active_jazz",
        "34in_active_pj": "34in_active_pj",
        "active_pj": "34in_active_pj"
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

    ratio = tgt_mag / np.maximum(src_mag, 0.05)
    h_damp_ratio = np.clip(ratio, 0.15, 3.0)

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
    Checks if a target voice physically matches the source instrument's pickup and scale,
    meaning zero spatial or acoustic transfer is required (identity transformation).
    """
    inst = load_instrument(instrument) if not isinstance(instrument, dict) else instrument
    vcfg = voice_cfg or VOICES.get(voice_id, {})

    src_speeds = inst.get("string_wave_speeds", [])
    tgt_scale = vcfg.get("scale", "34in")
    tgt_speeds = SCALES.get(tgt_scale, {}).get("speeds", [])

    if len(src_speeds) != len(tgt_speeds) or not np.allclose(src_speeds, tgt_speeds, rtol=0.02):
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

def numpy_pickup_acoustic_response(freqs, coils, string_speeds, string_names=None):
    """
    Computes compound spatial aperture and multi-coil response for an arbitrary
    array of N physical coils across multi-string wave speeds using NumPy vector math.
    Respects per-string coil bindings (e.g. P-Bass split E/A vs D/G coils).
    Preserves 0 dB low-frequency fundamental without artificial standing-wave comb nulls.
    """
    f = np.asarray(freqs, dtype=np.float64)
    if string_names is None:
        if len(string_speeds) == 4:
            string_names = ["E", "A", "D", "G"]
        elif len(string_speeds) == 5:
            string_names = ["B", "E", "A", "D", "G"]
        else:
            string_names = [f"S{i}" for i in range(len(string_speeds))]

    acc = np.zeros_like(f, dtype=np.float64)
    for s_name, v in zip(string_names, string_speeds):
        active = [
            c for c in coils
            if "all" in c.get("strings", ["all"]) or s_name in c.get("strings", [])
        ]
        if not active:
            active = coils

        total_w = sum(abs(c.get("weight", 1.0)) for c in active) or 1.0
        center_pos = sum(c["position_from_bridge_m"] * abs(c.get("weight", 1.0)) for c in active) / total_w

        # Complex phasor sum relative to active coil centroid
        coil_sum = np.zeros_like(f, dtype=np.complex128)
        for c in active:
            pos_m = c["position_from_bridge_m"]
            w_m = c.get("aperture_width_in", 0.75) * 0.0254
            weight = c.get("weight", 1.0)
            polarity = c.get("polarity", 1.0)

            delta_x = pos_m - center_pos
            phase = 2.0 * math.pi * f * delta_x / v
            sinc_w = np.sinc(w_m * f / v)

            coil_sum += weight * polarity * sinc_w * np.exp(-1j * phase)

        acc += np.abs(coil_sum)

    return acc / len(string_speeds)

def numpy_pickup_macro_aperture(freqs, coils, string_speeds):
    """
    Computes the macro sensing aperture response (sinc envelope of the individual coil aperture)
    averaged across string wave speeds, without inter-coil phase cancellation nulls.
    Used for safe, non-inverting deconvolution of multi-coil source pickups.
    """
    f = np.asarray(freqs, dtype=np.float64)
    w_in = coils[0].get("aperture_width_in", 0.75) if coils else 0.75
    w_m = w_in * 0.0254
    acc = np.zeros_like(f, dtype=np.float64)
    for v in string_speeds:
        acc += np.abs(np.sinc(w_m * f / v))
    return acc / len(string_speeds)

def numpy_aperture(freqs, w_in, d_in, speeds):
    """Computes multi-string aperture sinc + dual-coil comb using NumPy."""
    f = np.asarray(freqs, dtype=np.float64)
    w_m = w_in * 0.0254
    d_m = d_in * 0.0254
    acc = np.zeros_like(f, dtype=np.float64)
    for v in speeds:
        sinc_v = np.abs(np.sinc(w_m * f / v)) + 0.05
        comb_v = np.abs(np.cos(np.pi * d_m * f / v)) + 0.05 if d_in > 0 else 1.0
        acc += (sinc_v * comb_v)
    return acc / len(speeds)

def numpy_position(freqs, pos_m, speeds):
    """Computes spatial standing wave envelope using NumPy."""
    f = np.asarray(freqs, dtype=np.float64)
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

    src_speeds = inst.get("string_wave_speeds")
    if not src_speeds:
        l_m = inst.get("scale_length_m", inst.get("scale_length_in", 34.0) * 0.0254)
        src_speeds = [2.0 * l_m * f0 for f0 in [41.203, 55.0, 73.416, 97.999]]

    src_pickup = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_pickup, inst)
    src_pos_eff = compute_effective_position(src_coils)

    freqs = np.asarray(FREQS, dtype=np.float64)

    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, src_speeds)

    src_string = get_instrument_string(inst)
    tgt_string = get_voice_string(cfg)

    # Scale-Length Tension & Body Bloom Filter
    src_scale_in = inst.get("scale_length_in", 34.0)
    if target_scale_key == "upright":
        # Upright string physics & body bloom: deep fundamental, woody low-mids
        # Modulated by differential bloom between target double-bass strings and source instrument strings
        delta_bloom = float(tgt_string.get("bloom_db", 2.8)) - float(src_string.get("bloom_db", 0.0))
        g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
        h_bloom = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        h_tension = h_bloom
    elif target_scale_key == "34in" and src_scale_in != 34.0:
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = np.sqrt((1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2))
    else:
        h_tension = np.ones_like(freqs)

    sensor_type = cfg.get("sensor_type", "magnetic")
    pickups = resolve_voice_pickups(cfg)
    is_identity = (sensor_type != "bridge_force") and is_voice_matching_source(inst, voice_id, cfg)

    # Resolve branch-matched source coils if source is a composite blend matching target branch count
    src_components = src_pickup.get("components", []) if src_pickup.get("type") == "composite" else []
    use_branch_matching = (len(src_components) == len(pickups) and len(pickups) > 1)

    # Active Pickup Electrical Resonance Deconvolution (Wiener Inversion)
    # For passive source instruments, electrical deconvolution is handled directly in the differential SPICE engine
    is_passive = (inst.get("electronics") == "passive")
    h_elec_inv = np.ones_like(freqs) if (is_identity or is_passive) else resolve_pickup_electrical_deconvolution_np(freqs, src_pickup, inst)
    raw_firs = []
    for i, p in enumerate(pickups):
        p_coils = p["coils"]
        tgt_pos_eff = compute_effective_position(p_coils)

        if use_branch_matching:
            comp_sub_id = src_components[i]["pickup"]
            comp_sub_p = inst["pickups"][comp_sub_id]
            b_src_coils = resolve_pickup_coils(comp_sub_p, inst)
            b_src_pos_eff = compute_effective_position(b_src_coils)
            b_src_acoustic = numpy_pickup_acoustic_response(freqs, b_src_coils, src_speeds)
        else:
            b_src_coils = src_coils
            b_src_pos_eff = src_pos_eff
            b_src_acoustic = h_src_acoustic

        if sensor_type == "bridge_force":
            # 1. Band-limited de-combing: active in 100 Hz - 1.8 kHz passband, smoothly tapering
            # to 1.0 between 1.8 kHz and 3.2 kHz to eliminate high-frequency comb ripples
            eps = 0.08
            h_decomb_raw = b_src_acoustic / (b_src_acoustic ** 2 + eps)
            mid_mask = (freqs >= 100.0) & (freqs <= 1000.0)
            h_decomb_raw = h_decomb_raw / np.median(h_decomb_raw[mid_mask])

            f_taper_start = 1800.0
            f_taper_end = 3200.0
            t = np.clip((freqs - f_taper_start) / (f_taper_end - f_taper_start), 0.0, 1.0)
            w = 0.5 * (1.0 + np.cos(np.pi * t))
            h_decomb = w * h_decomb_raw + (1.0 - w) * 1.0

            # 2. Pure acoustic spruce wood damping (monotonically falling above 3.8-4.2 kHz)
            is_flatwound = "flat" in src_string.get("type", "")
            f_damp = 4200.0 if is_flatwound else 3600.0
            h_damp = 1.0 / np.sqrt((1.0 - (freqs / f_damp) ** 2) ** 2 + 2.0 * (freqs / f_damp) ** 2)

            # 3. Subsonic rumble cut (32 Hz with -16.5 dB DC shelf floor to prevent cepstral zero)
            h_sub = np.maximum(freqs / np.sqrt(freqs ** 2 + 32.0 ** 2), 0.15)

            h_acoustic_transfer = h_decomb * h_damp * h_sub

            # 4. Leaky velocity-to-force integrator (+6 dB/oct from 70 Hz to 250 Hz)
            h_tilt = np.sqrt((1.0 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 70.0) ** 2))
            h_tilt = h_tilt / np.max(h_tilt)
        elif is_identity:
            h_acoustic_transfer = np.ones_like(freqs)
            h_tilt = np.ones_like(freqs)
        else:
            h_tgt_acoustic = numpy_pickup_acoustic_response(freqs, p_coils, tgt_speeds)
            h_src_macro = numpy_pickup_macro_aperture(freqs, b_src_coils, src_speeds)
            h_ratio = h_tgt_acoustic / np.maximum(h_src_macro, 0.08)
            h_acoustic_transfer = np.clip(h_ratio, 0.25, 2.5)

            delta_in = (tgt_pos_eff - b_src_pos_eff) / 0.0254
            tilt_db = delta_in * 1.5
            g_low = 10.0 ** (tilt_db / 20.0)
            g_hi = 10.0 ** (-tilt_db / 20.0)
            h_low_tilt = np.sqrt((g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2))
            h_hi_tilt = np.sqrt((1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2))
            h_tilt = h_low_tilt * h_hi_tilt

        p_weight = p.get("weight", 1.0)
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
    tgt_speeds = tgt["speeds"]

    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    src_speeds = inst.get("string_wave_speeds")
    if not src_speeds:
        l_m = inst.get("scale_length_m", inst.get("scale_length_in", 34.0) * 0.0254)
        src_speeds = [2.0 * l_m * f0 for f0 in [41.203, 55.0, 73.416, 97.999]]

    src_pickup = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_pickup, inst)
    tgt_coils = resolve_voice_coils(cfg)

    src_pos_eff = compute_effective_position(src_coils)
    tgt_pos_eff = compute_effective_position(tgt_coils)

    freqs = np.asarray(FREQS, dtype=np.float64)

    h_src_acoustic = numpy_pickup_acoustic_response(freqs, src_coils, src_speeds)

    src_string = get_instrument_string(inst)
    tgt_string = get_voice_string(cfg)

    sensor_type = cfg.get("sensor_type", "magnetic")
    is_identity = (sensor_type != "bridge_force") and is_voice_matching_source(inst, voice_id, cfg)
    if sensor_type == "bridge_force":
        # 1. Band-limited de-combing: active in 100 Hz - 1.8 kHz passband, smoothly tapering
        # to 1.0 between 1.8 kHz and 3.2 kHz to eliminate high-frequency comb ripples
        eps = 0.08
        h_decomb_raw = h_src_acoustic / (h_src_acoustic ** 2 + eps)
        mid_mask = (freqs >= 100.0) & (freqs <= 1000.0)
        h_decomb_raw = h_decomb_raw / np.median(h_decomb_raw[mid_mask])

        f_taper_start = 1800.0
        f_taper_end = 3200.0
        t = np.clip((freqs - f_taper_start) / (f_taper_end - f_taper_start), 0.0, 1.0)
        w = 0.5 * (1.0 + np.cos(np.pi * t))
        h_decomb = w * h_decomb_raw + (1.0 - w) * 1.0

        # 2. Pure acoustic spruce wood damping (monotonically falling above 3.8-4.2 kHz)
        is_flatwound = "flat" in src_string.get("type", "")
        f_damp = 4200.0 if is_flatwound else 3600.0
        h_damp = 1.0 / np.sqrt((1.0 - (freqs / f_damp) ** 2) ** 2 + 2.0 * (freqs / f_damp) ** 2)

        # 3. Subsonic rumble cut (32 Hz with -16.5 dB DC shelf floor to prevent cepstral zero)
        h_sub = np.maximum(freqs / np.sqrt(freqs ** 2 + 32.0 ** 2), 0.15)

        h_acoustic_transfer = h_decomb * h_damp * h_sub

        # 4. Leaky velocity-to-force integrator (+6 dB/oct from 70 Hz to 250 Hz)
        h_tilt = np.sqrt((1.0 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 70.0) ** 2))
        h_tilt = h_tilt / np.max(h_tilt)
    elif is_identity:
        h_acoustic_transfer = np.ones_like(freqs)
        h_tilt = np.ones_like(freqs)
    else:
        h_tgt_acoustic = numpy_pickup_acoustic_response(freqs, tgt_coils, tgt_speeds)
        h_src_macro = numpy_pickup_macro_aperture(freqs, src_coils, src_speeds)
        h_ratio = h_tgt_acoustic / np.maximum(h_src_macro, 0.08)
        h_acoustic_transfer = np.clip(h_ratio, 0.25, 2.5)

        delta_in = (tgt_pos_eff - src_pos_eff) / 0.0254
        tilt_db = delta_in * 1.5
        g_low = 10.0 ** (tilt_db / 20.0)
        g_hi = 10.0 ** (-tilt_db / 20.0)
        h_low_tilt = np.sqrt((g_low ** 2 + (freqs / 250.0) ** 2) / (1.0 + (freqs / 250.0) ** 2))
        h_hi_tilt = np.sqrt((1.0 + g_hi ** 2 * (freqs / 2200.0) ** 2) / (1.0 + (freqs / 2200.0) ** 2))
        h_tilt = h_low_tilt * h_hi_tilt

    src_scale_in = inst.get("scale_length_in", 34.0)
    if is_identity:
        h_tension = np.ones_like(freqs)
    elif target_scale_key == "upright":
        # Upright string physics & body bloom: deep fundamental, woody low-mids
        delta_bloom = float(tgt_string.get("bloom_db", 2.8)) - float(src_string.get("bloom_db", 0.0))
        g_bloom = 10.0 ** (max(delta_bloom, 0.5) / 20.0)
        h_bloom = np.sqrt((g_bloom ** 2 + (freqs / 100.0) ** 2) / (1.0 + (freqs / 100.0) ** 2))
        h_tension = h_bloom
    elif target_scale_key == "34in" and src_scale_in != 34.0:
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = np.sqrt((1.0 + g_snap ** 2 * (freqs / 2800.0) ** 2) / (1.0 + (freqs / 2800.0) ** 2))
    else:
        h_tension = np.ones_like(freqs)

    # Differential string transfer for specialized target voicing strings (e.g. vintage flats, multiscale)
    if sensor_type != "bridge_force" and cfg.get("target_string") and cfg.get("target_string") != "roundwound_nickel_standard":
        h_str_diff = compute_differential_string_transfer(freqs, src_string, tgt_string)
    else:
        h_str_diff = np.ones_like(freqs)

    is_passive = (inst.get("electronics") == "passive")
    h_elec_inv = np.ones_like(freqs) if (is_identity or is_passive) else resolve_pickup_electrical_deconvolution_np(freqs, src_pickup, inst)

    prefilter_curve = h_acoustic_transfer * h_elec_inv * h_tilt * h_tension * h_str_diff
    max_val = np.max(prefilter_curve)
    resp_norm = prefilter_curve / max_val if max_val > 0 else prefilter_curve

    return synthesize_minimum_phase_fir(resp_norm, num_taps=num_taps)


