"""
Allomorph Pipeline - CLI Parser and Dispatcher
Command-line entrypoint coordinating full end-to-end simulation, export, and training workflows.
"""

import argparse
from pathlib import Path
from typing import Optional, Sequence

from allomorph.config import (
    REPO_ROOT,
    INSTRUMENTS,
    VOICES,
    resolve_voice_coils,
    resolve_voice_pickups,
    compute_effective_position,
    load_instrument,
    get_source_pickup,
)
from allomorph.naming import (
    resolve_voices,
    resolve_instruments,
    get_baked_basename,
)
from allomorph.circuit import (
    AUDIO_DIR,
    MODELS_DIR,
    simulate_voice,
    generate_canonical_sweep,
    export_all_frontend_irs,
    simulate_backend_targets,
)
from allomorph.pipeline.stages import (
    DEFAULT_LTSPICE_BIN,
    run_visualization,
    run_prep_audio,
    run_training,
)
from allomorph.pipeline.batch import run_spice_batch


def list_instruments():
    """Lists all configured source instruments and their pickups."""
    print("Available Allomorph Source Instruments:")
    for iid, cfg in INSTRUMENTS.items():
        print(f"  - {iid}: {cfg.get('name', iid)} ({cfg.get('scale_length_in', 34.0)}\")")
        pickups = cfg.get("pickups", {})
        for pid, pcfg in pickups.items():
            print(f"      * [{pid}] {pcfg.get('name', pid)}: pos={pcfg.get('position_from_bridge_m', 0)*1000:.1f}mm, w={pcfg.get('aperture_width_in', 0):.2f}\", d={pcfg.get('coil_spacing_in', 0):.2f}\"")


def list_voices():
    """Lists all target pickup voices and their SPICE netlists."""
    print("Available Allomorph Target Pickup Voices (SPICE Digital Twins):")
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


