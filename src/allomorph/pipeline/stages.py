"""
Allomorph Pipeline - Execution Stages
Individual execution stages for visualization, audio pre-filtering,
circuit simulation, and neural model training.
"""

import subprocess
import sys
from pathlib import Path

from allomorph.circuit.simulation import simulate_voice

REPO_ROOT = Path(__file__).resolve().parents[3]

DOCS_DIR = REPO_ROOT / "docs"
SCRIPTS_DIR = REPO_ROOT / "scripts"


def run_visualization(instrument: str = "all"):
    """Generates the interactive Altair visualization charts and master portal."""
    inst_desc = "all instruments" if instrument == "all" else f"Instrument: {instrument}"
    print(f"\n[Stage 1] Generating interactive Altair visualization ({inst_desc})...")
    script = SCRIPTS_DIR / "analyze_voices.py"
    if instrument == "all":
        cmd = [sys.executable, str(script), "--all"]
    else:
        cmd = [sys.executable, str(script), "--instrument", instrument]
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
    if res.returncode != 0:
        print(f"Warning: Visualization generation returned non-zero code {res.returncode}")
    else:
        resp_dir = DOCS_DIR / "frequency_responses"
        print(f"Interactive charts generated in {resp_dir}/")
        print(f"Master interactive portal updated at {DOCS_DIR / 'frequency_responses.html'}")


def run_circuit_simulation(
    voice: str,
    instrument: str = "30in",
    input_wav: str | Path | None = None,
    output_wav: str | Path | None = None,
    backend: str = "native",
    max_samples: int | None = None,
) -> bool:
    """Executes circuit simulation for a single target voice netlist using the native Apple Silicon WAV SPICE engine."""
    if backend != "native":
        raise ValueError(
            f"Unsupported backend '{backend}'. The legacy LTspice pipeline has been removed; "
            "Allomorph uses the built-in native Apple Silicon WAV SPICE engine."
        )
    try:
        return simulate_voice(
            voice,
            input_wav=input_wav,
            output_wav=output_wav,
            instrument=instrument,
            prefiltered=False,
            max_samples=max_samples,
        )
    except (RuntimeError, ValueError, OSError) as e:
        print(f"Error during native circuit simulation: {e}")
        return False


def run_training(
    instrument: str = "30in",
    voice: str = "04_modern_p_ceramic",
    input_wav: str | Path | None = None,
    output_wav: str | Path | None = None,
    models_dir: str | Path | None = None,
    tier: str | None = None,
    epochs: int = 100,
    goal_esr: float | None = 0.0005,
    fast_dev_run: bool = False,
    basename: str | None = None,
):
    """Trains a Neural Amp Modeler (NAM) Architecture 2 model locally with MPS GPU acceleration."""
    print(
        f"\n[Training] Training Neural Amp Modeler A2 model for {voice} (Instrument: {instrument})..."
    )
    script = SCRIPTS_DIR / "train_nam.py"
    cmd = [
        sys.executable,
        str(script),
        "--instrument",
        instrument,
        "--voice",
        voice,
        "--epochs",
        str(epochs),
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
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
    if res.returncode != 0:
        print(f"Notice: Model training exited with code {res.returncode}")
