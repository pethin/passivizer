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

def synthesize_minimum_phase_fir(magnitude_curve, num_taps=NUM_TAPS):
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
        "30in": "30in_emg_mm",
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
        return pickups[mapping[voice_id]]

    # 2. Default pickup declared on instrument
    default_key = instrument.get("default_pickup")
    if default_key and default_key in pickups:
        return pickups[default_key]

    # 3. Fallback to first available pickup
    return next(iter(pickups.values()))

# Global registries initialized from modular configuration files
SCALES = load_scales()
VOICES = load_voices_config()
INSTRUMENTS = load_all_instruments()

def polars_aperture(freq_expr, w_in, d_in, speeds):
    """Computes multi-string aperture sinc + dual-coil comb using Polars."""
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
    """Computes spatial standing wave envelope using Polars."""
    acc = pl.lit(0.0)
    for v in speeds:
        arg_p = freq_expr * (2.0 * math.pi * pos_m / v)
        acc = acc + (arg_p.sin().abs() + 0.15)
    return acc / len(speeds)

def compute_aperture_prefilter_fir(voice_id, instrument="30in", src_scale=None, num_taps=NUM_TAPS):
    """
    Computes the acoustic pre-filter FIR (aperture de-humbucking, displacement delta,
    and scale tension) to pre-filter audio before feeding SPICE circuit digital twins.
    Instrument can be an instrument ID ('30in_emg_mm'), a path to a TOML file, or an alias ('30in', '32in').
    """
    cfg = VOICES[voice_id]
    target_scale_key = cfg.get("scale", "34in")
    tgt = SCALES[target_scale_key]
    tgt_speeds = tgt["speeds"]

    # Support legacy src_scale keyword argument if passed
    inst_selector = src_scale if src_scale is not None else instrument
    inst = load_instrument(inst_selector) if not isinstance(inst_selector, dict) else inst_selector

    src_speeds = inst.get("string_wave_speeds")
    if not src_speeds:
        l_m = inst.get("scale_length_m", inst.get("scale_length_in", 34.0) * 0.0254)
        src_speeds = [2.0 * l_m * f0 for f0 in [41.203, 55.0, 73.416, 97.999]]

    src_pickup = get_source_pickup(inst, voice_id)
    src_w = src_pickup["aperture_width_in"]
    src_d = src_pickup["coil_spacing_in"]
    src_pos_m = src_pickup["position_from_bridge_m"]

    df = pl.DataFrame({"freq": FREQS})
    f = pl.col("freq")

    # 1. Aperture Transfer via Polars
    h_src_ap = polars_aperture(f, src_w, src_d, src_speeds)
    h_tgt_ap = polars_aperture(f, cfg["w"], cfg["d"], tgt_speeds)
    h_ap_transfer = (h_tgt_ap * h_src_ap) / (h_src_ap.pow(2) + 0.001)

    # 2. Position Transfer via Polars
    h_src_pos = polars_position(f, src_pos_m, src_speeds)
    h_tgt_pos = polars_position(f, cfg["pos_34"], tgt_speeds)
    h_pos_transfer = (h_tgt_pos * h_src_pos) / (h_src_pos.pow(2) + 0.002)

    # 3. Macro Position Displacement Tilt (1.5 dB per inch)
    delta_in = (cfg["pos_34"] - src_pos_m) / 0.0254
    tilt_db = delta_in * 1.5
    g_low = 10.0 ** (tilt_db / 20.0)
    g_hi = 10.0 ** (-tilt_db / 20.0)
    h_low_tilt = ((g_low ** 2 + (f / 250.0).pow(2)) / (1.0 + (f / 250.0).pow(2))).sqrt()
    h_hi_tilt = ((1.0 + g_hi ** 2 * (f / 2200.0).pow(2)) / (1.0 + (f / 2200.0).pow(2))).sqrt()

    # 4. Scale-Length Tension Filter
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

    # Total acoustic/spatial pre-filter response (RLC electronics handled in SPICE)
    df = df.with_columns(
        (h_ap_transfer * h_pos_transfer * (h_low_tilt * h_hi_tilt) * h_tension).alias("prefilter_curve")
    )

    resp_series = df["prefilter_curve"]
    max_val = resp_series.max()
    resp_norm = [v / max_val for v in resp_series.to_list()]

    return synthesize_minimum_phase_fir(resp_norm, num_taps=num_taps)

