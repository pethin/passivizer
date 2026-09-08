"""
Passivizer - Neural Amp Modeler (NAM) Architecture 2 (A2) Local Trainer
Trains a high-fidelity analog twin neural model using Apple Silicon Metal (MPS) GPU acceleration.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"
MODELS_DIR = REPO_ROOT / "models"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import VOICES

def find_sweep_input(candidate_path=None):
    if candidate_path and Path(candidate_path).exists():
        return Path(candidate_path)
    for name in ["T3K-sweep-v3.wav", "v3_0_0.wav", "v1_1_1.wav", "input.wav"]:
        p = REPO_ROOT / name
        if p.exists():
            return p
    return None

def train_voice(
    voice="03_modern_p_ceramic",
    input_wav=None,
    output_wav=None,
    models_dir=MODELS_DIR,
    epochs=100,
    batch_size=16,
    silent=False,
    save_plot=False,
    fast_dev_run=False,
):
    try:
        import nam.train.core as nam_core
        from nam.models.metadata import UserMetadata
        import nam.train.metadata as train_meta
    except ImportError:
        print("Error: 'neural-amp-modeler' is not installed in the current environment.")
        print("Please run with:")
        print(f"  uv run --with neural-amp-modeler python main.py --stage train --voice {voice}")
        return False

    input_path = find_sweep_input(input_wav)
    if not input_path:
        print("Error: Could not find training sweep file (e.g. T3K-sweep-v3.wav or v3_0_0.wav).")
        return False

    if not output_wav:
        output_path = CIRCUITS_DIR / f"out_{voice}.wav"
    else:
        output_path = Path(output_wav)

    if not output_path.exists():
        print(f"Error: Target output audio '{output_path}' does not exist.")
        print(f"Please run the SPICE simulation stage first:")
        print(f"  uv run python main.py --stage prep --voice {voice}")
        print(f"  uv run python main.py --stage spice")
        return False

    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    train_work_dir = models_dir / f".train_{voice}"
    train_work_dir.mkdir(parents=True, exist_ok=True)

    vcfg = VOICES.get(voice, {})
    voice_name = vcfg.get("name", voice)

    print(f"\n========================================")
    print(f"  PASSIVIZER NAM LOCAL A2 TRAINER")
    print(f"  Voice:       {voice} ({voice_name})")
    print(f"  Input:       {input_path.name}")
    print(f"  Output:      {output_path.name}")
    print(f"  Epochs:      {epochs}")
    print(f"  Destination: {models_dir / f'{voice}.nam'}")
    print(f"========================================\n")

    user_metadata = UserMetadata(
        name=voice_name,
        modeled_by="Passivizer",
        gear_make="Passivizer Analog Digital Twin",
        gear_model=voice_name,
        gear_type="preamp",
        tone_type="clean",
    )

    print("Validating dataset and calibration markers...")
    train_output = nam_core.train(
        input_path=str(input_path),
        output_path=str(output_path),
        train_path=str(train_work_dir),
        epochs=epochs,
        batch_size=batch_size,
        modelname=voice,
        silent=silent,
        save_plot=save_plot,
        local=True,
        user_metadata=user_metadata,
        fast_dev_run=fast_dev_run,
    )

    if train_output is None or train_output.model is None:
        print("Error: Training did not produce a model.")
        return False

    print("\nExporting Architecture 2 (.nam) model container...")
    target_nam = models_dir / f"{voice}.nam"
    train_output.model.net.export(
        str(models_dir),
        basename=voice,
        user_metadata=user_metadata,
        other_metadata={
            train_meta.TRAINING_KEY: train_output.metadata.model_dump()
        },
    )

    # Clean up temporary lightning checkpoint folder
    if train_work_dir.exists():
        shutil.rmtree(train_work_dir, ignore_errors=True)

    if target_nam.exists():
        size_kb = target_nam.stat().st_size / 1024
        print(f"\n[Success] Architecture 2 Model exported successfully!")
        print(f"  Model: {target_nam} ({size_kb:.1f} KB)")
        if train_output.metadata.validation_esr is not None:
            print(f"  Validation ESR: {train_output.metadata.validation_esr:.6f}")
        print(f"  Ready for Darkglass Anagram Block 1 (Preamp) loading.")
        return True
    else:
        print(f"Warning: Expected model file at {target_nam} not found.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Passivizer NAM Architecture 2 Local Trainer")
    parser.add_argument("--voice", choices=VOICES.keys(), default="03_modern_p_ceramic", help="Target pickup voice")
    parser.add_argument("--input", help="Path to dry training sweep WAV (default: auto-detect T3K-sweep-v3.wav)")
    parser.add_argument("--output", help="Path to simulated SPICE output WAV (default: circuits/out_<voice>.wav)")
    parser.add_argument("--models-dir", default=str(MODELS_DIR), help="Output models directory")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs (default: 100)")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size (default: 16)")
    parser.add_argument("--show-plot", action="store_true", help="Display matplotlib validation plot window")
    parser.add_argument("--save-plot", action="store_true", help="Save validation plot as PNG in models/")
    parser.add_argument("--fast-dev-run", action="store_true", help="Run 1-batch dry run for smoke testing")
    parser.add_argument("--gui", action="store_true", help="Launch official NAM desktop GUI")
    args = parser.parse_args()

    if args.gui:
        try:
            from nam.cli import nam_gui
            nam_gui()
            return
        except ImportError:
            print("Error: 'neural-amp-modeler' GUI could not be loaded.")
            return

    train_voice(
        voice=args.voice,
        input_wav=args.input,
        output_wav=args.output,
        models_dir=args.models_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        silent=not args.show_plot,
        save_plot=args.save_plot,
        fast_dev_run=args.fast_dev_run,
    )

if __name__ == "__main__":
    main()
