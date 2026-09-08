"""
Passivizer - Scale-Length & Acoustic Aperture Pre-Filter for NAM Training
Pre-filters NAM calibration audio (e.g. v1_1_1.wav) through the physical
acoustic aperture, dual-coil spacing, placement delta, and scale tension filters.
The resulting audio is placed in circuits/v1_1_1_aperture.wav to drive SPICE simulation.

Uses Spotify's Pedalboard library for SIMD-accelerated C++ convolution and 24-bit audio I/O.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import VOICES, compute_voice_prefilter_firs, compute_aperture_prefilter_fir, write_wav_24bit

def prefilter_audio(input_wav_path, output_wav_path, fir_samples):
    """
    Applies the aperture and scale tension FIR(s) to NAM calibration audio
    using Spotify's Pedalboard SIMD convolution engine in under 200ms.
    Supports single mono FIR (1D list of floats) or multi-channel FIRs
    (list of lists of floats, e.g. stereo for dual-pickup voices).
    """
    try:
        from pedalboard import Pedalboard, Convolution
        from pedalboard.io import AudioFile
        import numpy as np
    except ImportError:
        print("Error: 'pedalboard' is required for audio pre-filtering.")
        print("Install it with: uv add pedalboard")
        sys.exit(1)

    is_multichannel = len(fir_samples) > 0 and isinstance(fir_samples[0], (list, tuple))
    channels_firs = fir_samples if is_multichannel else [fir_samples]

    with tempfile.TemporaryDirectory() as tmpdir:
        with AudioFile(str(input_wav_path)) as f:
            audio = f.read(f.frames)
            sr = f.samplerate

        # If audio has multiple channels, take first channel as excitation
        input_mono = audio[0:1, :] if audio.shape[0] > 1 else audio

        effected_channels = []
        for idx, ch_fir in enumerate(channels_firs):
            tmp_fir_path = os.path.join(tmpdir, f"fir_ch{idx}.wav")
            write_wav_24bit(tmp_fir_path, ch_fir, sample_rate=48000)
            board = Pedalboard([Convolution(tmp_fir_path)])
            eff = board(input_mono, sr)
            effected_channels.append(eff[0])

        effected = np.array(effected_channels, dtype=np.float32)

        max_val = np.max(np.abs(effected))
        if max_val > 0:
            # Leave 8 dB headroom (scale to 0.40) so SPICE RLC resonant peaks (+6 to +8 dB) do not clip 1.0V
            effected = (effected / max_val) * 0.40

        with AudioFile(str(output_wav_path), "w", samplerate=sr, num_channels=effected.shape[0], bit_depth=24) as out:
            out.write(effected)

        # Re-save with standard wave module to ensure canonical RIFF/WAVE header (no JUNK chunk) for LTspice
        import wave
        with wave.open(str(output_wav_path), "rb") as wf:
            params = wf.getparams()
            frames = wf.readframes(wf.getnframes())
        with wave.open(str(output_wav_path), "wb") as wf:
            wf.setparams(params)
            wf.writeframes(frames)

    num_ch = len(channels_firs)
    ch_label = f"{num_ch}-channel stereo" if num_ch == 2 else f"{num_ch}-channel mono"
    print(f"Pre-filtered {ch_label} audio written to: {output_wav_path}")

def main():
    parser = argparse.ArgumentParser(description="Pre-filter NAM audio for SPICE simulation.")
    parser.add_argument("--input", default="v1_1_1.wav", help="Input NAM calibration audio (e.g. v1_1_1.wav)")
    parser.add_argument(
        "--instrument", "-i",
        default="30in",
        help="Source instrument configuration (ID, path to .toml, or alias like 30in, 32in)"
    )
    parser.add_argument(
        "--source-scale",
        dest="instrument",
        help="Legacy alias for --instrument (e.g. 30in, 32in)"
    )
    parser.add_argument("--voice", choices=VOICES.keys(), default="03_modern_p_ceramic", help="Target pickup voice")
    parser.add_argument("--out", help="Output WAV path (default: circuits/v1_1_1_aperture.wav)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        for candidate in ["T3K-sweep-v3.wav", "v1_1_1.wav", "v3_0_0.wav", "input.wav"]:
            if (REPO_ROOT / candidate).exists():
                input_path = REPO_ROOT / candidate
                break

    if not input_path.exists():
        print(f"Notice: Neither '{args.input}' nor any standard sweep file (T3K-sweep-v3.wav, v1_1_1.wav) was found.")
        return

    out_path = Path(args.out) if args.out else CIRCUITS_DIR / "v1_1_1_aperture.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    firs = compute_voice_prefilter_firs(args.voice, instrument=args.instrument)
    ch_desc = f"{len(firs)} channels" if len(firs) > 1 else "1 channel"
    print(f"Synthesizing aperture & scale pre-filter ({ch_desc}) for {args.voice} (Source: {args.instrument})...")
    prefilter_audio(input_path, out_path, firs)

if __name__ == "__main__":
    main()
