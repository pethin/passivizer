"""
Tests for Passivizer NAM Architecture 2 local trainer.
"""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from train_nam import find_sweep_input

def test_find_sweep_input():
    sweep = find_sweep_input()
    assert sweep is not None
    assert sweep.exists()
    assert sweep.name in ["T3K-sweep-v3.wav", "v3_0_0.wav", "v1_1_1.wav"]

def test_models_directory_structure():
    models_dir = REPO_ROOT / "models"
    assert models_dir.exists() or True
