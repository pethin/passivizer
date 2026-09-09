"""
Passivizer - Native Apple Silicon Virtual Analog (VA) Circuit Simulation Engine

Provides a high-performance, exact analytical circuit solver that replaces
external SPICE dependencies (LTspice, ngspice). Directly parses .cir netlists,
evaluates closed-form nodal AC transfer functions, applies non-linear soft-knee
tanh compliance, and generates 24-bit 48 kHz audio digital twins in < 1 second.
"""

import argparse
import cmath
import math
import os
import re
import sys
import tempfile
import wave
from pathlib import Path
import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"
AUDIO_DIR = REPO_ROOT / "audio"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import (
    VOICES,
    FREQS,
    NUM_TAPS,
    synthesize_minimum_phase_fir,
    write_wav_24bit,
    compute_voice_prefilter_firs,
    load_instrument,
    get_instrument_string,
    get_source_pickup,
)

def parse_spice_val(val_str: str) -> float:
    """Parses standard SPICE engineering suffix notation (k, Meg, p, n, u, m, g)."""
    s = val_str.strip()
    if s.lower().endswith("meg"):
        return float(s[:-3]) * 1e6
    suffix_map = {
        "p": 1e-12,
        "n": 1e-9,
        "u": 1e-6,
        "m": 1e-3,
        "k": 1e3,
        "g": 1e9,
    }
    last_char = s[-1].lower()
    if last_char in suffix_map:
        return float(s[:-1]) * suffix_map[last_char]
    return float(s)

class CircuitModel:
    """Represents a parsed RLC guitar circuit digital twin."""
    def __init__(self):
        self.topology = "single"  # "single", "parallel", "series"
        self.vsat = 0.50
        self.vsat_n = 0.50
        self.vsat_b = 0.50

        # Branch parameters (single or neck)
        self.L = 4.8
        self.Rdc = 9500.0
        self.Reddy = 110000.0
        self.Ccoil = 80e-12

        # Bridge branch (for parallel or series)
        self.L_b = 3.6
        self.Rdc_b = 7800.0
        self.Reddy_b = 125000.0
        self.Ccoil_b = 70e-12

        # Optional tone / HPF
        self.Ctone = 0.0
        self.Rtone = 0.0
        self.Crick = 0.0

        # Volume pot & treble bleed (disabled by default unless specified in netlist)
        self.Rtop = 10.0
        self.Rbot = 500000.0
        self.Ctb = 0.0
        self.Rtb_par = 0.0
        self.Rtb_ser = 0.0

        # Active preamp buffer & EQ
        self.has_active_buffer = False
        self.preamp_type = "none"  # "sadowsky_2band", "stingray_2band", or "none"
        self.R_preamp_in = 1.0e6
        self.C_preamp_in = 25e-12
        self.R_out = 100.0

        # Cable & pedalboard load
        self.Ccable = 750e-12
        self.Ranagram = 1.0e6
        self.Canagram = 30e-12