def main(argv: Optional[Sequence[str]] = None):
    """Main CLI entrypoint for Allomorph pipeline automation."""
    parser = argparse.ArgumentParser(description="Allomorph SPICE -> NAM Automation Pipeline")
    parser.add_argument(
        "--instrument", "-i",
        default="all",
        help="Source instrument configuration (ID, comma-separated list, 'all', path to .toml, or alias like 30in, 32in; default: 'all')"
    )
    parser.add_argument(
        "--stage",
        choices=["all", "viz", "canonical", "frontends", "targets", "prep", "spice", "sim", "simulate", "train"],
        default="all",
        help="Pipeline stage to execute: 'canonical' (intermediate sweep), 'frontends' (export 33 IRs), 'targets' (simulate backend sweeps), 'train' (train models), 'viz' (visualizer), 'all' (canonical + frontends + targets + viz)."
    )
    parser.add_argument(
        "--tier",
        choices=["clean", "standard", "std", "hotrod", "dynamic", "all"],
        default=None,
        help="Dynamic tier: 'standard' / 'std' (100%% nominal target saturation; default for Architecture C targets), 'clean' (0%% saturation), 'hotrod' (175%% overwound), 'dynamic' (differential source/target saturation; default when using --bake), 'all'."
    )
    parser.add_argument(
        "--bake",
        action="store_true",
        help="On-demand single-block monolithic bake mode: directly models the source instrument to target voice transformation in a single .nam model."
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Train NAM model locally with Apple Silicon Metal/MPS acceleration after simulation (used with --bake)"
    )
    parser.add_argument(
        "--pickup", "-p",
        default=None,
        help="Physical pickup setting for source instrument ('auto' to resolve from pickup_mapping, or explicit pickup ID; default when using --bake is 'auto')"
    )
    parser.add_argument(
        "--backend",
        choices=["native", "ltspice"],
        default="native",
        help="Circuit simulation engine: 'native' (built-in Apple Silicon WAV SPICE simulator) or 'ltspice' (legacy external app)"
    )
    parser.add_argument(
        "--voice", "-v",
        default="all",
        help="Target pickup voice for audio pre-filtering, simulation, and training (voice ID, comma-separated list, or 'all'; default: 'all')"
    )
    parser.add_argument(
        "--jobs", "-j",
        type=int,
        default=None,
        help="Number of parallel worker processes for batch simulation (default: min(4, CPU count))"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum audio sample frames to simulate (default: None for full file)"
    )
    parser.add_argument(
        "--input-wav",
        default=None,
        help="Path to NAM calibration audio file (default: auto-detects T3K-sweep-v3.wav, v3_0_0.wav, or input.wav)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Maximum number of training epochs for NAM model (default: 100)"
    )
    parser.add_argument(
        "--goal-esr",
        type=float,
        default=0.0005,
        help="Goal validation ESR for early stopping (default: 0.0005 for studio quality; set to 0 to disable)"
    )
    parser.add_argument(
        "--no-goal-esr",
        action="store_true",
        help="Disable goal ESR early stopping and train for the exact number of epochs specified"
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
    args = parser.parse_args(argv)

    if args.list_instruments:
        list_instruments()
        return

    if args.list_voices:
        list_voices()
        return

    if args.jobs is not None and args.jobs < 1:
        parser.error("--jobs must be a positive integer >= 1")

    if args.max_samples is not None and args.max_samples < 1:
        parser.error("--max-samples must be a positive integer >= 1")

    effective_goal_esr = None if args.no_goal_esr or (args.goal_esr is not None and args.goal_esr <= 0) else args.goal_esr
    instruments_to_run = resolve_instruments(args.instrument or "all")
    voices_to_run = resolve_voices(args.voice or "all")

    samples_str = str(args.max_samples) if args.max_samples is not None else "full"

    print("========================================")
    print("  ALLOMORPH SPICE -> NAM PIPELINE")
    print(f"  Instruments ({len(instruments_to_run)}): {', '.join(instruments_to_run)}")
    print(f"  Stage:       {args.stage}")
    print(f"  Backend:     {args.backend}")
    print(f"  Max Samples: {samples_str}")
    print(f"  Voices ({len(voices_to_run)}): {', '.join(voices_to_run)}")
    print("========================================")

    input_wav = args.input_wav
    if not input_wav or not (REPO_ROOT / input_wav).exists():
        for candidate in ["T3K-sweep-v3.wav", "v3_0_0.wav", "input.wav"]:
            if (REPO_ROOT / candidate).exists():
                input_wav = candidate
                break

    if args.bake:
        effective_tier = args.tier if args.tier is not None else "dynamic"
        pickup_setting = args.pickup if args.pickup is not None else "auto"

        print("\n========================================")
        print("  ALLOMORPH ON-DEMAND SINGLE-BLOCK BAKE")
        print(f"  Source Instruments ({len(instruments_to_run)}): {', '.join(instruments_to_run)}")
        print(f"  Pickup Switch:     {pickup_setting}")
        print(f"  Dynamic Tier:      {effective_tier}")
        print(f"  Voices ({len(voices_to_run)}): {', '.join(voices_to_run)}")
        print("========================================\n")

        total_bakes = len(instruments_to_run) * len(voices_to_run)
        current_bake = 0
        for inst in instruments_to_run:
            inst_cfg = load_instrument(inst)
            inst_id = inst_cfg.get("id", str(inst))

            inst_baked_audio_dir = AUDIO_DIR / "baked" / inst_id
            inst_baked_audio_dir.mkdir(parents=True, exist_ok=True)
            inst_models_dir = MODELS_DIR / "baked" / inst_id
            if args.train or args.stage == "train":
                inst_models_dir.mkdir(parents=True, exist_ok=True)

            for voice in voices_to_run:
                current_bake += 1
                if total_bakes > 1:
                    print(f"\n--- [{current_bake}/{total_bakes}] Baking {inst_id} -> {voice} ---")

                if pickup_setting == "auto":
                    src_pickup = get_source_pickup(inst_cfg, voice)
                    eff_pickup = src_pickup.get("id", "default")
                else:
                    eff_pickup = pickup_setting

                basename = get_baked_basename(voice, tier=effective_tier, pickup=pickup_setting)
                baked_wav = inst_baked_audio_dir / f"{basename}.wav"

                simulate_voice(
                    voice,
                    input_wav=input_wav,
                    output_wav=baked_wav,
                    instrument=inst,
                    pickup=eff_pickup,
                    tier=effective_tier,
                    normalize="none",
                    max_samples=args.max_samples,
                )
                print(f"Baked simulation exported: {baked_wav}")

                if args.train or args.stage == "train":
                    run_training(
                        instrument=inst,
                        voice=voice,
                        input_wav=input_wav,
                        output_wav=baked_wav,
                        models_dir=inst_models_dir,
                        tier=effective_tier,
                        epochs=args.epochs,
                        goal_esr=effective_goal_esr,
                        fast_dev_run=args.fast_dev_run,
                        basename=basename,
                    )
        return

    if args.stage == "canonical":
        generate_canonical_sweep(input_wav=input_wav)
        return

    if args.stage == "frontends":
        export_all_frontend_irs()
        return

    if args.stage == "targets":
        simulate_backend_targets(tier=args.tier or "standard", voice_id=args.voice)
        return

    if args.stage in ["all", "viz"]:
        if len(instruments_to_run) == 1 and args.instrument != "all":
            run_visualization(instrument=instruments_to_run[0])
        else:
            run_visualization(instrument="all")
        if args.stage == "viz":
            return

    if args.stage == "prep":
        for inst in instruments_to_run:
            for idx, voice in enumerate(voices_to_run, 1):
                print(f"\n[{idx}/{len(voices_to_run)}] Pre-filtering audio: {inst} -> {voice}...")
                run_prep_audio(input_wav=input_wav, instrument=inst, voice=voice)

    elif args.stage in ["spice", "sim", "simulate"]:
        for inst in instruments_to_run:
            run_spice_batch(
                voices=voices_to_run,
                instrument=inst,
                input_wav=input_wav,
                backend=args.backend,
                ltspice_bin=args.ltspice_path,
                jobs=args.jobs,
                max_samples=args.max_samples,
            )

    elif args.stage == "train":
        tiers_to_train = ["clean", "standard", "hotrod"] if args.tier == "all" else [args.tier or "standard"]
        for inst in instruments_to_run:
            for t in tiers_to_train:
                for idx, voice in enumerate(voices_to_run, 1):
                    print(f"\n[{idx}/{len(voices_to_run)}] Training NAM A2 Model: {inst} -> {voice} (Tier: {t})...")
                    run_training(
                        instrument=inst,
                        voice=voice,
                        input_wav=input_wav,
                        tier=t,
                        epochs=args.epochs,
                        goal_esr=effective_goal_esr,
                        fast_dev_run=args.fast_dev_run,
                    )

    elif args.stage == "all":
        print("\n--- Step 1: Canonical Intermediate Baseline Sweep ---")
        generate_canonical_sweep(input_wav=input_wav)
        print("\n--- Step 2: Export All 33 Frontend Deconvolution IRs ---")
        export_all_frontend_irs()
        print("\n--- Step 3: Simulate Backend Targets ---")
        simulate_backend_targets(tier=args.tier or "standard", voice_id=args.voice)
        print("\n[Pipeline Complete: 33 Frontend IRs + Backend Sweeps + Interactive Portal Ready]")
