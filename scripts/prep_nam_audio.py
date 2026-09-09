"""
Passivizer - Scale-Length & Acoustic Aperture Pre-Filter for NAM Training
Pre-filters NAM calibration audio (e.g. T3K-sweep-v3.wav) through the physical
acoustic aperture, dual-coil spacing, placement delta, and scale tension filters.
The resulting audio is placed in audio/<instrument>/aperture_<voice>.wav to drive SPICE simulation.

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

from model_physics import VOICES, compute_voice_prefilter_firs, compute_aperture_prefilter_fir, write_wav_24bit, load_instrument
from simulate_circuits import prefilter_audio, AUDIO_DIR

def main():
    parser = argparse.ArgumentParser(description="Pre-filter NAM audio for SPICE simulation.")
    parser.add_argument("--input", default="T3K-sweep-v3.wav", help="Input NAM calibration audio (e.g. T3K-sweep-v3.wav)")
    parser.add_argument(
        "--instrument", "-i",
        default="30in",
        help="Source instrument configuration (ID, path to .toml, or alias like 30in, 32in)"
    )
    parser.add_argument("--voice", choices=VOICES.keys(), default="03_modern_p_ceramic", help="Target pickup voice")
    parser.add_argument("--out", help="Output WAV path (default: audio/<instrument>/aperture_<voice>.wav)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        for candidate in ["T3K-sweep-v3.wav", "v3_0_0.wav", "input.wav"]:
            if (REPO_ROOT / candidate).exists():
                input_path = REPO_ROOT / candidate
                break

    if not input_path.exists():
        print(f"Notice: Neither '{args.input}' nor any standard sweep file (T3K-sweep-v3.wav, v3_0_0.wav, input.wav) was found.")
        return

    inst_cfg = load_instrument(args.instrument) if not isinstance(args.instrument, dict) else args.instrument
    inst_id = inst_cfg.get("id", "30in_emg_mmtw")
    inst_audio_dir = AUDIO_DIR / inst_id
    inst_audio_dir.mkdir(parents=True, exist_ok=True)

    out_path = Path(args.out) if args.out else inst_audio_dir / f"aperture_{args.voice}.wav"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    firs = compute_voice_prefilter_firs(args.voice, instrument=args.instrument)
    ch_desc = f"{len(firs)} channels" if len(firs) > 1 else "1 channel"
    print(f"Synthesizing aperture & scale pre-filter ({ch_desc}) for {args.voice} (Source: {inst_id})...")
    prefilter_audio(input_path, out_path, firs)

if __name__ == "__main__":
    main()
