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

from model_physics import VOICES, compute_aperture_prefilter_fir, write_wav_24bit

def prefilter_audio(input_wav_path, output_wav_path, fir_samples):
    """
    Applies the aperture and scale tension FIR to NAM calibration audio
    using Spotify's Pedalboard SIMD convolution engine in under 200ms.
    """
    try:
        from pedalboard import Pedalboard, Convolution
        from pedalboard.io import AudioFile
        import numpy as np
    except ImportError:
        print("Error: 'pedalboard' is required for audio pre-filtering.")
        print("Install it with: uv add pedalboard")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_fir_path = os.path.join(tmpdir, "fir.wav")
        write_wav_24bit(tmp_fir_path, fir_samples, sample_rate=48000)

        with AudioFile(str(input_wav_path)) as f:
            audio = f.read(f.frames)
            sr = f.samplerate

        board = Pedalboard([Convolution(tmp_fir_path)])
        effected = board(audio, sr)

        max_val = np.max(np.abs(effected))
        if max_val > 0:
            effected = (effected / max_val) * 0.99

        with AudioFile(str(output_wav_path), "w", samplerate=sr, num_channels=effected.shape[0], bit_depth=24) as out:
            out.write(effected)

    print(f"Pre-filtered audio written to: {output_wav_path}")

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
        print(f"Notice: '{args.input}' not found. Place the official 3-minute NAM calibration file here to render.")
        return

    out_path = Path(args.out) if args.out else CIRCUITS_DIR / "v1_1_1_aperture.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Synthesizing aperture & scale pre-filter for {args.voice} (Source: {args.instrument})...")
    fir_samples = compute_aperture_prefilter_fir(args.voice, instrument=args.instrument)
    prefilter_audio(input_path, out_path, fir_samples)

if __name__ == "__main__":
    main()
