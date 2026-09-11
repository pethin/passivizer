"""
Reusable onboard active preamps and buffer catalog loader.
"""

import copy
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
PREAMPS_FILE = CONFIG_DIR / "preamps.toml"


def load_preamps_config(config_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Loads active preamps catalog from TOML."""
    path = Path(config_path) if config_path else PREAMPS_FILE
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("preamps", {})


PREAMPS: dict[str, dict[str, Any]] = load_preamps_config()


def get_preamp(preamp_spec: str | dict[str, Any] | None) -> dict[str, Any]:
    """
    Resolves an active preamp configuration.
    Accepts:
      - None or "": returns default flat active buffer with 0 EQ bands.
      - str (preset ID): looks up preset from PREAMPS catalog.
      - dict: if 'preset' in dict, inherits preset and overlays overrides; otherwise returns dict as-is.
    """
    if not preamp_spec:
        return copy.deepcopy(PREAMPS.get("flat_buffer", {
            "name": "Flat Active Buffer",
            "input_impedance_meg": 1.0,
            "output_impedance_ohm": 100.0,
            "gain_db": 0.0,
            "bands": [],
        }))

    if isinstance(preamp_spec, str):
        if preamp_spec in PREAMPS:
            return copy.deepcopy(PREAMPS[preamp_spec])
        raise KeyError(f"Unknown preamp preset '{preamp_spec}'. Available presets: {list(PREAMPS.keys())}")

    if isinstance(preamp_spec, dict):
        res = copy.deepcopy(preamp_spec)
        preset_name = res.get("preset")
        if preset_name and preset_name in PREAMPS:
            base = copy.deepcopy(PREAMPS[preset_name])
            base.update(res)
            return base
        return res

    raise TypeError(f"Invalid preamp specification type: {type(preamp_spec)}")
