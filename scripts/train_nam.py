"""
Passivizer - Neural Amp Modeler (NAM) Architecture 2 (A2) Local Trainer
Trains a high-fidelity analog twin neural model using Apple Silicon Metal (MPS) GPU acceleration.
Includes full source instrument, scale length, and pickup routing metadata in the exported .nam container.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"
MODELS_DIR = REPO_ROOT / "models"
AUDIO_DIR = REPO_ROOT / "audio"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from model_physics import (
    VOICES,
    load_instrument,
    get_source_pickup,
    INSTRUMENTS,
    resolve_voices,
    resolve_voice_coils,
    resolve_voice_pickups,
    compute_effective_position,
)

def find_sweep_input(candidate_path=None):
    if candidate_path and Path(candidate_path).exists():
        return Path(candidate_path)
    for name in ["T3K-sweep-v3.wav", "v3_0_0.wav", "v1_1_1.wav", "input.wav"]:
        p = REPO_ROOT / name
        if p.exists():
            return p
    return None

def train_voice(
    instrument="30in",
    voice="03_modern_p_ceramic",
    input_wav=None,
    output_wav=None,
    models_dir=MODELS_DIR,
    epochs=100,
    batch_size=16,
    silent=True,
    save_plot=False,
    fast_dev_run=False,
):
    try:
        import nam.train.core as nam_core
        from nam.models.metadata import UserMetadata
        import nam.train.metadata as train_meta
    except ImportError:
        print("Error: 'neural-amp-modeler' is not installed in the current environment.")
        print("Please run `uv sync` or install project dependencies:")
        print(f"  uv run python main.py --stage train --instrument {instrument} --voice {voice}")
        return False

    # 1. Load source instrument and resolve routing
    inst_cfg = load_instrument(instrument)
    inst_id = inst_cfg["id"]
    inst_name = inst_cfg.get("name", inst_id)
    scale_length_in = inst_cfg.get("scale_length_in", 34.0)

    src_pickup = get_source_pickup(inst_cfg, voice)
    src_pickup_name = src_pickup.get("name", "Source Pickup")
    src_pos_mm = src_pickup.get("position_from_bridge_m", 0.0) * 1000.0

    vcfg = VOICES.get(voice, {})
    voice_name = vcfg.get("name", voice)

    input_path = find_sweep_input(input_wav)
    if not input_path:
        print("Error: Could not find training sweep file (e.g. T3K-sweep-v3.wav or v3_0_0.wav).")
        return False

    if not output_wav:
        candidate = AUDIO_DIR / inst_id / f"out_{voice}.wav"
        if candidate.exists():
            output_path = candidate
        elif (CIRCUITS_DIR / inst_id / f"out_{voice}.wav").exists():
            output_path = CIRCUITS_DIR / inst_id / f"out_{voice}.wav"
        else:
            output_path = CIRCUITS_DIR / f"out_{voice}.wav"
    else:
        output_path = Path(output_wav)

    if not output_path.exists():
        print(f"Error: Target output audio '{output_path}' does not exist.")
        print(f"Please run the simulation stage first:")
        print(f"  uv run python main.py --stage sim --instrument {inst_id} --voice {voice}")
        return False

    models_dir = Path(models_dir)
    inst_models_dir = models_dir / inst_id
    inst_models_dir.mkdir(parents=True, exist_ok=True)
    train_work_dir = inst_models_dir / f".train_{voice}"
    train_work_dir.mkdir(parents=True, exist_ok=True)

    model_basename = voice
    target_nam = inst_models_dir / f"{voice}.nam"

    print(f"\n========================================")
    print(f"  PASSIVIZER NAM LOCAL A2 TRAINER")
    print(f"  Source Bass: {inst_name} ({inst_id}, {scale_length_in}\")")
    print(f"  Source PU:   {src_pickup_name} (pos={src_pos_mm:.1f}mm)")
    print(f"  Target Voice:{voice} ({voice_name})")
    print(f"  Input Audio: {input_path.name}")
    print(f"  Output Audio:{output_path.name}")
    print(f"  Epochs:      {epochs}")
    print(f"  Destination: {target_nam}")
    print(f"========================================\n")

    model_title = f"{voice_name} [{inst_name}]"
    user_metadata = UserMetadata(
        name=model_title,
        modeled_by="Passivizer",
        gear_make=inst_name,
        gear_model=f"{src_pickup_name} -> {voice_name}",
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
        modelname=model_basename,
        silent=silent,
        save_plot=save_plot,
        local=True,
        user_metadata=user_metadata,
        fast_dev_run=fast_dev_run,
    )

    if train_output is None or train_output.model is None:
        print("Error: Training did not produce a model.")
        return False

    print("\nExporting Architecture 2 (.nam) model container with full instrument metadata...")
    other_metadata = {
        train_meta.TRAINING_KEY: train_output.metadata.model_dump(),
        "source_instrument": {
            "id": inst_id,
            "name": inst_name,
            "scale_length_in": scale_length_in,
            "scale_length_m": inst_cfg.get("scale_length_m"),
            "string_wave_speeds": inst_cfg.get("string_wave_speeds", []),
            "pickup": {
                "id": src_pickup.get("id", ""),
                "name": src_pickup_name,
                "position_from_bridge_m": src_pickup.get("position_from_bridge_m", 0.0),
                "position_from_bridge_mm": src_pos_mm,
                "aperture_width_in": src_pickup.get("aperture_width_in", 0.0),
                "coil_spacing_in": src_pickup.get("coil_spacing_in", 0.0),
                "type": src_pickup.get("type", ""),
            },
        },
        "target_voice": {
            "id": voice,
            "name": voice_name,
            "topology": vcfg.get("topology", ""),
            "resonant_frequency_hz": vcfg.get("fr", 0.0),
            "q_factor": vcfg.get("Q", 0.0),
            "target_position_34_m": compute_effective_position(resolve_voice_coils(vcfg)),
            "effective_position_m": compute_effective_position(resolve_voice_coils(vcfg)),
            "pickups": resolve_voice_pickups(vcfg),
            "coils": resolve_voice_coils(vcfg),
            "circuit": vcfg.get("circuit", ""),
        },
    }

    train_output.model.net.export(
        str(inst_models_dir),
        basename=model_basename,
        user_metadata=user_metadata,
        other_metadata=other_metadata,
    )

    # Clean up temporary lightning checkpoint folder
    if train_work_dir.exists():
        shutil.rmtree(train_work_dir, ignore_errors=True)

    if target_nam.exists():
        size_kb = target_nam.stat().st_size / 1024
        print(f"\n[Success] Architecture 2 Model exported successfully!")
        print(f"  Model Path:    {target_nam} ({size_kb:.1f} KB)")
        print(f"  Model Title:   {model_title}")
        print(f"  Source Bass:   {inst_name}")
        print(f"  Source Pickup: {src_pickup_name} ({src_pos_mm:.1f}mm)")
        if train_output.metadata.validation_esr is not None:
            print(f"  Validation ESR: {train_output.metadata.validation_esr:.6f}")
        print(f"  Ready for Darkglass Anagram Block 1 (Preamp) loading.")
        return True
    else:
        print(f"Warning: Expected model file at {target_nam} not found.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Passivizer NAM Architecture 2 Local Trainer")
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
    parser.add_argument("--voice", default="03_modern_p_ceramic", help="Target pickup voice (ID, comma-separated list, or 'all')")
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

    voices_to_run = resolve_voices(args.voice)
    all_ok = True
    for idx, voice in enumerate(voices_to_run, 1):
        if len(voices_to_run) > 1:
            print(f"\n==================================================")
            print(f"  [{idx}/{len(voices_to_run)}] Training Voice: {voice}")
            print(f"==================================================")
        out_wav = args.output if len(voices_to_run) == 1 else None
        ok = train_voice(
            instrument=args.instrument,
            voice=voice,
            input_wav=args.input,
            output_wav=out_wav,
            models_dir=args.models_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
            silent=not args.show_plot,
            save_plot=args.save_plot,
            fast_dev_run=args.fast_dev_run,
        )
        if not ok:
            all_ok = False

    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
