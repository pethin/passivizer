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
from simulate_circuits import prefilter_audio

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
