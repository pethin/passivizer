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
MODELS_FRONTENDS_DIR = MODELS_DIR / "frontends"
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
from allomorph.pipeline.schema import (
    NamExportMetadata,
    NamSourceInstrumentMeta,
    NamSourcePickupMeta,
    NamTargetVoiceMeta,
    NamTrainingConfig,
    NamTrainingMetadata,
    get_tier_spec,
)


def find_sweep_input(candidate_path: str | Path | None = None) -> Path | None:
    if candidate_path and Path(candidate_path).exists():
        return Path(candidate_path)
    for name in ["T3K-sweep-v3.wav", "v3_0_0.wav", "input.wav"]:
        p = REPO_ROOT / name
        if p.exists():
            return p
    return None


DEFAULT_GOAL_ESR = 0.0005  # A2-Lite studio reference early-stopping target (~ -33 dB ESR)
DEFAULT_MAX_EPOCHS = 500  # A2-Lite studio reference epoch safety ceiling
DEFAULT_BATCH_SIZE = 32  # Standard batch size for high GPU core utilization
CANONICAL_SWEEP_PATH = AUDIO_DIR / "canonical" / "canonical_sweep.wav"


def configure_a2_architecture(nam_core: Any, a2_full: bool = False) -> None:
    """Configure NAM Architecture 2 packed model submodels.

    By default, isolates channels_8 (A2-Lite), providing 2x faster iteration
    and preventing the 3-channel submodel from inflating reported ESR and blocking early stopping.
    If a2_full is True, retains all submodels (channels_3 + channels_8).
    """
    if a2_full:
        if hasattr(nam_core, "_orig_get_packed_model_config"):
            nam_core._get_packed_model_config = nam_core._orig_get_packed_model_config
        return
    orig_get_packed_model_config = getattr(
        nam_core, "_orig_get_packed_model_config", nam_core._get_packed_model_config
    )
    nam_core._orig_get_packed_model_config = orig_get_packed_model_config

    def get_lite_only_packed_model_config() -> dict[str, Any]:
        cfg: dict[str, Any] = orig_get_packed_model_config()
        cfg["net"]["config"]["submodels"] = [
            s for s in cfg["net"]["config"]["submodels"] if s["name"] == "channels_8"
        ]
        return cfg

    nam_core._get_packed_model_config = get_lite_only_packed_model_config


