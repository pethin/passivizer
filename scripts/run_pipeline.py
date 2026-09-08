"""
Passivizer - Master Automation Pipeline Runner
Coordinates:
1. Linear IR Generation (48 kHz / 24-bit FIR) for all 10 voices + Dingwall Multi-scale
2. Interactive Frequency Visualization (Polars + Altair -> docs/frequency_responses.html)
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
IRS_DIR = REPO_ROOT / "irs"
DOCS_DIR = REPO_ROOT / "docs"
SCRIPTS_DIR = REPO_ROOT / "scripts"

DEFAULT_LTSPICE_BIN = "/Applications/LTspice.app/Contents/MacOS/LTspice"

def run_ir_generation(source_scale="30in"):
    """Generates all 48 kHz / 24-bit IRs using generate_irs.py."""
    print(f"\n[Stage 1] Generating linear minimum-phase IRs (Source: {source_scale})...")
    IRS_DIR.mkdir(parents=True, exist_ok=True)
    
    script = SCRIPTS_DIR / "generate_irs.py"
    cmd = [sys.executable, str(script), "--source-scale", source_scale]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Warning: IR generation returned non-zero code {res.returncode}")
    else:
        print(f"IR generation complete. Files written to {IRS_DIR}/")

def run_visualization():
    """Generates the interactive Altair visualization chart."""
    print("\n[Stage 2] Generating interactive Altair visualization...")
    script = SCRIPTS_DIR / "analyze_voices.py"
    cmd = [sys.executable, str(script)]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Warning: Visualization generation returned non-zero code {res.returncode}")
    else:
        print(f"Interactive chart generated at {DOCS_DIR / 'frequency_responses.html'}")

def run_spice_batch(ltspice_bin=DEFAULT_LTSPICE_BIN):
    """Executes headless batch simulation of all 10 SPICE netlists."""
    print("\n[Stage 3] Executing headless SPICE simulations...")
    if not os.path.exists(ltspice_bin):
        print(f"Notice: LTspice executable not found at '{ltspice_bin}'.")
        print("Skipping headless SPICE batch. To run, pass --ltspice-path /path/to/LTspice")
        return

    cir_files = sorted(CIRCUITS_DIR.glob("*.cir"))
    if not cir_files:
        print("No .cir netlists found in circuits/")
        return

    for cir in cir_files:
        print(f"  -> Simulating: {cir.name}...")
        cmd = [ltspice_bin, "-b", str(cir)]
        res = subprocess.run(cmd, cwd=str(CIRCUITS_DIR))
        if res.returncode != 0:
            print(f"     Warning: Simulation of {cir.name} exited with code {res.returncode}")

    print("Batch SPICE execution finished.")

def main():
    parser = argparse.ArgumentParser(description="Passivizer Master Pipeline Runner")
    parser.add_argument(
        "--source-scale",
        choices=["30in", "32in"],
        default="30in",
        help="Source instrument scale length (default: 30in for single EMG MM)"
    )
    parser.add_argument(
        "--stage",
        choices=["all", "irs", "viz", "spice"],
        default="all",
        help="Pipeline stage to execute (default: all)"
    )
    parser.add_argument(
        "--ltspice-path",
        default=DEFAULT_LTSPICE_BIN,
        help="Path to LTspice binary for headless simulation"
    )
    args = parser.parse_args()

    print("========================================")
    print("  PASSIVIZER AUTOMATION PIPELINE")
    print(f"  Source Scale: {args.source_scale}")
    print(f"  Stage:        {args.stage}")
    print("========================================")

    if args.stage in ["all", "irs"]:
        run_ir_generation(source_scale=args.source_scale)

    if args.stage in ["all", "viz"]:
        run_visualization()

    if args.stage in ["all", "spice"]:
        run_spice_batch(ltspice_bin=args.ltspice_path)

    print("\n[Pipeline Complete]")

if __name__ == "__main__":
    main()