def parse_netlist(cir_path: Path) -> CircuitModel:
    """Parses a Passivizer .cir netlist into a CircuitModel."""
    model = CircuitModel()
    with open(cir_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    has_neck = False
    has_bridge = False
    is_series = False

    # Check filename for known active configurations
    stem = cir_path.stem.lower()
    if "01_modern_jazz" in stem:
        model.has_active_buffer = True
        model.preamp_type = "sadowsky_2band"
    elif "08_stingray" in stem:
        model.has_active_buffer = True
        model.preamp_type = "stingray_2band"

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        line_lower = line_clean.lower()
        if "sadowsky_2band" in line_lower or "sadowsky" in line_lower:
            model.has_active_buffer = True
            model.preamp_type = "sadowsky_2band"
        elif "stingray_2band" in line_lower:
            model.has_active_buffer = True
            model.preamp_type = "stingray_2band"

        if line_clean.startswith("*") or line_clean.startswith("."):
            continue

        tokens = line_clean.split()
        tag = tokens[0].upper()

        # Behavioral soft-knee compliance
        if tag.startswith("B_COMP"):
            match = re.search(r"V\s*=\s*([0-9\.]+)\s*\*\s*tanh", line_clean, re.IGNORECASE)
            if match:
                v = float(match.group(1))
                if tag == "B_COMP_N":
                    model.vsat_n = v
                elif tag == "B_COMP_B":
                    model.vsat_b = v
                else:
                    model.vsat = v

        # Inductors
        elif tag in ["L_COIL", "L_NECK"]:
            model.L = parse_spice_val(tokens[3])
            if tag == "L_NECK":
                has_neck = True
                if tokens[2] == "node_mid":
                    is_series = True
        elif tag == "L_BRIDGE":
            model.L_b = parse_spice_val(tokens[3])
            has_bridge = True
            if tokens[1] in ["node_mid", "in_dyn_b"] and tokens[2] in ["node1_b"]:
                pass

        # DC Resistance
        elif tag in ["R_DC", "R_DC_N"]:
            model.Rdc = parse_spice_val(tokens[3])
        elif tag == "R_DC_B":
            model.Rdc_b = parse_spice_val(tokens[3])

        # Eddy Resistance
        elif tag in ["R_EDDY", "R_EDDY_N"]:
            model.Reddy = parse_spice_val(tokens[3])
        elif tag == "R_EDDY_B":
            model.Reddy_b = parse_spice_val(tokens[3])

        # Coil Self-Capacitance
        elif tag in ["C_COIL", "C_COIL_N"]:
            model.Ccoil = parse_spice_val(tokens[3])
        elif tag == "C_COIL_B":
            model.Ccoil_b = parse_spice_val(tokens[3])
            if tokens[2] == "node_mid":
                is_series = True

        # Tone / HPF
        elif tag == "C_TONE":
            model.Ctone = parse_spice_val(tokens[3])
        elif tag == "R_TONE":
            model.Rtone = parse_spice_val(tokens[3])
        elif tag == "C_RICK":
            model.Crick = parse_spice_val(tokens[3])

        # Volume Pot
        elif tag == "R_POT_TOP":
            model.Rtop = parse_spice_val(tokens[3])
        elif tag == "R_POT_BOT":
            model.Rbot = parse_spice_val(tokens[3])

        # Treble Bleed
        elif tag == "C_TB":
            model.Ctb = parse_spice_val(tokens[3])
        elif tag == "R_TB_PAR":
            model.Rtb_par = parse_spice_val(tokens[3])
        elif tag == "R_TB_SER":
            model.Rtb_ser = parse_spice_val(tokens[3])

        # Active Preamp Buffer
        elif tag in ["E_PREAMP", "E_BUF"]:
            model.has_active_buffer = True
        elif tag == "R_PREAMP_IN":
            model.R_preamp_in = parse_spice_val(tokens[3])
            model.has_active_buffer = True
        elif tag == "C_PREAMP_IN":
            model.C_preamp_in = parse_spice_val(tokens[3])
            model.has_active_buffer = True
        elif tag == "R_OUT":
            model.R_out = parse_spice_val(tokens[3])
            model.has_active_buffer = True

        # Cable
        elif tag == "C_CABLE":
            model.Ccable = parse_spice_val(tokens[3])

        # Anagram
        elif tag == "R_ANAGRAM":
            model.Ranagram = parse_spice_val(tokens[3])
        elif tag == "C_ANAGRAM":
            model.Canagram = parse_spice_val(tokens[3])

    if has_neck and has_bridge:
        model.topology = "series" if is_series else "parallel"
    else:
        model.topology = "single"

    return model

def compute_active_preamp_eq(preamp_type: str, s):
    """
    Evaluates analog active preamp contour transfer function:
    - Subsonic HPF: 10 Hz AC coupling pole
    - Sadowsky 2-band boost: +3.5 dB @ 40 Hz shelf, +3.5 dB @ 4 kHz shelf
    - StingRay 2-band boost: +1.8 dB @ 50 Hz shelf, +2.2 dB @ 4-7 kHz shelf
    """
    w_sub = 2.0 * math.pi * 10.0
    h_sub = s / (s + w_sub)

    if preamp_type == "sadowsky_2band":
        wb = 2.0 * math.pi * 60.0
        gb = 10.0 ** (3.5 / 20.0)
        h_bass = (s + gb * wb) / (s + wb)

        wt = 2.0 * math.pi * 3500.0
        gt = 10.0 ** (3.5 / 20.0)
        h_treble = (gt * s + wt) / (s + wt)

        return h_sub * h_bass * h_treble

    elif preamp_type == "stingray_2band":
        wb = 2.0 * math.pi * 80.0
        gb = 10.0 ** (1.8 / 20.0)
        h_bass = (s + gb * wb) / (s + wb)

        wt = 2.0 * math.pi * 4000.0
        gt = 10.0 ** (2.2 / 20.0)
        h_treble = (gt * s + wt) / (s + wt)

        return h_sub * h_bass * h_treble

    return 1.0 + 0j

def compute_circuit_transfer_functions(model: CircuitModel, freqs=FREQS):
    """
    Computes closed-form nodal AC transfer functions across frequencies.
    Returns a list of magnitude curves:
      - Single-pickup: [mag_curve] (length 1)
      - Dual-pickup (parallel or series): [mag_neck, mag_bridge] (length 2)
    Supports both passive high-Z harnesses and active buffered preamps.
    """
    if model.has_active_buffer:
        # Active Preamp Buffer: coils terminate into high-Z buffer, isolating them from cable capacitance.
        # Op-amp buffer drives cable and Anagram pedalboard load through low-Z output stage.
        if model.topology == "single":
            mag_curve = []
            for f in freqs:
                w = 2.0 * math.pi * 1e-3 if f == 0.0 else 2.0 * math.pi * f
                s = 1j * w

                # Output stage: low-Z buffer driving cable & Anagram load
                Z_cable_load = 1.0 / (1.0 / model.Ranagram + s * (model.Ccable + model.Canagram))
                H_buf_to_out = Z_cable_load / (model.R_out + Z_cable_load)

                # Preamp active contour
                H_eq = compute_active_preamp_eq(model.preamp_type, s)

                # Coils terminated into high-Z preamp input (R_preamp_in || C_preamp_in)
                Y_preamp_in = 1.0 / model.R_preamp_in + s * model.C_preamp_in
                if model.Ctone > 0:
                    Y_tone = (s * model.Ctone) / (1.0 + s * model.Rtone * model.Ctone) if model.Rtone > 0 else s * model.Ctone
                else:
                    Y_tone = 0.0
                Y_eff2 = Y_preamp_in + Y_tone

                Y_branch = 1.0 / (model.Rdc + s * model.L) + 1.0 / model.Reddy
                Y_shunt2 = s * model.Ccoil + Y_eff2
                H_dyn_to_2 = Y_branch / (Y_branch + Y_shunt2)

                H_total = H_dyn_to_2 * H_eq * H_buf_to_out
                mag_curve.append(abs(H_total))
            return [mag_curve]

        elif model.topology == "parallel":
            mag_n = []
            mag_b = []
            for f in freqs:
                w = 2.0 * math.pi * 1e-3 if f == 0.0 else 2.0 * math.pi * f
                s = 1j * w

                # Output stage: low-Z buffer driving cable & Anagram load
                Z_cable_load = 1.0 / (1.0 / model.Ranagram + s * (model.Ccable + model.Canagram))
                H_buf_to_out = Z_cable_load / (model.R_out + Z_cable_load)

                # Preamp active contour
                H_eq = compute_active_preamp_eq(model.preamp_type, s)

                # Coils terminated into high-Z preamp input
                Y_preamp_in = 1.0 / model.R_preamp_in + s * model.C_preamp_in
                if model.Ctone > 0:
                    Y_tone = (s * model.Ctone) / (1.0 + s * model.Rtone * model.Ctone) if model.Rtone > 0 else s * model.Ctone
                else:
                    Y_tone = 0.0
                Y_eff2 = Y_preamp_in + Y_tone

                Y_br_n = 1.0 / (model.Rdc + s * model.L) + 1.0 / model.Reddy
                Y_br_b = 1.0 / (model.Rdc_b + s * model.L_b) + 1.0 / model.Reddy_b
                Y_shunt2 = s * (model.Ccoil + model.Ccoil_b) + Y_eff2
                Y_total = Y_br_n + Y_br_b + Y_shunt2

                H_n_to_2 = Y_br_n / Y_total
                H_b_to_2 = Y_br_b / Y_total

                H_n = H_n_to_2 * H_eq * H_buf_to_out
                H_b = H_b_to_2 * H_eq * H_buf_to_out

                mag_n.append(abs(H_n))
                mag_b.append(abs(H_b))
            return [mag_n, mag_b]

    # Passive RLC Guitar Harness: Coils directly loaded by pots, cable capacitance, and Anagram load
    Rload = (model.Rbot * model.Ranagram) / (model.Rbot + model.Ranagram)
    Cload = model.Ccable + model.Canagram

    if model.topology == "single":
        mag_curve = []
        for f in freqs:
            if f == 0.0:
                # If there is a series blocking capacitor, DC gain is 0
                if model.Crick > 0:
                    mag_curve.append(0.0)
                    continue
                w = 2.0 * math.pi * 1e-3
            else:
                w = 2.0 * math.pi * f
            s = 1j * w

            # Branch admittance (L + Rdc || Reddy)
            Y_branch = 1.0 / (model.Rdc + s * model.L) + 1.0 / model.Reddy

            # Tone circuit admittance (series R-C branch to ground)
            if model.Ctone > 0:
                Y_tone = (s * model.Ctone) / (1.0 + s * model.Rtone * model.Ctone) if model.Rtone > 0 else s * model.Ctone
            else:
                Y_tone = 0.0

            Y_shunt2 = s * model.Ccoil + Y_tone

            # Treble bleed impedance (if configured)
            if model.Ctb > 0 and model.Rtb_par > 0:
                Z_tb = model.Rtb_ser + model.Rtb_par / (1.0 + s * model.Rtb_par * model.Ctb)
                Z23_pot = (model.Rtop * Z_tb) / (model.Rtop + Z_tb)
            else:
                Z23_pot = model.Rtop

            Z_rick = 1.0 / (s * model.Crick) if model.Crick > 0 else 0.0
            Z23 = Z_rick + Z23_pot

            Zload = 1.0 / (1.0 / Rload + s * Cload)

            Y_eff2 = Y_shunt2 + 1.0 / (Z23 + Zload)
            H_dyn_to_2 = Y_branch / (Y_branch + Y_eff2)
            H_2_to_3 = Zload / (Z23 + Zload)
            H_total = H_dyn_to_2 * H_2_to_3
            mag_curve.append(abs(H_total))
        return [mag_curve]

    elif model.topology == "parallel":
        mag_n = []
        mag_b = []
        for f in freqs:
            w = 2.0 * math.pi * f
            s = 1j * w

            Y_br_n = 1.0 / (model.Rdc + s * model.L) + 1.0 / model.Reddy
            Y_br_b = 1.0 / (model.Rdc_b + s * model.L_b) + 1.0 / model.Reddy_b

            # Tone circuit admittance (series R-C branch to ground)
            if model.Ctone > 0:
                Y_tone = (s * model.Ctone) / (1.0 + s * model.Rtone * model.Ctone) if model.Rtone > 0 else s * model.Ctone
            else:
                Y_tone = 0.0

            Y_shunt2 = s * (model.Ccoil + model.Ccoil_b) + Y_tone

            if model.Ctb > 0 and model.Rtb_par > 0:
                Z_tb = model.Rtb_ser + model.Rtb_par / (1.0 + s * model.Rtb_par * model.Ctb)
                Z23 = (model.Rtop * Z_tb) / (model.Rtop + Z_tb)
            else:
                Z23 = model.Rtop

            Zload = 1.0 / (1.0 / Rload + s * Cload)

            Y_eff2 = Y_shunt2 + 1.0 / (Z23 + Zload)
            Y_total = Y_br_n + Y_br_b + Y_eff2

            H_n_to_2 = Y_br_n / Y_total
            H_b_to_2 = Y_br_b / Y_total
            H_2_to_3 = Zload / (Z23 + Zload)

            mag_n.append(abs(H_n_to_2 * H_2_to_3))
            mag_b.append(abs(H_b_to_2 * H_2_to_3))
        return [mag_n, mag_b]

    elif model.topology == "series":
        mag_n = []
        mag_b = []
        for f in freqs:
            w = 2.0 * math.pi * f
            s = 1j * w

            Y_br_n = 1.0 / (model.Rdc + s * model.L) + 1.0 / model.Reddy
            Y_br_b = 1.0 / (model.Rdc_b + s * model.L_b) + 1.0 / model.Reddy_b
            Y_cn = s * model.Ccoil
            Y_cb = s * model.Ccoil_b
            Y_2b = Y_br_b + Y_cb

            # Tone circuit admittance (series R-C branch to ground)
            if model.Ctone > 0:
                Y_tone = (s * model.Ctone) / (1.0 + s * model.Rtone * model.Ctone) if model.Rtone > 0 else s * model.Ctone
            else:
                Y_tone = 0.0

            if model.Ctb > 0 and model.Rtb_par > 0:
                Z_tb = model.Rtb_ser + model.Rtb_par / (1.0 + s * model.Rtb_par * model.Ctb)
                Z23 = (model.Rtop * Z_tb) / (model.Rtop + Z_tb)
            else:
                Z23 = model.Rtop

            Zload = 1.0 / (1.0 / Rload + s * Cload)
            Y_out_load = 1.0 / (Z23 + Zload)

            Y_m = Y_br_n + Y_cn + Y_2b
            Y_2 = Y_2b + Y_out_load + Y_tone
            delta = Y_m * Y_2 - Y_2b ** 2

            T2_n = (Y_2b * Y_br_n) / delta
            T2_b = ((Y_br_n + Y_cn) * Y_br_b) / delta
            T_2_to_3 = Zload / (Z23 + Zload)

            mag_n.append(abs(T2_n * T_2_to_3))
            mag_b.append(abs(T2_b * T_2_to_3))
        return [mag_n, mag_b]

    raise ValueError(f"Unknown circuit topology: {model.topology}")

def compute_differential_circuit_transfer_functions(
    target_model: CircuitModel,
    source_model: CircuitModel,
    freqs=FREQS,
    max_boost_db: float = 6.0,
    eps: float = 0.05,
):
    """
    Computes regularized differential AC transfer functions for passive-to-passive modeling:
    |H_diff(s)| = (|H_target(s)| * |H_source(s)|) / (|H_source(s)|^2 + eps^2)
    with Wiener regularization and frequency-dependent high-frequency gain clamping (<= max_boost_db
    above 4.5 kHz) to prevent amplifying passive coil hum, Johnson noise, or cable hiss.
    """
    tgt_curves = compute_circuit_transfer_functions(target_model, freqs=freqs)
    src_curves = compute_circuit_transfer_functions(source_model, freqs=freqs)

    f_arr = np.asarray(freqs, dtype=np.float64)
    ref_idx = int(np.argmin(np.abs(f_arr - 1000.0)))

    diff_curves = []
    for ch_idx, tgt_c in enumerate(tgt_curves):
        src_c = src_curves[ch_idx] if len(src_curves) > ch_idx else src_curves[0]

        tgt_arr = np.asarray(tgt_c, dtype=np.float64)
        src_arr = np.asarray(src_c, dtype=np.float64)

        # Wiener regularized quotient
        h_diff = (tgt_arr * src_arr) / (src_arr ** 2 + eps ** 2)

        # Reference gain at 1 kHz (or DC)
        ref_gain = h_diff[ref_idx] if ref_idx < len(h_diff) else h_diff[0]
        if ref_gain <= 0:
            ref_gain = 1.0

        max_allowed = ref_gain * (10.0 ** (max_boost_db / 20.0))

        # Smooth clamp gain above 4.5 kHz
        hi_mask = f_arr >= 4500.0
        h_diff[hi_mask] = np.minimum(h_diff[hi_mask], max_allowed)

        diff_curves.append(h_diff.tolist())

    return diff_curves

def apply_prefilter_to_audio(audio: np.ndarray, sr: int, fir_samples) -> np.ndarray:
    """
    Applies the aperture and scale tension FIR(s) to audio in memory using vectorized FFT convolution.
    Returns an array of shape (n_channels, n_samples) scaled with 8 dB headroom (0.40 max).
    """
    is_multichannel = len(fir_samples) > 0 and isinstance(fir_samples[0], (list, tuple, np.ndarray))
    channels_firs = fir_samples if is_multichannel else [fir_samples]

    input_mono = audio[0] if audio.ndim > 1 and audio.shape[0] > 1 else (audio[0] if audio.ndim > 1 else audio)
    n_sig = len(input_mono)

    effected_channels = []
    for ch_fir in channels_firs:
        fir = np.asarray(ch_fir, dtype=np.float32)
        n_ir = len(fir)
        n_fft = 1 << (n_sig + n_ir - 1).bit_length()
        eff = np.fft.irfft(
            np.fft.rfft(input_mono, n_fft) * np.fft.rfft(fir, n_fft),
            n_fft
        )[:n_sig].astype(np.float32)
        effected_channels.append(eff)

    effected = np.array(effected_channels, dtype=np.float32)
    max_val = np.max(np.abs(effected))
    if max_val > 0:
        effected = (effected / max_val) * 0.40
    return effected

def prefilter_audio(input_wav_path: Path, output_wav_path: Path, fir_samples):
    """
    Applies aperture and scale tension FIR(s) to audio and writes a 24-bit 48 kHz WAV.
    Maintained for standalone export and backward compatibility.
    """
    from pedalboard.io import AudioFile

    with AudioFile(str(input_wav_path)) as f:
        audio = f.read(f.frames)
        sr = f.samplerate

    effected = apply_prefilter_to_audio(audio, sr, fir_samples)

    output_wav_path = Path(output_wav_path)
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)

    with AudioFile(str(output_wav_path), "w", samplerate=sr, num_channels=effected.shape[0], bit_depth=24) as out:
        out.write(effected)

    # Ensure standard canonical WAV headers (no JUNK chunks)
    with wave.open(str(output_wav_path), "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(wf.getnframes())
    with wave.open(str(output_wav_path), "wb") as wf:
        wf.setparams(params)
        wf.writeframes(frames)

def simulate_circuit_audio(
    input_audio,
    output_wav_path: Path,
    model: CircuitModel,
    prefilter_firs=None,
    save_intermediate: Path = None,
    circuit_curves=None,
    is_passive: bool = False,
):
    """
    Executes native Virtual Analog circuit simulation on audio.
    If prefilter_firs is provided, convolves input audio through acoustic aperture and
    scale-tension FIRs in memory first.
    For active instruments, applies soft-knee tanh compliance.
    For passive source instruments, bypasses forward saturation (to prevent double-compression)
    and applies regularized differential SPICE transfer functions (H_target / H_source).
    Writes canonical 24-bit 48 kHz mono audio.
    """
    from pedalboard.io import AudioFile

    if isinstance(input_audio, (str, Path)):
        with AudioFile(str(input_audio)) as f:
            audio = f.read(f.frames)
            sr = f.samplerate
    elif isinstance(input_audio, np.ndarray):
        audio = input_audio
        sr = 48000
    else:
        raise ValueError(f"Unsupported input_audio type: {type(input_audio)}")

    if prefilter_firs is not None:
        audio = apply_prefilter_to_audio(audio, sr, prefilter_firs)
        if save_intermediate:
            save_path = Path(save_intermediate)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with AudioFile(str(save_path), "w", samplerate=sr, num_channels=audio.shape[0], bit_depth=24) as out:
                out.write(audio)
            with wave.open(str(save_path), "rb") as wf:
                params = wf.getparams()
                frames = wf.readframes(wf.getnframes())
            with wave.open(str(save_path), "wb") as wf:
                wf.setparams(params)
                wf.writeframes(frames)

    if circuit_curves is not None:
        mag_curves = circuit_curves
    else:
        mag_curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    n_ch = len(mag_curves)

    channel_outputs = []
    n_samples = audio.shape[1] if audio.ndim > 1 else len(audio)

    for ch_idx, mag_curve in enumerate(mag_curves):
        if audio.ndim > 1:
            in_ch = audio[ch_idx] if audio.shape[0] > ch_idx else audio[0]
        else:
            in_ch = audio

        # Dynamic magnetic saturation: bypassed for passive sources (already physically saturated)
        if is_passive:
            in_dyn = in_ch.copy().astype(np.float32)
        else:
            if model.topology in ["parallel", "series"]:
                vsat = model.vsat_n if ch_idx == 0 else model.vsat_b
            else:
                vsat = model.vsat
            in_dyn = (vsat * np.tanh(in_ch / vsat)).astype(np.float32)

        # Synthesize minimum-phase causal impulse response
        fir = np.array(
            synthesize_minimum_phase_fir(mag_curve, num_taps=NUM_TAPS, normalize=False),
            dtype=np.float32
        )

        # High-speed FFT block convolution
        n_sig = len(in_dyn)
        n_ir = len(fir)
        n_fft = 1 << (n_sig + n_ir - 1).bit_length()

        out_ch = np.fft.irfft(
            np.fft.rfft(in_dyn, n_fft) * np.fft.rfft(fir, n_fft),
            n_fft
        )[:n_sig]
        channel_outputs.append(out_ch)

    # Sum all pickup contributions
    out_total = np.sum(channel_outputs, axis=0)

    # Prevent clipping outside 24-bit range
    max_val = np.max(np.abs(out_total))
    if max_val > 1.0:
        out_total = out_total / max_val

    output_wav_path = Path(output_wav_path)
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)

    # Write 24-bit 48 kHz mono PCM WAV
    with wave.open(str(output_wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(3)  # 24-bit
        wf.setframerate(sr)
        # Convert float32 [-1.0, 1.0] to 24-bit integers
        int24_max = 8388607.0
        scaled = np.clip(out_total * int24_max, -8388608.0, 8388607.0).astype(np.int32)
        # Pack into 3 bytes little-endian
        raw_bytes = bytearray(len(scaled) * 3)
        for i, val in enumerate(scaled):
            b = int(val).to_bytes(4, byteorder="little", signed=True)
            raw_bytes[i * 3: (i + 1) * 3] = b[:3]
        wf.writeframes(raw_bytes)

    return True

def find_default_input_audio() -> Path:
    """Finds raw calibration audio in the repository root."""
    for candidate in ["v1_1_1.wav", "T3K-sweep-v3.wav", "v3_0_0.wav", "input.wav"]:
        p = REPO_ROOT / candidate
        if p.exists():
            return p
    return None

def simulate_voice(
    voice_id: str,
    input_wav: Path = None,
    output_wav: Path = None,
    instrument: str = "30in",
    prefiltered: bool = False,
    cir_path: Path = None,
    save_intermediate = None,
):
    """
    Simulates a target voice digital twin using the native Virtual Analog engine.
    By default, applies acoustic aperture pre-filtering and circuit simulation
    end-to-end in memory from raw calibration audio.
    Outputs are saved by default to audio/{instrument_id}/out_{voice_id}.wav.
    """
    vcfg = VOICES.get(voice_id, {})
    if not cir_path:
        cir_rel = vcfg.get("circuit", f"circuits/{voice_id}.cir")
        cir_path = REPO_ROOT / cir_rel
        if not cir_path.exists():
            cir_path = CIRCUITS_DIR / f"{voice_id}.cir"

    if not cir_path.exists():
        raise FileNotFoundError(f"Circuit netlist '{cir_path}' not found.")

    inst_cfg = load_instrument(instrument) if not isinstance(instrument, dict) else instrument
    inst_id = inst_cfg.get("id", "30in_emg_mmtw")
    inst_audio_dir = AUDIO_DIR / inst_id
    inst_audio_dir.mkdir(parents=True, exist_ok=True)

    if not input_wav or not Path(input_wav).exists():
        found = find_default_input_audio()
        if found:
            input_wav = found
        elif (inst_audio_dir / f"aperture_{voice_id}.wav").exists():
            input_wav = inst_audio_dir / f"aperture_{voice_id}.wav"
            prefiltered = True
        elif (CIRCUITS_DIR / "v1_1_1_aperture.wav").exists():
            input_wav = CIRCUITS_DIR / "v1_1_1_aperture.wav"
            prefiltered = True
        else:
            raise FileNotFoundError(f"Input audio '{input_wav}' not found, and no standard calibration audio (T3K-sweep-v3.wav, v1_1_1.wav) was detected.")

    if not output_wav:
        output_wav = inst_audio_dir / f"out_{voice_id}.wav"
    else:
        output_wav = Path(output_wav)

    if save_intermediate is True:
        save_intermediate = inst_audio_dir / f"aperture_{voice_id}.wav"
    elif save_intermediate:
        save_intermediate = Path(save_intermediate)

    model = parse_netlist(cir_path)

    # Dynamic bridge compliance scaling based on source string pluck excursion
    if "upright_bridge_transducer" in voice_id:
        src_string = get_instrument_string(inst_cfg)
        excursion = float(src_string.get("pluck_excursion_factor", 1.0))
        if excursion > 0:
            model.vsat = round(model.vsat / excursion, 3)

    is_passive = (inst_cfg.get("electronics") == "passive")
    diff_curves = None
    if is_passive:
        src_pickup = get_source_pickup(inst_cfg, voice_id)
        src_cir_rel = src_pickup.get("circuit", "circuits/sources/source_standard_p.cir")
        src_cir_path = REPO_ROOT / src_cir_rel
        if src_cir_path.exists():
            src_model = parse_netlist(src_cir_path)
            diff_curves = compute_differential_circuit_transfer_functions(model, src_model, freqs=FREQS)

    prefilter_firs = None
    if not prefiltered:
        prefilter_firs = compute_voice_prefilter_firs(voice_id, instrument=instrument)
        if is_passive:
            stage_desc = "Acoustic Aperture + Differential Circuit Simulation (Passive Source)"
        else:
            stage_desc = "Acoustic Aperture + Circuit Simulation"
    else:
        stage_desc = "Circuit Simulation (Pre-filtered Input)"

    print(f"  -> Simulating Native VA ({stage_desc}): {cir_path.name} (Topology: {model.topology}, Source: {inst_id})...")
    simulate_circuit_audio(
        input_wav,
        output_wav,
        model,
        prefilter_firs=prefilter_firs,
        save_intermediate=save_intermediate,
        circuit_curves=diff_curves,
        is_passive=is_passive,
    )
    print(f"     Exported: {output_wav}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Passivizer Native Virtual Analog Circuit Simulator.")
    parser.add_argument("--voice", "-v", default="04_modern_p_ceramic", help="Target voice to simulate (or 'all')")
    parser.add_argument(
        "--instrument", "-i",
        default="30in",
        help="Source instrument configuration (30in, 32in, or path to .toml)"
    )
    parser.add_argument("--input", help="Input WAV path (defaults to auto-detecting v1_1_1.wav)")
    parser.add_argument("--out", help="Output WAV path (default: audio/<instrument>/out_<voice>.wav)")
    parser.add_argument("--prefiltered", action="store_true", help="Input is already pre-filtered through acoustic aperture")
    parser.add_argument("--save-intermediate", action="store_true", help="Export intermediate pre-filtered audio to audio/<instrument>/aperture_<voice>.wav")
    args = parser.parse_args()

    voices = list(VOICES.keys()) if args.voice == "all" else [args.voice]
    for v in voices:
        in_path = Path(args.input) if args.input else None
        out_path = Path(args.out) if args.out else None
        simulate_voice(
            v,
            input_wav=in_path,
            output_wav=out_path,
            instrument=args.instrument,
            prefiltered=args.prefiltered,
            save_intermediate=args.save_intermediate,
        )

if __name__ == "__main__":
    main()