def train_voice(
    instrument: str | InstrumentConfig = "30in",
    voice: str = "04_modern_p_ceramic",
    input_wav: str | Path | None = None,
    output_wav: str | Path | None = None,
    models_dir: str | Path = MODELS_DIR,
    tier: str | None = None,
    epochs: int = DEFAULT_MAX_EPOCHS,
    goal_esr: float | None = DEFAULT_GOAL_ESR,
    batch_size: int = DEFAULT_BATCH_SIZE,
    silent: bool = True,
    save_plot: bool = False,
    fast_dev_run: bool = False,
    basename: str | None = None,
    a2_full: bool = False,
    t3k_pack: bool = False,
) -> bool:
    try:
        import nam.train.core as nam_core
        import nam.train.metadata as train_meta
        from nam.models.metadata import UserMetadata

        configure_a2_architecture(nam_core, a2_full=a2_full)
    except ImportError:
        print("Error: 'neural-amp-modeler' is not installed in the current environment.")
        print("Please run `uv sync` or install project dependencies:")
        print(f"  uv run python main.py --stage train --voice {voice}")
        return False

    if voice not in VOICES:
        raise KeyError(f"Target voice '{voice}' not found in catalog.")
    vcfg = VOICES[voice]
    voice_name = vcfg.name

    if not basename and t3k_pack:
        try:
            inst_cfg_tmp = (
                instrument
                if isinstance(instrument, InstrumentConfig)
                else load_instrument(instrument)
            )
            if len(inst_cfg_tmp.pickups) <= 1:
                pos_name = None
            else:
                pcfg = get_source_pickup(inst_cfg_tmp, voice)
                pos_name = pcfg.position_name or pcfg.name
        except (FileNotFoundError, KeyError, ValueError, OSError):
            pos_name = None
        tone_name = vcfg.tone_name or vcfg.name
        from allomorph.naming import get_t3k_basename

        basename = get_t3k_basename(tone_name, pos_name)

    if basename:
        model_basename = basename
        try:
            inst_cfg = load_instrument(instrument)
            inst_id = inst_cfg.id
            inst_name = inst_cfg.name
            scale_length_in = inst_cfg.scale_length_in or 34.0
            src_pickup = get_source_pickup(inst_cfg, voice)
            src_pickup_name = src_pickup.name
            src_pos_mm = (src_pickup.position_from_bridge_m or 0.0) * 1000.0
        except FileNotFoundError, KeyError, ValueError, OSError:
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
        output_path = (
            Path(output_wav)
            if output_wav
            else (AUDIO_DIR / "baked" / inst_id / f"{model_basename}.wav")
        )
    elif tier:
        tier_spec = get_tier_spec(tier)
        folder_name, prefix = tier_spec.folder_name, tier_spec.prefix
        slug = VOICE_CONCISE_SLUGS.get(voice, voice)
        model_basename = f"{prefix}{slug}"
        inst_models_dir = Path(models_dir) / folder_name
        inst_models_dir.mkdir(parents=True, exist_ok=True)
        target_nam = inst_models_dir / f"{model_basename}.nam"
        input_path = find_sweep_input(input_wav)
        output_path = (
            Path(output_wav)
            if output_wav
            else (AUDIO_DIR / "targets" / folder_name / f"out_{voice}.wav")
        )
        try:
            inst_cfg = load_instrument("canonical_intermediate")
        except FileNotFoundError, KeyError, ValueError, OSError:
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
        src_pickup = inst_cfg.pickups.get("canonical_median") or PickupConfig(
            name="93.5mm Canonical Median", position_from_bridge_m=0.0935
        )
        src_pickup_name = "93.5mm Canonical Median"
        src_pos_mm = 93.5
    else:
        inst_cfg = load_instrument(instrument)
        inst_id = inst_cfg.id
        inst_name = inst_cfg.name
        scale_length_in = inst_cfg.scale_length_in or 34.0

        src_pickup = get_source_pickup(inst_cfg, voice)
        src_pickup_name = src_pickup.name
        src_pos_mm = (src_pickup.position_from_bridge_m or 0.0) * 1000.0

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
        if tier:
            from allomorph.circuit.staging import simulate_backend_targets

            print(f"[Train NAM] Target audio missing. Simulating: {output_path.name}...")
            simulate_backend_targets(tier=tier, voice_id=voice)
        else:
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
    print(f'  Source Bass: {inst_name} ({inst_id}, {scale_length_in}")')
    print(f"  Source PU:   {src_pickup_name} (pos={src_pos_mm:.1f}mm)")
    print(f"  Target Voice:{voice} ({voice_name})")
    arch_display = (
        "Architecture 2 Full (channels_3 + channels_8, slimmable)"
        if a2_full
        else "Architecture 2 Lite (channels_8 only, fast)"
    )
    print(f"  Model Tier:  {arch_display}")
    print(f"  Batch Size:  {batch_size}")
    print(f"  Input Audio: {input_path.name}")
    print(f"  Output Audio:{output_path.name}")
    print(f"  Max Epochs:  {epochs}")
    esr_display = (
        f"{threshold_esr:.6f} (A2-Lite Studio Reference Early Stopping)"
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
    nam_meta = NamExportMetadata(
        training=NamTrainingMetadata.model_validate(train_output.metadata.model_dump()),
        license="PolyForm Noncommercial License 1.0.0 (https://polyformproject.org/licenses/noncommercial/1.0.0)",
        copyright="Copyright 2026 Peter Nguyen <peter@phn.dev>. All commercial rights reserved.",
        author="Peter Nguyen <peter@phn.dev>",
        source_instrument=NamSourceInstrumentMeta(
            id=inst_id,
            name=inst_name,
            scale_length_in=scale_length_in,
            scale_length_m=inst_cfg.scale_length_m,
            string_wave_speeds=inst_cfg.string_wave_speeds,
            pickup=NamSourcePickupMeta(
                id=src_pickup.id or "",
                name=src_pickup_name,
                position_from_bridge_m=src_pickup.position_from_bridge_m or 0.0,
                position_from_bridge_mm=src_pos_mm,
                aperture_width_in=src_pickup.aperture_width_in,
                coil_spacing_in=src_pickup.coil_spacing_in,
                type=src_pickup.type,
            ),
        ),
        target_voice=NamTargetVoiceMeta(
            id=voice,
            name=voice_name,
            topology=vcfg.topology,
            resonant_frequency_hz=float(vcfg.fr),
            q_factor=float(vcfg.Q),
            target_position_34_m=compute_effective_position(resolve_voice_coils(vcfg)),
            effective_position_m=compute_effective_position(resolve_voice_coils(vcfg)),
            pickups=resolve_voice_pickups(vcfg),
            coils=resolve_voice_coils(vcfg),
            circuit=vcfg.circuit,
        ),
    )
    meta_dump = nam_meta.model_dump()
    other_metadata = {
        train_meta.TRAINING_KEY: meta_dump["training"],
        "license": meta_dump["license"],
        "copyright": meta_dump["copyright"],
        "author": meta_dump["author"],
        "source_instrument": meta_dump["source_instrument"],
        "target_voice": meta_dump["target_voice"],
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


def train_frontend(
    instrument: str | InstrumentConfig = "30in",
    pickup: str | None = None,
    input_wav: str | Path | None = None,
    output_wav: str | Path | None = None,
    models_dir: str | Path = MODELS_FRONTENDS_DIR,
    epochs: int = DEFAULT_MAX_EPOCHS,
    goal_esr: float | None = DEFAULT_GOAL_ESR,
    batch_size: int = DEFAULT_BATCH_SIZE,
    silent: bool = True,
    save_plot: bool = False,
    fast_dev_run: bool = False,
    basename: str | None = None,
    normalize: bool = False,
    gain_db: float = 0.0,
    a2_full: bool = False,
) -> bool:
    try:
        import nam.train.core as nam_core
        import nam.train.metadata as train_meta
        from nam.models.metadata import UserMetadata

        configure_a2_architecture(nam_core, a2_full=a2_full)
    except ImportError:
        print("Error: 'neural-amp-modeler' is not installed in the current environment.")
        return False

    inst_cfg = load_instrument(instrument) if isinstance(instrument, str) else instrument
    inst_id = inst_cfg.id
    inst_name = inst_cfg.name
    scale_length_in = inst_cfg.scale_length_in or 34.0

    pickups_dict = inst_cfg.pickups
    if pickup and pickup not in ["all", "auto"]:
        if pickup in pickups_dict:
            pickups_to_train = [pickup]
        else:
            matched = [k for k in pickups_dict if k.endswith(pickup) or pickup in k]
            if matched:
                pickups_to_train = [matched[0]]
            else:
                raise KeyError(f"Pickup '{pickup}' not found in instrument '{inst_id}'")
    else:
        pickups_to_train = list(pickups_dict.keys())

    input_path = find_sweep_input(input_wav)
    if not input_path or not input_path.exists():
        print(f"Error: Could not find training sweep file '{input_path}'.")
        return False

    p_models = Path(models_dir)
    if p_models.name == "frontends" or str(p_models).endswith("/frontends"):
        inst_models_dir = p_models / inst_id
    else:
        inst_models_dir = p_models / "frontends" / inst_id
    inst_models_dir.mkdir(parents=True, exist_ok=True)

    all_success = True
    for pkey in pickups_to_train:
        pcfg = pickups_dict[pkey]
        pos_mm = (pcfg.position_from_bridge_m or 0.0) * 1000.0
        p_name = (
            pkey[len("mmtw_") :]
            if (inst_id.endswith("mmtw") and pkey.startswith("mmtw_"))
            else pkey
        )
        model_basename = (
            basename if (basename and len(pickups_to_train) == 1) else f"{inst_id}_{p_name}"
        )
        target_nam = inst_models_dir / f"{model_basename}.nam"

        if output_wav and len(pickups_to_train) == 1:
            out_wav_path = Path(output_wav)
        else:
            out_wav_path = AUDIO_DIR / "frontends" / inst_id / f"{inst_id}_{p_name}_wet.wav"

        if not out_wav_path.exists():
            from allomorph.circuit.staging import export_frontend_wet_wav

            print(f"[Train Frontend] Generating missing wet WAV: {out_wav_path.name}...")
            export_frontend_wet_wav(
                inst_id=inst_id,
                pickup_key=pkey,
                input_wav=input_path,
                out_path=out_wav_path,
                normalize=normalize,
                gain_db=gain_db,
            )

        train_work_dir = inst_models_dir / f".train_{model_basename}"
        train_work_dir.mkdir(parents=True, exist_ok=True)

        threshold_esr = None if (goal_esr is not None and goal_esr <= 0) else goal_esr

        print("\n========================================")
        print("  ALLOMORPH NAM FRONTEND TRAINER")
        print(f'  Source Bass:  {inst_name} ({inst_id}, {scale_length_in}")')
        print(f"  Source PU:    {pcfg.name} (pos={pos_mm:.1f}mm)")
        print("  Target:       00_canonical_intermediate (Block 1 Deconvolution)")
        arch_display = (
            "Architecture 2 Full (channels_3 + channels_8, slimmable)"
            if a2_full
            else "Architecture 2 Lite (channels_8 only, fast)"
        )
        print(f"  Model Tier:   {arch_display}")
        print(f"  Batch Size:   {batch_size}")
        print(f"  Input Audio:  {input_path.name}")
        print(f"  Output Audio: {out_wav_path.name}")
        print(f"  Max Epochs:   {epochs}")
        esr_display = (
            f"{threshold_esr:.6f} (A2-Lite Studio Reference Early Stopping)"
            if threshold_esr is not None
            else "Disabled (Fixed Epochs)"
        )
        print(f"  Goal ESR:     {esr_display}")
        print(f"  Destination:  {target_nam}")
        print("========================================\n")

        model_title = f"{inst_name} ({pcfg.name}) Frontend Deconvolution"
        user_metadata = UserMetadata(
            name=model_title,
            modeled_by="Allomorph (Peter Nguyen <peter@phn.dev>)",
            gear_make=inst_name,
            gear_model=f"Block 1 Frontend ({pcfg.name})",
            gear_type="preamp",
            tone_type="clean",
        )

        print("Validating dataset and calibration markers...")
        train_output = nam_core.train(
            input_path=str(input_path),
            output_path=str(out_wav_path),
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
            print(f"Error: Training did not produce a model for {inst_id} ({pkey}).")
            all_success = False
            continue

        print("\nExporting Architecture 2 (.nam) model container with full instrument metadata...")
        nam_meta = NamExportMetadata(
            training=NamTrainingMetadata.model_validate(train_output.metadata.model_dump()),
            license="PolyForm Noncommercial License 1.0.0 (https://polyformproject.org/licenses/noncommercial/1.0.0)",
            copyright="Copyright 2026 Peter Nguyen <peter@phn.dev>. All commercial rights reserved.",
            author="Peter Nguyen <peter@phn.dev>",
            source_instrument=NamSourceInstrumentMeta(
                id=inst_id,
                name=inst_name,
                scale_length_in=scale_length_in,
                scale_length_m=inst_cfg.scale_length_m,
                string_wave_speeds=inst_cfg.string_wave_speeds,
                pickup=NamSourcePickupMeta(
                    id=pcfg.id or pkey,
                    name=pcfg.name,
                    position_from_bridge_m=pcfg.position_from_bridge_m or 0.0,
                    position_from_bridge_mm=pos_mm,
                    aperture_width_in=pcfg.aperture_width_in,
                    coil_spacing_in=pcfg.coil_spacing_in,
                    type=pcfg.type,
                ),
            ),
            target_voice=NamTargetVoiceMeta(
                id="00_canonical_intermediate",
                name="Canonical Intermediate Datum (34in @ 93.5mm)",
                topology="single_coil",
                resonant_frequency_hz=4800.0,
                q_factor=0.707,
                target_position_34_m=0.0935,
                effective_position_m=0.0935,
                pickups=[],
                coils=[],
                circuit=None,
            ),
        )
        meta_dump = nam_meta.model_dump()
        other_metadata = {
            train_meta.TRAINING_KEY: meta_dump["training"],
            "license": meta_dump["license"],
            "copyright": meta_dump["copyright"],
            "author": meta_dump["author"],
            "source_instrument": meta_dump["source_instrument"],
            "target_voice": meta_dump["target_voice"],
        }

        export_net: Any = train_output.model.net
        export_net.export(
            str(inst_models_dir),
            basename=model_basename,
            user_metadata=user_metadata,
            other_metadata=other_metadata,
        )

        if train_work_dir.exists():
            shutil.rmtree(train_work_dir, ignore_errors=True)

        if target_nam.exists():
            size_kb = target_nam.stat().st_size / 1024
            print("\n[Success] Architecture 2 Model exported successfully!")
            print(f"  Model Path:    {target_nam} ({size_kb:.1f} KB)")
            print(f"  Model Title:   {model_title}")
            print(f"  Source Bass:   {inst_name}")
            print(f"  Source Pickup: {pcfg.name} ({pos_mm:.1f}mm)")
            print("  Ready for Darkglass Anagram Block 1 (Preamp) loading.")
        else:
            print(f"Warning: Expected model file at {target_nam} not found.")
            all_success = False

    return all_success


def main():
    parser = argparse.ArgumentParser(description="Allomorph NAM Architecture 2 Local Trainer")
    parser.add_argument(
        "--instrument",
        "-i",
        default="all",
        help="Source instrument configuration (ID, comma-separated list, 'all', path to .toml, or alias like 30in, 32in; default: 'all')",
    )
    parser.add_argument(
        "--voice",
        default="all",
        help="Target pickup voice (ID, comma-separated list, or 'all'; default: 'all')",
    )
    parser.add_argument(
        "--frontend",
        action="store_true",
        help="Train NAM neural model on Block 1 frontend deconvolution wet WAVs instead of target voices",
    )
    parser.add_argument(
        "--pickup",
        "-p",
        default=None,
        help="Physical pickup setting for source instrument (default: all pickups on the instrument)",
    )
    parser.add_argument(
        "--normalize-frontend",
        action="store_true",
        default=False,
        help="Enable full-scale peak normalization for frontend wet audio synthesis (default: False for unnormalized unity gain)",
    )
    parser.add_argument(
        "--gain-db",
        type=float,
        default=0.0,
        help="Optional manual gain trim in dB for frontend wet audio synthesis (default: 0.0 dB)",
    )
    parser.add_argument(
        "--input", help="Path to dry training sweep WAV (default: auto-detect T3K-sweep-v3.wav)"
    )
    parser.add_argument(
        "--output", help="Path to simulated SPICE output WAV (default: circuits/out_<voice>.wav)"
    )
    parser.add_argument("--models-dir", default=str(MODELS_DIR), help="Output models directory")
    parser.add_argument(
        "--epochs",
        type=int,
        default=DEFAULT_MAX_EPOCHS,
        help=f"Maximum number of training epochs (default: {DEFAULT_MAX_EPOCHS} for A2-Lite studio reference)",
    )
    parser.add_argument(
        "--goal-esr",
        type=float,
        default=DEFAULT_GOAL_ESR,
        help=f"Goal validation ESR for early stopping (default: {DEFAULT_GOAL_ESR} for A2-Lite studio reference; set to 0 to disable)",
    )
    parser.add_argument(
        "--no-goal-esr",
        action="store_true",
        help="Disable goal ESR early stopping and train for the exact number of epochs specified",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Batch size (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--a2-full",
        action="store_true",
        help="Train full slimmable Architecture 2 container with both channels_3 and channels_8 (default: False, trains A2-Lite channels_8 only for 2x faster throughput and unskewed ESR)",
    )
    parser.add_argument(
        "--show-plot", action="store_true", help="Display matplotlib validation plot window"
    )
    parser.add_argument(
        "--save-plot", action="store_true", help="Save validation plot as PNG in models/"
    )
    parser.add_argument(
        "--tier",
        choices=["clean", "standard", "std", "hotrod", "dynamic"],
        default=None,
        help="Dynamic tier: 'standard' / 'std' (100%% nominal target saturation), 'clean' (0%% saturation), 'hotrod' (175%% overwound), 'dynamic' (differential source/target saturation).",
    )
    parser.add_argument("--basename", help="Explicit basename for the exported .nam model file")
    parser.add_argument(
        "--t3k-pack",
        action="store_true",
        help="Export model file formatted as 'Tone Name [Pickup Position]' (max 34 chars)",
    )
    parser.add_argument(
        "--fast-dev-run",
        action="store_true",
        help="Run 1-batch dry run for smoke testing NAM training",
    )
    parser.add_argument("--gui", action="store_true", help="Launch NAM training GUI")
    args = parser.parse_args()

    cli_cfg = NamTrainingConfig.model_validate(
        {
            "instrument": args.instrument,
            "voice": args.voice,
            "input_wav": args.input,
            "output_wav": args.output,
            "models_dir": args.models_dir,
            "epochs": args.epochs,
            "goal_esr": args.goal_esr,
            "no_goal_esr": args.no_goal_esr,
            "batch_size": args.batch_size,
            "show_plot": args.show_plot,
            "save_plot": args.save_plot,
            "tier": args.tier,
            "basename": args.basename,
            "fast_dev_run": args.fast_dev_run,
            "gui": args.gui,
            "a2_full": args.a2_full,
            "t3k_pack": args.t3k_pack,
        }
    )

    if cli_cfg.gui:
        try:
            from nam.cli import nam_gui

            nam_gui()
            return
        except ImportError:
            print("Error: 'neural-amp-modeler' GUI could not be loaded.")
            return

    effective_goal_esr = (
        None
        if cli_cfg.no_goal_esr or (cli_cfg.goal_esr is not None and cli_cfg.goal_esr <= 0)
        else cli_cfg.goal_esr
    )

    if args.frontend:
        instruments_to_run = resolve_instruments(cli_cfg.instrument)
        all_ok = True
        for inst in instruments_to_run:
            ok = train_frontend(
                instrument=inst,
                pickup=args.pickup,
                input_wav=cli_cfg.input_wav,
                output_wav=cli_cfg.output_wav,
                models_dir=cli_cfg.models_dir,
                epochs=cli_cfg.epochs,
                goal_esr=effective_goal_esr,
                batch_size=cli_cfg.batch_size,
                silent=not cli_cfg.show_plot,
                save_plot=cli_cfg.save_plot,
                fast_dev_run=cli_cfg.fast_dev_run,
                basename=cli_cfg.basename,
                normalize=args.normalize_frontend,
                gain_db=args.gain_db,
                a2_full=cli_cfg.a2_full,
            )
            if not ok:
                all_ok = False
        if not all_ok:
            sys.exit(1)
        return

    if cli_cfg.tier and cli_cfg.instrument == "all":
        instruments_to_run = ["canonical_intermediate"]
    else:
        instruments_to_run = resolve_instruments(cli_cfg.instrument)
    voices_to_run = resolve_voices(cli_cfg.voice)
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
            out_wav = (
                cli_cfg.output_wav
                if (len(voices_to_run) == 1 and len(instruments_to_run) == 1)
                else None
            )
            ok = train_voice(
                instrument=inst,
                voice=voice,
                input_wav=cli_cfg.input_wav,
                output_wav=out_wav,
                models_dir=cli_cfg.models_dir,
                tier=cli_cfg.tier,
                epochs=cli_cfg.epochs,
                goal_esr=effective_goal_esr,
                batch_size=cli_cfg.batch_size,
                silent=not cli_cfg.show_plot,
                save_plot=cli_cfg.save_plot,
                fast_dev_run=cli_cfg.fast_dev_run,
                basename=cli_cfg.basename
                if (len(voices_to_run) == 1 and len(instruments_to_run) == 1)
                else None,
                a2_full=cli_cfg.a2_full,
                t3k_pack=cli_cfg.t3k_pack,
            )
            if not ok:
                all_ok = False

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()

