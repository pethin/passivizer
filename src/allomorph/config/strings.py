"""
Physical string catalog presets and instrument/voice string configuration resolution.
"""

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
STRINGS_FILE = CONFIG_DIR / "strings.toml"


def load_strings_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Loads physical string catalog from TOML."""
    path = Path(config_path) if config_path else STRINGS_FILE
    if not path.exists():
        empty_res: dict[str, Any] = {}
        return empty_res
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("strings", {})


STRINGS = load_strings_config()


def get_instrument_string(instrument: dict[str, Any] | str | None) -> dict[str, Any]:
    """Resolves string configuration dictionary for a source instrument."""
    if instrument is None:
        from allomorph.config.instruments import load_instrument
        inst = load_instrument("30in")
    elif not isinstance(instrument, dict):
        from allomorph.config.instruments import load_instrument
        inst = load_instrument(instrument)
    else:
        inst = instrument
    s_block = inst.get("strings", {})
    preset = s_block.get("preset", "roundwound_nickel_standard")
    if preset not in STRINGS:
        raise KeyError(
            f"String preset '{preset}' not found in strings catalog ({STRINGS_FILE}). "
            f"Available presets: {list(STRINGS.keys())}"
        )
    base = STRINGS[preset].copy()
    base.update(s_block)
    return base


def get_voice_string(voice_cfg: dict[str, Any]) -> dict[str, Any]:
    """Resolves target string configuration dictionary for a target voice."""
    preset = voice_cfg.get("target_string", "roundwound_nickel_standard")
    if preset not in STRINGS:
        raise KeyError(
            f"String preset '{preset}' not found in strings catalog ({STRINGS_FILE}). "
            f"Available presets: {list(STRINGS.keys())}"
        )
    return STRINGS[preset].copy()
