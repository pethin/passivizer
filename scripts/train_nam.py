"""
Allomorph - Neural Amp Modeler (NAM) Architecture 2 (A2) Local Trainer
Trains a high-fidelity analog twin neural model using Apple Silicon Metal (MPS) GPU acceleration.
Includes full source instrument, scale length, and pickup routing metadata in the exported .nam container.
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"
MODELS_DIR = REPO_ROOT / "models"
AUDIO_DIR = REPO_ROOT / "audio"
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from allomorph.config import (
    VOICES,
    InstrumentConfig,
    PickupConfig,
    compute_effective_position,
    get_source_pickup,
    load_instrument,
    resolve_voice_coils,
    resolve_voice_pickups,
)
from allomorph.naming import (
    VOICE_CONCISE_SLUGS,
    resolve_instruments,
    resolve_voices,
)


def find_sweep_input(candidate_path: str | Path | None = None) -> Path | None:
    if candidate_path and Path(candidate_path).exists():
        return Path(candidate_path)
    for name in ["T3K-sweep-v3.wav", "v3_0_0.wav", "input.wav"]:
        p = REPO_ROOT / name
        if p.exists():
            return p
    return None

DEFAULT_GOAL_ESR = 0.0005  # Studio reference early-stopping target (~ -33 dB ESR)
CANONICAL_SWEEP_PATH = AUDIO_DIR / "canonical" / "canonical_sweep.wav"

def train_voice(
    instrument: str | dict[str, Any] = "30in",
    voice: str = "04_modern_p_ceramic",
    input_wav: str | Path | None = None,
    output_wav: str | Path | None = None,
    models_dir: str | Path = MODELS_DIR,
    tier: str | None = None,
    epochs: int = 100,
    goal_esr: float | None = DEFAULT_GOAL_ESR,
    batch_size: int = 16,
    silent: bool = True,
    save_plot: bool = False,
    fast_dev_run: bool = False,
    basename: str | None = None,
) -> bool:
    try:
        import nam.train.core as nam_core
        import nam.train.metadata as train_meta
        from nam.models.metadata import UserMetadata
    except ImportError:
        print("Error: 'neural-amp-modeler' is not installed in the current environment.")
        print("Please run `uv sync` or install project dependencies:")
        print(f"  uv run python main.py --stage train --voice {voice}")
        return False

    vcfg = VOICES.get(voice, {})
    voice_name = vcfg.get("name", voice)

    tier_map = {
        "clean": ("01_studio_clean", "cln_"),
        "standard": ("02_standard_dynamic", "std_"),
        "std": ("02_standard_dynamic", "std_"),
        "hotrod": ("03_hot_rod", "hot_"),
        "dynamic": ("00_dynamic", "dyn_"),
    }

    if basename:
        model_basename = basename
        try:
            inst_cfg = load_instrument(instrument)
            inst_id = inst_cfg["id"]
            inst_name = inst_cfg.get("name", inst_id)
            scale_length_in = inst_cfg.get("scale_length_in", 34.0)
            src_pickup = get_source_pickup(inst_cfg, voice)
            src_pickup_name = src_pickup.get("name", "Source Pickup")
            src_pos_mm = src_pickup.get("position_from_bridge_m", 0.0) * 1000.0
        except (FileNotFoundError, KeyError, ValueError, OSError):
            inst_id = str(instrument)
            inst_name = str(instrument)
            scale_length_in = 34.0
            inst_cfg = InstrumentConfig(
                id=inst_id,
                name=inst_name,
                scale_length_in=scale_length_in,
                scale_length_m=0.8636,
                string_wave_speeds=[58.02, 75.88, 99.19, 129.6],
                pickups={},
            )
            src_pickup = PickupConfig(name="Baked Pickup", position_from_bridge_m=0.0)
            src_pickup_name = "Baked Pickup"
            src_pos_mm = 0.0

        p_models = Path(models_dir)
        if p_models.name == "baked" or str(p_models).endswith("/baked"):
            inst_models_dir = p_models / inst_id
        else:
            inst_models_dir = p_models

        inst_models_dir.mkdir(parents=True, exist_ok=True)
        target_nam = inst_models_dir / f"{model_basename}.nam"
        input_path = find_sweep_input(input_wav)
        output_path = Path(output_wav) if output_wav else (AUDIO_DIR / "baked" / inst_id / f"{model_basename}.wav")
    elif tier:
        folder_name, prefix = tier_map.get(tier, ("02_standard_dynamic", "std_"))
        slug = VOICE_CONCISE_SLUGS.get(voice, voice)
        model_basename = f"{prefix}{slug}"
        inst_models_dir = Path(models_dir) / folder_name
        inst_models_dir.mkdir(parents=True, exist_ok=True)
        target_nam = inst_models_dir / f"{model_basename}.nam"
        input_path = find_sweep_input(input_wav)
        output_path = Path(output_wav) if output_wav else (AUDIO_DIR / "targets" / folder_name / f"out_{voice}.wav")
        try:
            inst_cfg = load_instrument("canonical_intermediate")
        except (FileNotFoundError, KeyError, ValueError, OSError):
            inst_cfg = InstrumentConfig(
                id="canonical_intermediate",
                name="Canonical Intermediate",
                scale_length_in=34.0,
                scale_length_m=0.8636,
                string_wave_speeds=[58.02, 75.88, 99.19, 129.6],
                pickups={},
            )
        inst_id = "canonical_intermediate"
        inst_name = "Canonical Intermediate"
        scale_length_in = 34.0
        src_pickup = inst_cfg.pickups.get("canonical_median") or PickupConfig(name="93.5mm Canonical Median", position_from_bridge_m=0.0935)
        src_pickup_name = "93.5mm Canonical Median"
        src_pos_mm = 93.5
    else:
        inst_cfg = load_instrument(instrument)
        inst_id = inst_cfg["id"]
        inst_name = inst_cfg.get("name", inst_id)
        scale_length_in = inst_cfg.get("scale_length_in", 34.0)

        src_pickup = get_source_pickup(inst_cfg, voice)
        src_pickup_name = src_pickup.get("name", "Source Pickup")
        src_pos_mm = src_pickup.get("position_from_bridge_m", 0.0) * 1000.0

        input_path = find_sweep_input(input_wav)
        if not output_wav:
            candidate = AUDIO_DIR / inst_id / f"out_{voice}.wav"
            output_path = candidate if candidate.exists() else (CIRCUITS_DIR / f"out_{voice}.wav")
        else:
            output_path = Path(output_wav)
        inst_models_dir = Path(models_dir) / inst_id
        inst_models_dir.mkdir(parents=True, exist_ok=True)
        model_basename = voice
        target_nam = inst_models_dir / f"{voice}.nam"

    if not input_path or not input_path.exists():
        print(f"Error: Could not find training sweep file '{input_path}'.")
        return False

    if not output_path.exists():
        print(f"Error: Target output audio '{output_path}' does not exist.")
        print("Please run the simulation stage first:")
        print(f"  uv run python main.py --stage sim --voice {voice} --tier {tier or 'dynamic'}")
        return False

    train_work_dir = inst_models_dir / f".train_{model_basename}"
    train_work_dir.mkdir(parents=True, exist_ok=True)

    if goal_esr is not None and goal_esr <= 0:
        threshold_esr = None
    else:
        threshold_esr = goal_esr

    print("\n========================================")
    print("  ALLOMORPH NAM LOCAL A2 TRAINER")
    print(f"  Source Bass: {inst_name} ({inst_id}, {scale_length_in}\")")
    print(f"  Source PU:   {src_pickup_name} (pos={src_pos_mm:.1f}mm)")
    print(f"  Target Voice:{voice} ({voice_name})")
    print(f"  Input Audio: {input_path.name}")
    print(f"  Output Audio:{output_path.name}")
    print(f"  Max Epochs:  {epochs}")
    esr_display = (
        f"{threshold_esr:.6f} (Studio Quality Early Stopping)"
        if threshold_esr is not None
        else "Disabled (Fixed Epochs)"
    )
    print(f"  Goal ESR:    {esr_display}")
    print(f"  Destination: {target_nam}")
    print("========================================\n")

    model_title = f"{voice_name} [{inst_name}]"
    user_metadata = UserMetadata(
        name=model_title,
        modeled_by="Allomorph (Peter Nguyen <peter@phn.dev>)",
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
        threshold_esr=threshold_esr,
        user_metadata=user_metadata,
        fast_dev_run=fast_dev_run,
    )

    if train_output is None or train_output.model is None:
        print("Error: Training did not produce a model.")
        return False

    print("\nExporting Architecture 2 (.nam) model container with full instrument metadata...")
    other_metadata = {
        train_meta.TRAINING_KEY: train_output.metadata.model_dump(),
        "license": "PolyForm Noncommercial License 1.0.0 (https://polyformproject.org/licenses/noncommercial/1.0.0)",
        "copyright": "Copyright 2026 Peter Nguyen <peter@phn.dev>. All commercial rights reserved.",
        "author": "Peter Nguyen <peter@phn.dev>",
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

    export_net: Any = train_output.model.net
    export_net.export(
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
        print("\n[Success] Architecture 2 Model exported successfully!")
        print(f"  Model Path:    {target_nam} ({size_kb:.1f} KB)")
        print(f"  Model Title:   {model_title}")
        print(f"  Source Bass:   {inst_name}")
        print(f"  Source Pickup: {src_pickup_name} ({src_pos_mm:.1f}mm)")
        if train_output.metadata.validation_esr is not None:
            vesr = train_output.metadata.validation_esr
            esr_status = ""
            if threshold_esr is not None:
                if vesr <= threshold_esr:
                    esr_status = f" (Goal Met <= {threshold_esr:.6f})"
                else:
                    esr_status = f" (Safety ceiling reached at {epochs} epochs)"
            print(f"  Validation ESR: {vesr:.6f}{esr_status}")
        print("  Ready for Darkglass Anagram Block 1 (Preamp) loading.")
        return True
    else:
        print(f"Warning: Expected model file at {target_nam} not found.")
        return False

def main():
    parser = argparse.ArgumentParser(description="Allomorph NAM Architecture 2 Local Trainer")
    parser.add_argument(
        "--instrument", "-i",
        default="all",
        help="Source instrument configuration (ID, comma-separated list, 'all', path to .toml, or alias like 30in, 32in; default: 'all')"
    )
    parser.add_argument("--voice", default="all", help="Target pickup voice (ID, comma-separated list, or 'all'; default: 'all')")
    parser.add_argument("--input", help="Path to dry training sweep WAV (default: auto-detect T3K-sweep-v3.wav)")
    parser.add_argument("--output", help="Path to simulated SPICE output WAV (default: circuits/out_<voice>.wav)")
    parser.add_argument("--models-dir", default=str(MODELS_DIR), help="Output models directory")
    parser.add_argument("--epochs", type=int, default=100, help="Maximum number of training epochs (default: 100)")
    parser.add_argument(
        "--goal-esr",
        type=float,
        default=DEFAULT_GOAL_ESR,
        help=f"Goal validation ESR for early stopping (default: {DEFAULT_GOAL_ESR} for studio quality; set to 0 to disable)"
    )
    parser.add_argument(
        "--no-goal-esr",
        action="store_true",
        help="Disable goal ESR early stopping and train for the exact number of epochs specified"
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size (default: 16)")
    parser.add_argument("--show-plot", action="store_true", help="Display matplotlib validation plot window")
    parser.add_argument("--save-plot", action="store_true", help="Save validation plot as PNG in models/")
    parser.add_argument(
        "--tier",
        choices=["clean", "standard", "std", "hotrod", "dynamic"],
        default=None,
        help="Dynamic tier: 'standard' / 'std' (100%% nominal target saturation), 'clean' (0%% saturation), 'hotrod' (175%% overwound), 'dynamic' (differential source/target saturation)."
    )
    parser.add_argument("--basename", help="Explicit basename for the exported .nam model file")
    parser.add_argument("--fast-dev-run", action="store_true", help="Run 1-batch dry run for smoke testing NAM training")
    parser.add_argument("--gui", action="store_true", help="Launch NAM training GUI")
    args = parser.parse_args()

    if args.gui:
        try:
            from nam.cli import nam_gui
            nam_gui()
            return
        except ImportError:
            print("Error: 'neural-amp-modeler' GUI could not be loaded.")
            return

    effective_goal_esr = None if args.no_goal_esr or (args.goal_esr is not None and args.goal_esr <= 0) else args.goal_esr

    instruments_to_run = resolve_instruments(args.instrument)
    voices_to_run = resolve_voices(args.voice)
    all_ok = True
    total_runs = len(instruments_to_run) * len(voices_to_run)
    current_run = 0
    for inst in instruments_to_run:
        for idx, voice in enumerate(voices_to_run, 1):
            current_run += 1
            if total_runs > 1:
                print("\n==================================================")
                print(f"  [{current_run}/{total_runs}] Training: {inst} -> {voice}")
                print("==================================================")
            out_wav = args.output if (len(voices_to_run) == 1 and len(instruments_to_run) == 1) else None
            ok = train_voice(
                instrument=inst,
                voice=voice,
                input_wav=args.input,
                output_wav=out_wav,
                models_dir=args.models_dir,
                tier=args.tier,
                epochs=args.epochs,
                goal_esr=effective_goal_esr,
                batch_size=args.batch_size,
                silent=not args.show_plot,
                save_plot=args.save_plot,
                fast_dev_run=args.fast_dev_run,
                basename=args.basename if (len(voices_to_run) == 1 and len(instruments_to_run) == 1) else None,
            )
            if not ok:
                all_ok = False

    if not all_ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
