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
AUDIO_DIR = REPO_ROOT / "audio"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import INSTRUMENTS, VOICES, resolve_voices, resolve_voice_coils, resolve_voice_pickups, compute_effective_position
from simulate_circuits import simulate_voice

DEFAULT_LTSPICE_BIN = "/Applications/LTspice.app/Contents/MacOS/LTspice"

def run_visualization(instrument="30in"):
    """Generates the interactive Altair visualization charts and master portal."""
    print(f"\n[Stage 1] Generating interactive Altair visualization (Instrument: {instrument})...")
    script = SCRIPTS_DIR / "analyze_voices.py"
    cmd = [sys.executable, str(script), "--instrument", instrument]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Warning: Visualization generation returned non-zero code {res.returncode}")
    else:
        resp_dir = DOCS_DIR / "frequency_responses"
        print(f"Interactive charts generated in {resp_dir}/")
        print(f"Master interactive portal updated at {DOCS_DIR / 'frequency_responses.html'}")

def run_prep_audio(input_wav=None, instrument="30in", voice="03_modern_p_ceramic"):
    """Pre-filters NAM calibration audio through acoustic and spatial transfer functions."""
    if not input_wav or not (REPO_ROOT / input_wav).exists():
        for candidate in ["T3K-sweep-v3.wav", "v3_0_0.wav", "v1_1_1.wav", "input.wav"]:
            if (REPO_ROOT / candidate).exists():
                input_wav = candidate
                break

    print(f"\n[Prep Audio] Pre-filtering for {voice} (Instrument: {instrument}, Input: {input_wav})...")
    script = SCRIPTS_DIR / "prep_nam_audio.py"
    cmd = [
        sys.executable, str(script),
        "--input", input_wav,
        "--instrument", instrument,
        "--voice", voice
    ]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Notice: Pre-filtering returned code {res.returncode}")

