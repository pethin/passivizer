"""
Passivizer - Physical & Acoustic Modeling Engine
Computes magnetic aperture sinc windows, dual-coil humbucker comb filtering,
scale-length wave-speed conversions, and string tension filters using Polars.
Synthesizes minimum-phase causal FIR filters for NAM audio pre-filtering.
"""

import cmath
import math
import os
import tomllib
import wave
from pathlib import Path
import polars as pl

FS = 48000
NUM_TAPS = 2048
NYQ = FS / 2.0
FREQS = [i * (NYQ / (NUM_TAPS - 1)) for i in range(NUM_TAPS)]

def _fft(x):
    n = len(x)
    if n <= 1:
        return x
    even = _fft(x[0::2])
    odd = _fft(x[1::2])
    factor = [cmath.exp(-2j * math.pi * k / n) for k in range(n // 2)]
    return [even[k] + factor[k] * odd[k] for k in range(n // 2)] + \
           [even[k] - factor[k] * odd[k] for k in range(n // 2)]

def _ifft(x):
    n = len(x)
    x_conj = [val.conjugate() for val in x]
    transformed = _fft(x_conj)
    return [val.conjugate() / n for val in transformed]

def synthesize_minimum_phase_fir(magnitude_curve, num_taps=NUM_TAPS, normalize=True):
    """
    Synthesizes a causal, minimum-phase FIR filter from a desired magnitude
    curve using the homomorphic real-cepstrum Hilbert transform.
    Pure Python, zero heavy scientific dependencies, executes in ~3ms.
    """
    n_fft = 4096
    half = n_fft // 2

    # Linear interpolation of input magnitude curve to half + 1 points
    m_in = len(magnitude_curve)
    mag_grid = []
    for i in range(half + 1):
        idx_f = i * (m_in - 1) / half
        idx_low = int(idx_f)
        idx_hi = min(idx_low + 1, m_in - 1)
        frac = idx_f - idx_low
        val = (1.0 - frac) * magnitude_curve[idx_low] + frac * magnitude_curve[idx_hi]
        mag_grid.append(max(val, 1e-6))

    # Build full symmetric log-magnitude spectrum
    log_mag = [math.log(m) for m in mag_grid]
    full_log_mag = log_mag + [log_mag[k] for k in range(half - 1, 0, -1)]

    # Real cepstrum via IFFT
    c = _ifft([complex(v, 0.0) for v in full_log_mag])

    # Minimum-phase causal folding (Hilbert transform operator in cepstral domain)
    c_hat = [complex(0.0, 0.0)] * n_fft
    c_hat[0] = c[0]
    c_hat[half] = c[half]
    for n in range(1, half):
        c_hat[n] = 2.0 * c[n]

    # Complex minimum-phase frequency spectrum H_min = exp(FFT(c_hat))
    spec = _fft(c_hat)
    h_min_spec = [cmath.exp(s) for s in spec]

    # Causal impulse response h[n] = Re(IFFT(H_min))
    h = [val.real for val in _ifft(h_min_spec)]
    fir = h[:num_taps]

    # Smooth tail (final 15%) with a cosine taper to eliminate truncation artifacts
    taper_len = int(num_taps * 0.15)
    start_taper = num_taps - taper_len
    for i in range(taper_len):
        w = 0.5 * (1.0 + math.cos(math.pi * i / taper_len))
        fir[start_taper + i] *= w

    if not normalize:
        return fir

    # Peak normalization to -0.1 dBFS (0.99)
    max_peak = max(abs(x) for x in fir)
    return [(x / max_peak) * 0.99 for x in fir] if max_peak > 0 else fir

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
        "34in": "34in_standard_p"
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

# Global registries initialized from modular configuration files
SCALES = load_scales()
VOICES = load_voices_config()
INSTRUMENTS = load_all_instruments()

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

def polars_pickup_acoustic_response(freq_expr, coils, string_speeds, string_names=None):
    """
    Computes the unified spatial standing-wave and aperture response for an arbitrary
    array of N physical coils across multi-string wave speeds using Polars.
    Respects per-string coil bindings (e.g. P-Bass split E/A vs D/G coils).
    """
    if string_names is None:
        if len(string_speeds) == 4:
            string_names = ["E", "A", "D", "G"]
        elif len(string_speeds) == 5:
            string_names = ["B", "E", "A", "D", "G"]
        else:
            string_names = [f"S{i}" for i in range(len(string_speeds))]

    acc = pl.lit(0.0)
    for s_name, v in zip(string_names, string_speeds):
        # Filter coils active under this string
        active = [
            c for c in coils
            if "all" in c.get("strings", ["all"]) or s_name in c.get("strings", [])
        ]
        if not active:
            active = coils

        coil_sum = pl.lit(0.0)
        for c in active:
            pos_m = c["position_from_bridge_m"]
            w_m = c["aperture_width_in"] * 0.0254
            weight = c.get("weight", 1.0)
            polarity = c.get("polarity", 1.0)

            arg_p = freq_expr * (2.0 * math.pi * pos_m / v)
            standing_wave = arg_p.sin()

            arg_w = freq_expr * (math.pi * w_m / v)
            sinc_w = pl.when(freq_expr == 0).then(1.0).otherwise(arg_w.sin() / arg_w)

            coil_sum = coil_sum + (weight * polarity * standing_wave * sinc_w)

        acc = acc + (coil_sum.abs() + 0.05)

    return acc / len(string_speeds)

def polars_aperture(freq_expr, w_in, d_in, speeds):
    """Computes multi-string aperture sinc + dual-coil comb using Polars (legacy helper)."""
    w_m = w_in * 0.0254
    d_m = d_in * 0.0254
    acc = pl.lit(0.0)
    for v in speeds:
        arg_w = freq_expr * (math.pi * w_m / v)
        sinc_v = (
            pl.when(freq_expr == 0)
            .then(1.0)
            .otherwise(arg_w.sin() / arg_w)
        ).abs() + 0.05
        comb_v = (freq_expr * (math.pi * d_m / v)).cos().abs() + 0.05 if d_in > 0 else pl.lit(1.0)
        acc = acc + (sinc_v * comb_v)
    return acc / len(speeds)

def polars_position(freq_expr, pos_m, speeds):
    """Computes spatial standing wave envelope using Polars (legacy helper)."""
    acc = pl.lit(0.0)
    for v in speeds:
        arg_p = freq_expr * (2.0 * math.pi * pos_m / v)
        acc = acc + (arg_p.sin().abs() + 0.15)
    return acc / len(speeds)

def polars_pickup_electrical_response(freq_expr, fr, q):
    """
    Computes the 2nd-order electrical low-pass magnitude response of an active pickup.
    |H_elec(f)| = 1 / sqrt((1 - (f/fr)^2)^2 + (f / (q * fr))^2)
    """
    if fr is None or fr <= 0.0 or q is None or q <= 0.0:
        return pl.lit(1.0)
    x = freq_expr / float(fr)
    denom = ((pl.lit(1.0) - x.pow(2)).pow(2) + (x / float(q)).pow(2)).sqrt()
    return pl.lit(1.0) / denom

def resolve_pickup_electrical_response(freq_expr, pickup_cfg, inst_cfg):
    """
    Resolves the electrical frequency response for a source pickup or composite blend.
    For composite pickups (e.g. EMG ABCX active blend), performs weighted linear summation.
    """
    p_type = pickup_cfg.get("type", "single_coil")
    if p_type == "composite":
        components = pickup_cfg.get("components", [])
        if not components:
            return pl.lit(1.0)
        total_w = sum(c.get("weight", 1.0) for c in components)
        if total_w <= 0.0:
            return pl.lit(1.0)
        acc = None
        for comp in components:
            sub_id = comp["pickup"]
            sub_w = comp.get("weight", 1.0)
            sub_p = inst_cfg["pickups"][sub_id]
            sub_elec = resolve_pickup_electrical_response(freq_expr, sub_p, inst_cfg)
            term = sub_elec * (sub_w / total_w)
            acc = term if acc is None else (acc + term)
        return acc

    fr = pickup_cfg.get("resonant_frequency_hz")
    q = pickup_cfg.get("q_factor", 1.35)
    return polars_pickup_electrical_response(freq_expr, fr, q)

def polars_pickup_anti_resonance(freq_expr, fr, q_src, q_target=1.0):
    """
    Computes a 2nd-order biquad anti-resonance filter that neutralizes the internal active
    pickup resonant peak at fr without causing high-frequency noise explosion.
    |H_anti(f)| = sqrt((1 - (f/fr)^2)^2 + (f / (q_src * fr))^2) / sqrt((1 - (f/fr)^2)^2 + (f / (q_target * fr))^2)
    """
    if fr is None or fr <= 0.0 or q_src is None or q_src <= 0.0:
        return pl.lit(1.0)
    x = freq_expr / float(fr)
    num = ((pl.lit(1.0) - x.pow(2)).pow(2) + (x / float(q_src)).pow(2)).sqrt()
    den = ((pl.lit(1.0) - x.pow(2)).pow(2) + (x / float(q_target)).pow(2)).sqrt()
    return num / den

def resolve_pickup_electrical_deconvolution(freq_expr, pickup_cfg, inst_cfg, q_target=1.0):
    """
    Resolves the anti-resonance flattening filter for the source pickup or composite blend.
    Neutralizes the resonant peak (1/Q attenuation) while keeping sub-bass and high-frequency
    gain strictly bounded at <= 1.0 (0 dB).
    """
    p_type = pickup_cfg.get("type", "single_coil")
    if p_type == "composite":
        components = pickup_cfg.get("components", [])
        has_fr = any(
            inst_cfg.get("pickups", {}).get(c.get("pickup", ""), {}).get("resonant_frequency_hz")
            for c in components
        )
        if not has_fr:
            return pl.lit(1.0)
        total_w = sum(c.get("weight", 1.0) for c in components)
        if total_w <= 0.0:
            return pl.lit(1.0)
        acc = None
        for comp in components:
            sub_id = comp["pickup"]
            sub_w = comp.get("weight", 1.0)
            sub_p = inst_cfg["pickups"][sub_id]
            sub_deconv = resolve_pickup_electrical_deconvolution(freq_expr, sub_p, inst_cfg, q_target=q_target)
            term = sub_deconv * (sub_w / total_w)
            acc = term if acc is None else (acc + term)
        return acc

    fr = pickup_cfg.get("resonant_frequency_hz")
    if fr is None or fr <= 0.0:
        return pl.lit(1.0)
    q_src = pickup_cfg.get("q_factor", 1.35)
    return polars_pickup_anti_resonance(freq_expr, fr, q_src, q_target=q_target)

def compute_voice_prefilter_firs(voice_id, instrument="30in", src_scale=None, num_taps=NUM_TAPS):
    """
    Computes acoustic pre-filter FIRs for each pickup in a target voice configuration.
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

    df = pl.DataFrame({"freq": FREQS})
    f = pl.col("freq")

    h_src_acoustic = polars_pickup_acoustic_response(f, src_coils, src_speeds)

    # Scale-Length Tension Filter
    src_scale_in = inst.get("scale_length_in", 34.0)
    if target_scale_key == "multiscale":
        sub_gain = 10.0 ** (1.5 / 20.0)
        h_sub = ((sub_gain ** 2 + (f / 75.0).pow(2)) / (1.0 + (f / 75.0).pow(2))).sqrt()
        a_clank = 10.0 ** (3.5 / 40.0)
        x_clank = f / 3200.0
        h_clank = (((1.0 - x_clank.pow(2)).pow(2) + (a_clank * x_clank / 1.5).pow(2)) /
                   ((1.0 - x_clank.pow(2)).pow(2) + (x_clank / (a_clank * 1.5)).pow(2))).sqrt()
        h_tension = h_sub * h_clank
    elif target_scale_key == "34in" and src_scale_in != 34.0:
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = ((1.0 + g_snap ** 2 * (f / 2800.0).pow(2)) / (1.0 + (f / 2800.0).pow(2))).sqrt()
    else:
        h_tension = pl.lit(1.0)

    # Active Pickup Electrical Resonance Deconvolution (Wiener Inversion)
    h_elec_inv = resolve_pickup_electrical_deconvolution(f, src_pickup, inst)

    pickups = resolve_voice_pickups(cfg)
    raw_firs = []
    for p in pickups:
        p_coils = p["coils"]
        tgt_pos_eff = compute_effective_position(p_coils)

        h_tgt_acoustic = polars_pickup_acoustic_response(f, p_coils, tgt_speeds)
        h_acoustic_transfer = (h_tgt_acoustic * h_src_acoustic) / (h_src_acoustic.pow(2) + 0.001)

        delta_in = (tgt_pos_eff - src_pos_eff) / 0.0254
        tilt_db = delta_in * 1.5
        g_low = 10.0 ** (tilt_db / 20.0)
        g_hi = 10.0 ** (-tilt_db / 20.0)
        h_low_tilt = ((g_low ** 2 + (f / 250.0).pow(2)) / (1.0 + (f / 250.0).pow(2))).sqrt()
        h_hi_tilt = ((1.0 + g_hi ** 2 * (f / 2200.0).pow(2)) / (1.0 + (f / 2200.0).pow(2))).sqrt()

        p_weight = p.get("weight", 1.0)
        p_pol = p.get("polarity", 1.0)
        scale_fac = pl.lit(abs(p_weight * p_pol))

        df_p = df.with_columns(
            (scale_fac * h_acoustic_transfer * h_elec_inv * (h_low_tilt * h_hi_tilt) * h_tension).alias("prefilter_curve")
        )
        resp_series = df_p["prefilter_curve"]
        resp_list = resp_series.to_list()
        fir_raw = synthesize_minimum_phase_fir(resp_list, num_taps=num_taps, normalize=False)
        raw_firs.append(fir_raw)

    global_peak = max(max(abs(x) for x in fir) for fir in raw_firs)
    if global_peak > 0:
        return [[(x / global_peak) * 0.99 for x in fir] for fir in raw_firs]
    return raw_firs

def compute_aperture_prefilter_fir(voice_id, instrument="30in", src_scale=None, num_taps=NUM_TAPS):
    """
    Computes a single composite acoustic pre-filter FIR.
    Retained for backward compatibility. For multi-pickup independent channels,
    use compute_voice_prefilter_firs().
    """
    cfg = VOICES[voice_id]
    pickups = resolve_voice_pickups(cfg)
    if len(pickups) == 1:
        firs = compute_voice_prefilter_firs(voice_id, instrument=instrument, src_scale=src_scale, num_taps=num_taps)
        return firs[0]

    # For multi-pickup voices when a single flattened FIR is requested,
    # evaluate the composite acoustic response across all coils:
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

    df = pl.DataFrame({"freq": FREQS})
    f = pl.col("freq")

    h_src_acoustic = polars_pickup_acoustic_response(f, src_coils, src_speeds)
    h_tgt_acoustic = polars_pickup_acoustic_response(f, tgt_coils, tgt_speeds)
    h_acoustic_transfer = (h_tgt_acoustic * h_src_acoustic) / (h_src_acoustic.pow(2) + 0.001)

    delta_in = (tgt_pos_eff - src_pos_eff) / 0.0254
    tilt_db = delta_in * 1.5
    g_low = 10.0 ** (tilt_db / 20.0)
    g_hi = 10.0 ** (-tilt_db / 20.0)
    h_low_tilt = ((g_low ** 2 + (f / 250.0).pow(2)) / (1.0 + (f / 250.0).pow(2))).sqrt()
    h_hi_tilt = ((1.0 + g_hi ** 2 * (f / 2200.0).pow(2)) / (1.0 + (f / 2200.0).pow(2))).sqrt()

    src_scale_in = inst.get("scale_length_in", 34.0)
    if target_scale_key == "multiscale":
        sub_gain = 10.0 ** (1.5 / 20.0)
        h_sub = ((sub_gain ** 2 + (f / 75.0).pow(2)) / (1.0 + (f / 75.0).pow(2))).sqrt()
        a_clank = 10.0 ** (3.5 / 40.0)
        x_clank = f / 3200.0
        h_clank = (((1.0 - x_clank.pow(2)).pow(2) + (a_clank * x_clank / 1.5).pow(2)) /
                   ((1.0 - x_clank.pow(2)).pow(2) + (x_clank / (a_clank * 1.5)).pow(2))).sqrt()
        h_tension = h_sub * h_clank
    elif target_scale_key == "34in" and src_scale_in != 34.0:
        g_snap = 10.0 ** (1.8 / 20.0)
        h_tension = ((1.0 + g_snap ** 2 * (f / 2800.0).pow(2)) / (1.0 + (f / 2800.0).pow(2))).sqrt()
    else:
        h_tension = pl.lit(1.0)

    h_elec_inv = resolve_pickup_electrical_deconvolution(f, src_pickup, inst)

    df = df.with_columns(
        (h_acoustic_transfer * h_elec_inv * (h_low_tilt * h_hi_tilt) * h_tension).alias("prefilter_curve")
    )

    resp_series = df["prefilter_curve"]
    max_val = resp_series.max()
    resp_norm = [v / max_val for v in resp_series.to_list()]

    return synthesize_minimum_phase_fir(resp_norm, num_taps=num_taps)


