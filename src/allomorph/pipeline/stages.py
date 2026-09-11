"""
Allomorph Pipeline - Execution Stages
Individual execution stages for visualization, audio pre-filtering,
circuit simulation, and neural model training.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union, Dict, Any

from allomorph.config import (
    REPO_ROOT,
    VOICES,
    load_instrument,
)
from allomorph.physics import compute_voice_prefilter_firs
from allomorph.circuit import (
    CIRCUITS_DIR,
    AUDIO_DIR,
    MODELS_DIR,
    simulate_voice,
    prefilter_audio,
)

DOCS_DIR = REPO_ROOT / "docs"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEFAULT_LTSPICE_BIN = "/Applications/LTspice.app/Contents/MacOS/LTspice"


def run_visualization(instrument: str = "all"):
    """Generates the interactive Altair visualization charts and master portal."""
    inst_desc = "all instruments" if instrument == "all" else f"Instrument: {instrument}"
    print(f"\n[Stage 1] Generating interactive Altair visualization ({inst_desc})...")
    script = SCRIPTS_DIR / "analyze_voices.py"
    if instrument == "all":
        cmd = [sys.executable, str(script), "--all"]
    else:
        cmd = [sys.executable, str(script), "--instrument", instrument]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Warning: Visualization generation returned non-zero code {res.returncode}")
    else:
        resp_dir = DOCS_DIR / "frequency_responses"
        print(f"Interactive charts generated in {resp_dir}/")
        print(f"Master interactive portal updated at {DOCS_DIR / 'frequency_responses.html'}")


def run_prep_audio(input_wav: Optional[Union[str, Path]] = None, instrument: str = "30in", voice: str = "04_modern_p_ceramic"):
    """Pre-filters NAM calibration audio through acoustic and spatial transfer functions in-process."""
    input_path = Path(input_wav) if input_wav else None
    if not input_path or not input_path.exists():
        for candidate in ["T3K-sweep-v3.wav", "v3_0_0.wav", "input.wav"]:
            p = REPO_ROOT / candidate
            if p.exists():
                input_path = p
                break

    if not input_path or not input_path.exists():
        print("Notice: Audio calibration sweep not found.")
        return

    inst_cfg = load_instrument(instrument) if not isinstance(instrument, dict) else instrument
    inst_id = inst_cfg.get("id", "30in_emg_mmtw")
    inst_audio_dir = AUDIO_DIR / inst_id
    inst_audio_dir.mkdir(parents=True, exist_ok=True)

    out_path = inst_audio_dir / f"aperture_{voice}.wav"
    firs = compute_voice_prefilter_firs(voice, instrument=instrument)
    ch_desc = f"{len(firs)} channels" if len(firs) > 1 else "1 channel"
    print(f"\n[Prep Audio] Pre-filtering ({ch_desc}) for {voice} (Instrument: {inst_id}, Input: {input_path.name})...")
    prefilter_audio(input_path, out_path, firs)


def run_circuit_simulation(
    voice: str,
    instrument: str = "30in",
    input_wav: Optional[Union[str, Path]] = None,
    backend: str = "native",
    ltspice_bin: str = DEFAULT_LTSPICE_BIN,
    max_samples: Optional[int] = None,
) -> bool:
    """Executes circuit simulation for a single target voice netlist."""
    if backend == "native":
        try:
            return simulate_voice(voice, input_wav=input_wav, instrument=instrument, prefiltered=False, max_samples=max_samples)
        except Exception as e:
            print(f"Error during native circuit simulation: {e}")
            return False

    # LTspice backend requires intermediate aperture audio on disk
    run_prep_audio(input_wav=input_wav, instrument=instrument, voice=voice)
    if not os.path.exists(ltspice_bin):
        print(f"Notice: LTspice executable not found at '{ltspice_bin}'. Falling back to native VA backend.")
        return simulate_voice(voice, input_wav=input_wav, instrument=instrument, prefiltered=False, max_samples=max_samples)

    vcfg = VOICES.get(voice, {})
    cir_rel = vcfg.get("circuit", f"circuits/{voice}.cir")
    cir_path = REPO_ROOT / cir_rel
    if not cir_path.exists():
        cir_path = CIRCUITS_DIR / f"{voice}.cir"
    if not cir_path.exists():
        print(f"Warning: Netlist '{cir_path.name}' not found.")
        return False

    input_aperture = AUDIO_DIR / instrument / f"aperture_{voice}.wav"
    if not input_aperture.exists():
        input_aperture = CIRCUITS_DIR / "aperture.wav"
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


def run_spice_voice(
    voice: str,
    instrument: str = "30in",
    input_wav: Optional[Union[str, Path]] = None,
    ltspice_bin: str = DEFAULT_LTSPICE_BIN,
    backend: str = "native",
    max_samples: Optional[int] = None,
) -> bool:
    """Legacy alias for run_circuit_simulation."""
    return run_circuit_simulation(voice, instrument=instrument, input_wav=input_wav, backend=backend, ltspice_bin=ltspice_bin, max_samples=max_samples)


def run_training(
    instrument: str = "30in",
    voice: str = "04_modern_p_ceramic",
    input_wav: Optional[Union[str, Path]] = None,
    output_wav: Optional[Union[str, Path]] = None,
    models_dir: Optional[Union[str, Path]] = None,
    tier: Optional[str] = None,
    epochs: int = 100,
    goal_esr: Optional[float] = 0.0005,
    fast_dev_run: bool = False,
    basename: Optional[str] = None,
):
    """Trains a Neural Amp Modeler (NAM) Architecture 2 model locally with MPS GPU acceleration."""
    print(f"\n[Training] Training Neural Amp Modeler A2 model for {voice} (Instrument: {instrument})...")
    script = SCRIPTS_DIR / "train_nam.py"
    cmd = [
        sys.executable, str(script),
        "--instrument", instrument,
        "--voice", voice,
        "--epochs", str(epochs),
    ]
    if tier:
        cmd.extend(["--tier", tier])
    if output_wav:
        cmd.extend(["--output", str(output_wav)])
    if models_dir:
        cmd.extend(["--models-dir", str(models_dir)])
    if basename:
        cmd.extend(["--basename", basename])
    if goal_esr is not None and goal_esr > 0:
        cmd.extend(["--goal-esr", str(goal_esr)])
    else:
        cmd.append("--no-goal-esr")
    if input_wav:
        cmd.extend(["--input", str(input_wav)])
    if fast_dev_run:
        cmd.append("--fast-dev-run")
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if res.returncode != 0:
        print(f"Notice: Model training exited with code {res.returncode}")