def run_circuit_simulation(voice, instrument="30in", input_wav=None, backend="native", ltspice_bin=DEFAULT_LTSPICE_BIN):
    """Executes circuit simulation for a single target voice netlist."""
    if backend == "native":
        try:
            return simulate_voice(voice, input_wav=input_wav, instrument=instrument, prefiltered=False)
        except Exception as e:
            print(f"Error during native circuit simulation: {e}")
            return False

    # LTspice backend requires intermediate aperture audio on disk
    run_prep_audio(input_wav=input_wav, instrument=instrument, voice=voice)
    if not os.path.exists(ltspice_bin):
        print(f"Notice: LTspice executable not found at '{ltspice_bin}'. Falling back to native VA backend.")
        return simulate_voice(voice, input_wav=input_wav, instrument=instrument, prefiltered=False)

    vcfg = VOICES.get(voice, {})
    cir_rel = vcfg.get("circuit", f"circuits/{voice}.cir")
    cir_path = REPO_ROOT / cir_rel
    if not cir_path.exists():
        cir_path = CIRCUITS_DIR / f"{voice}.cir"
    if not cir_path.exists():
        print(f"Warning: Netlist '{cir_path.name}' not found.")
        return False

    input_aperture = CIRCUITS_DIR / "v1_1_1_aperture.wav"
    if not input_aperture.exists():
        print(f"Notice: Audio source '{input_aperture.name}' not found in circuits/.")
        return False

    print(f"  -> Simulating SPICE (LTspice): {cir_path.name}...")
    cmd = [ltspice_bin, "-b", str(cir_path.resolve())]
    try:
        res = subprocess.run(cmd, cwd=str(CIRCUITS_DIR), timeout=300)
        if res.returncode != 0:
            print(f"     Warning: Simulation of {cir_path.name} exited with code {res.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"     Warning: Simulation of {cir_path.name} timed out after 300s")
        return False

def run_spice_voice(voice, instrument="30in", input_wav=None, ltspice_bin=DEFAULT_LTSPICE_BIN, backend="native"):
    """Legacy alias for run_circuit_simulation."""
    return run_circuit_simulation(voice, instrument=instrument, input_wav=input_wav, backend=backend, ltspice_bin=ltspice_bin)

def run_spice_batch(voices=None, instrument="30in", input_wav=None, backend="native", ltspice_bin=DEFAULT_LTSPICE_BIN):
    """Executes batch simulation of specified voice circuit models."""
    print(f"\n[Stage 3] Executing circuit simulations (Backend: {backend})...")
    target_voices = voices if voices else list(VOICES.keys())
    for voice in target_voices:
        run_circuit_simulation(voice, instrument=instrument, input_wav=input_wav, backend=backend, ltspice_bin=ltspice_bin)
    print("Batch circuit simulation finished.")

def run_training(instrument="30in", voice="03_modern_p_ceramic", input_wav=None, epochs=100, fast_dev_run=False):
    """Trains a Neural Amp Modeler (NAM) Architecture 2 model locally with MPS GPU acceleration."""
    print(f"\n[Training] Training Neural Amp Modeler A2 model for {voice} (Instrument: {instrument})...")
    script = SCRIPTS_DIR / "train_nam.py"
    cmd = [
        sys.executable, str(script),
        "--instrument", instrument,
        "--voice", voice,
        "--epochs", str(epochs),
    ]
    if input_wav:
        cmd.extend(["--input", input_wav])
    if fast_dev_run:
        cmd.append("--fast-dev-run")
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Notice: Model training exited with code {res.returncode}")

def list_instruments():
    print("Available Passivizer Source Instruments:")
    for iid, cfg in INSTRUMENTS.items():
        print(f"  - {iid}: {cfg.get('name', iid)} ({cfg.get('scale_length_in', 34.0)}\")")
        pickups = cfg.get("pickups", {})
        for pid, pcfg in pickups.items():
            print(f"      * [{pid}] {pcfg.get('name', pid)}: pos={pcfg.get('position_from_bridge_m', 0)*1000:.1f}mm, w={pcfg.get('aperture_width_in', 0):.2f}\", d={pcfg.get('coil_spacing_in', 0):.2f}\"")

def list_voices():
    print("Available Passivizer Target Pickup Voices (SPICE Digital Twins):")
    for vid, cfg in VOICES.items():
        print(f"  - {vid}: {cfg.get('name', vid)} ({cfg.get('topology', '')})")
        coils = resolve_voice_coils(cfg)
        pickups = resolve_voice_pickups(cfg)
        eff_pos = compute_effective_position(coils)
        if len(pickups) > 1:
            print(f"      Circuit: {cfg.get('circuit', '')} | Pickups={len(pickups)}, Coils={len(coils)} (Eff pos={eff_pos*1000:.1f}mm) | Composite fr={cfg.get('fr', 0)}Hz (Q={cfg.get('Q', 0)})")
            for p in pickups:
                print(f"        * [{p['name']}]: fr={p['fr']:.0f}Hz (Q={p['Q']:.1f}), weight={p['weight']:.2f}, coils={len(p['coils'])}")
        else:
            print(f"      Circuit: {cfg.get('circuit', '')} | Coils={len(coils)} (Eff pos={eff_pos*1000:.1f}mm) | fr={cfg.get('fr', 0)}Hz (Q={cfg.get('Q', 0)})")

def main():
    parser = argparse.ArgumentParser(description="Passivizer SPICE -> NAM Automation Pipeline")
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
    parser.add_argument(
        "--stage",
        choices=["all", "viz", "prep", "spice", "sim", "simulate", "train"],
        default="all",
        help="Pipeline stage to execute (default: all; 'sim' or 'simulate' aliases for circuit modeling)"
    )
    parser.add_argument(
        "--backend",
        choices=["native", "ltspice"],
        default="native",
        help="Circuit simulation engine: 'native' (Apple Silicon Virtual Analog) or 'ltspice' (legacy external app)"
    )
    parser.add_argument(
        "--voice",
        default="03_modern_p_ceramic",
        help="Target pickup voice for audio pre-filtering and training (voice ID, comma-separated list, or 'all')"
    )
    parser.add_argument(
        "--input-wav",
        default=None,
        help="Path to NAM calibration audio file (default: auto-detects T3K-sweep-v3.wav or v1_1_1.wav)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of training epochs for NAM model (default: 100)"
    )
    parser.add_argument(
        "--fast-dev-run",
        action="store_true",
        help="Run 1-batch dry run for smoke testing NAM training"
    )
    parser.add_argument(
        "--ltspice-path",
        default=DEFAULT_LTSPICE_BIN,
        help="Path to LTspice binary for headless simulation (when using --backend ltspice)"
    )
    parser.add_argument(
        "--list-instruments",
        action="store_true",
        help="List all configured source instruments and their pickups"
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List all target pickup voices and their SPICE netlists"
    )
    args = parser.parse_args()

    if args.list_instruments:
        list_instruments()
        return

    if args.list_voices:
        list_voices()
        return

    voices_to_run = resolve_voices(args.voice)

    print("========================================")
    print("  PASSIVIZER SPICE -> NAM PIPELINE")
    print(f"  Instrument: {args.instrument}")
    print(f"  Stage:      {args.stage}")
    print(f"  Backend:    {args.backend}")
    print(f"  Voices ({len(voices_to_run)}): {', '.join(voices_to_run)}")
    print("========================================")

    input_wav = args.input_wav
    if not (REPO_ROOT / input_wav).exists():
        for candidate in ["T3K-sweep-v3.wav", "v3_0_0.wav", "input.wav"]:
            if (REPO_ROOT / candidate).exists():
                input_wav = candidate
                break

    if args.stage in ["all", "viz"]:
        run_visualization(instrument=args.instrument)

    if args.stage == "prep":
        for idx, voice in enumerate(voices_to_run, 1):
            print(f"\n[{idx}/{len(voices_to_run)}] Pre-filtering audio: {voice}...")
            run_prep_audio(input_wav=input_wav, instrument=args.instrument, voice=voice)

    elif args.stage in ["spice", "sim", "simulate"]:
        for idx, voice in enumerate(voices_to_run, 1):
            print(f"\n[{idx}/{len(voices_to_run)}] Circuit simulation: {voice} (Backend: {args.backend})...")
            run_circuit_simulation(
                voice=voice,
                instrument=args.instrument,
                input_wav=input_wav,
                backend=args.backend,
                ltspice_bin=args.ltspice_path,
            )

    elif args.stage == "train":
        for idx, voice in enumerate(voices_to_run, 1):
            print(f"\n[{idx}/{len(voices_to_run)}] Training NAM A2 Model: {voice}...")
            run_training(
                instrument=args.instrument,
                voice=voice,
                input_wav=input_wav,
                epochs=args.epochs,
                fast_dev_run=args.fast_dev_run,
            )

    elif args.stage == "all":
        for idx, voice in enumerate(voices_to_run, 1):
            print(f"\n==================================================")
            print(f"  [{idx}/{len(voices_to_run)}] Full Cycle for Voice: {voice}")
            print(f"==================================================")
            run_circuit_simulation(
                voice=voice,
                instrument=args.instrument,
                input_wav=input_wav,
                backend=args.backend,
                ltspice_bin=args.ltspice_path,
            )
            run_training(
                instrument=args.instrument,
                voice=voice,
                input_wav=input_wav,
                epochs=args.epochs,
                fast_dev_run=args.fast_dev_run,
            )

    print("\n[Pipeline Complete]")

if __name__ == "__main__":
    main()

