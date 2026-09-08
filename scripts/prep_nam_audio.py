"""
Passivizer - Scale-Length & Multi-Scale Audio Pre-Filter for NAM Training
Converts audio recorded on 30" (short) or 32" (medium) scale basses to sound
like authentic 34" standard or 34"-37" multi-scale (Dingwall-style) instruments.

Uses Spotify's Pedalboard library for SIMD-accelerated C++ convolution and 24-bit audio I/O.
"""

import argparse
import os
import sys
from pathlib import Path

# Add scripts directory to path to reuse generate_irs engine
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_irs import VOICES, generate_voice_ir

def process_audio(input_wav_path, output_wav_path, ir_wav_path):
    """
    Applies the Passivizer IR to the NAM calibration audio using Spotify's Pedalboard.
    Executes in under 200ms using JUCE SIMD-accelerated partitioned convolution.
    """
    try:
        from pedalboard import Pedalboard, Convolution
        from pedalboard.io import AudioFile
        import numpy as np
    except ImportError:
        print("Error: 'pedalboard' is required for NAM audio processing.")
        print("Install it with: uv add pedalboard")
        sys.exit(1)

    with AudioFile(input_wav_path) as f:
        audio = f.read(f.frames)
        sr = f.samplerate

    board = Pedalboard([Convolution(ir_wav_path)])
    effected = board(audio, sr)

    # Peak normalize to -0.1 dBFS
    max_val = np.max(np.abs(effected))
    if max_val > 0:
        effected = (effected / max_val) * 0.99

    with AudioFile(output_wav_path, "w", samplerate=sr, num_channels=effected.shape[0], bit_depth=24) as out:
        out.write(effected)
    print(f"Exported [NAM Pre-filtered]: {output_wav_path}")

def main():
    parser = argparse.ArgumentParser(description="Pre-filter NAM audio using Spotify Pedalboard.")
    parser.add_argument("--input", default="v1_1_1.wav", help="Input NAM calibration audio (e.g. v1_1_1.wav)")
    parser.add_argument("--source-scale", choices=["30in", "32in"], default="30in", help="Physical source bass scale")
    parser.add_argument("--target-scale", choices=["34in", "multiscale"], default="34in", help="Target tonal scale")
    parser.add_argument("--voice", choices=VOICES.keys(), help="Specific voice to process")
    parser.add_argument("--irs-dir", default="irs", help="Directory storing Passivizer IRs")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Notice: '{args.input}' not found. Place the official 3-minute NAM calibration file here to render.")
        return

    os.makedirs(args.irs_dir, exist_ok=True)

    voices_to_process = [args.voice] if args.voice else list(VOICES.keys())

    for voice_id in voices_to_process:
        cfg = VOICES[voice_id]
        tgt_s = cfg.get("scale", args.target_scale)
        ir_name = f"{voice_id}_{args.source_scale}_to_{tgt_s}.wav"
        ir_path = os.path.join(args.irs_dir, ir_name)

        # Ensure IR exists; generate on-the-fly if missing
        if not os.path.exists(ir_path):
            print(f"Generating missing IR for {voice_id}...")
            generate_voice_ir(voice_id, cfg, src_scale=args.source_scale, out_dir=args.irs_dir)

        out_name = f"v1_1_1_{voice_id}_{args.source_scale}_to_{tgt_s}.wav"
        process_audio(args.input, out_name, ir_path)

if __name__ == "__main__":
    main()
