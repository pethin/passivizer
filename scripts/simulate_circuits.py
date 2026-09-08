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

        # Optional tone / HPF caps
        self.Ctone = 0.0
        self.Crick = 0.0

        # Volume pot & treble bleed
        self.Rtop = 10.0
        self.Rbot = 500000.0
        self.Ctb = 1.0e-9
        self.Rtb_par = 150000.0
        self.Rtb_ser = 20000.0

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

    for line in lines:
        line = line.strip()
        if not line or line.startswith("*") or line.startswith("."):
            continue

        tokens = line.split()
        tag = tokens[0].upper()

        # Behavioral soft-knee compliance
        if tag.startswith("B_COMP"):
            match = re.search(r"V\s*=\s*([0-9\.]+)\s*\*\s*tanh", line, re.IGNORECASE)
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

def compute_circuit_transfer_functions(model: CircuitModel, freqs=FREQS):
    """
    Computes closed-form nodal AC transfer functions across frequencies.
    Returns a list of magnitude curves:
      - Single-pickup: [mag_curve] (length 1)
      - Dual-pickup (parallel or series): [mag_neck, mag_bridge] (length 2)
    """
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
            Y_shunt2 = s * model.Ccoil + (s * model.Ctone if model.Ctone > 0 else 0.0)

            # Treble bleed impedance
            Z_tb = model.Rtb_ser + model.Rtb_par / (1.0 + s * model.Rtb_par * model.Ctb)
            Z23_pot = (model.Rtop * Z_tb) / (model.Rtop + Z_tb)
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
            Y_shunt2 = s * (model.Ccoil + model.Ccoil_b)

            Z_tb = model.Rtb_ser + model.Rtb_par / (1.0 + s * model.Rtb_par * model.Ctb)
            Z23 = (model.Rtop * Z_tb) / (model.Rtop + Z_tb)
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

            Z_tb = model.Rtb_ser + model.Rtb_par / (1.0 + s * model.Rtb_par * model.Ctb)
            Z23 = (model.Rtop * Z_tb) / (model.Rtop + Z_tb)
            Zload = 1.0 / (1.0 / Rload + s * Cload)
            Y_out_load = 1.0 / (Z23 + Zload)

            Y_m = Y_br_n + Y_cn + Y_2b
            Y_2 = Y_2b + Y_out_load
            delta = Y_m * Y_2 - Y_2b ** 2

            T2_n = (Y_2b * Y_br_n) / delta
            T2_b = ((Y_br_n + Y_cn) * Y_br_b) / delta
            T_2_to_3 = Zload / (Z23 + Zload)

            mag_n.append(abs(T2_n * T_2_to_3))
            mag_b.append(abs(T2_b * T_2_to_3))
        return [mag_n, mag_b]

    raise ValueError(f"Unknown circuit topology: {model.topology}")

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
):
    """
    Executes native Virtual Analog circuit simulation on audio.
    If prefilter_firs is provided, convolves input audio through acoustic aperture and
    scale-tension FIRs in memory first.
    Applies soft-knee tanh compliance, convolves with exact circuit transfer function,
    and writes canonical 24-bit 48 kHz mono audio.
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

    mag_curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    n_ch = len(mag_curves)

    channel_outputs = []
    n_samples = audio.shape[1] if audio.ndim > 1 else len(audio)

    for ch_idx, mag_curve in enumerate(mag_curves):
        if audio.ndim > 1:
            in_ch = audio[ch_idx] if audio.shape[0] > ch_idx else audio[0]
        else:
            in_ch = audio

        # Resolve soft-knee saturation threshold
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

    prefilter_firs = None
    if not prefiltered:
        prefilter_firs = compute_voice_prefilter_firs(voice_id, instrument=instrument)
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
    )
    print(f"     Exported: {output_wav}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Passivizer Native Virtual Analog Circuit Simulator.")
    parser.add_argument("--voice", "-v", default="03_modern_p_ceramic", help="Target voice to simulate (or 'all')")
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
