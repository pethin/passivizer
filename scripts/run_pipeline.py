"""
Passivizer - Master Automation Pipeline Runner (SPICE -> NAM)
Coordinates:
1. Interactive Frequency Visualization (Polars + Altair -> docs/frequency_responses.html)
2. Acoustic Pre-Filtering (prep_nam_audio.py: aperture, placement, and scale tension)
3. Headless SPICE Circuit Twin Simulation (LTspice batch mode)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"
DOCS_DIR = REPO_ROOT / "docs"
MODELS_DIR = REPO_ROOT / "models"
SCRIPTS_DIR = REPO_ROOT / "scripts"

DEFAULT_LTSPICE_BIN = "/Applications/LTspice.app/Contents/MacOS/LTspice"

def run_visualization(source_scale="30in"):
    """Generates the interactive Altair visualization chart."""
    print(f"\n[Stage 1] Generating interactive Altair visualization (Source: {source_scale})...")
    script = SCRIPTS_DIR / "analyze_voices.py"
    cmd = [sys.executable, str(script), "--source-scale", source_scale]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Warning: Visualization generation returned non-zero code {res.returncode}")
    else:
        print(f"Interactive chart generated at {DOCS_DIR / 'frequency_responses.html'}")

def run_prep_audio(input_wav="v1_1_1.wav", source_scale="30in", voice="03_modern_p_ceramic"):
    """Pre-filters NAM calibration audio through acoustic and spatial transfer functions."""
    print(f"\n[Stage 2] Pre-filtering audio for {voice} (Source: {source_scale})...")
    script = SCRIPTS_DIR / "prep_nam_audio.py"
    cmd = [
        sys.executable, str(script),
        "--input", input_wav,
        "--source-scale", source_scale,
        "--voice", voice
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Notice: Pre-filtering returned code {res.returncode}")

def run_spice_batch(ltspice_bin=DEFAULT_LTSPICE_BIN):
    """Executes headless batch simulation of all SPICE netlists."""
    print("\n[Stage 3] Executing headless SPICE simulations...")
    if not os.path.exists(ltspice_bin):
        print(f"Notice: LTspice executable not found at '{ltspice_bin}'.")
        print("Skipping headless SPICE batch. To run, pass --ltspice-path /path/to/LTspice")
        return

    cir_files = sorted(CIRCUITS_DIR.glob("*.cir"))
    if not cir_files:
        print("No .cir netlists found in circuits/")
        return

    # Check if input wavefile exists in circuits directory to avoid headless modal dialog hang
    input_wav = CIRCUITS_DIR / "v1_1_1_aperture.wav"
    if not input_wav.exists():
        print(f"Notice: Audio source '{input_wav.name}' not found in circuits/.")
        print("Skipping SPICE transient simulation. Pre-filter audio with prep_nam_audio.py first.")
        return

    for cir in cir_files:
        print(f"  -> Simulating: {cir.name}...")
        cmd = [ltspice_bin, "-b", str(cir)]
        try:
            res = subprocess.run(cmd, cwd=str(CIRCUITS_DIR), timeout=300)
            if res.returncode != 0:
                print(f"     Warning: Simulation of {cir.name} exited with code {res.returncode}")
        except subprocess.TimeoutExpired:
            print(f"     Warning: Simulation of {cir.name} timed out after 300s")

    print("Batch SPICE execution finished.")

def main():
    parser = argparse.ArgumentParser(description="Passivizer SPICE -> NAM Automation Pipeline")
    parser.add_argument(
        "--source-scale",
        choices=["30in", "32in"],
        default="30in",
        help="Source instrument scale length (default: 30in for single EMG MM)"
    )
    parser.add_argument(
        "--stage",
        choices=["all", "viz", "prep", "spice"],
        default="all",
        help="Pipeline stage to execute (default: all)"
    )
    parser.add_argument(
        "--voice",
        default="03_modern_p_ceramic",
        help="Target pickup voice for audio pre-filtering"
    )
    parser.add_argument(
        "--input-wav",
        default="v1_1_1.wav",
        help="Path to NAM calibration audio file"
    )
    parser.add_argument(
        "--ltspice-path",
        default=DEFAULT_LTSPICE_BIN,
        help="Path to LTspice binary for headless simulation"
    )
    args = parser.parse_args()

    print("========================================")
    print("  PASSIVIZER SPICE -> NAM PIPELINE")
    print(f"  Source Scale: {args.source_scale}")
    print(f"  Stage:        {args.stage}")
    print("========================================")

    if args.stage in ["all", "viz"]:
        run_visualization(source_scale=args.source_scale)

    if args.stage in ["all", "prep"]:
        run_prep_audio(input_wav=args.input_wav, source_scale=args.source_scale, voice=args.voice)

    if args.stage in ["all", "spice"]:
        run_spice_batch(ltspice_bin=args.ltspice_path)

    print("\n[Pipeline Complete]")

if __name__ == "__main__":
    main()
