"""
Physical string catalog presets and instrument/voice string configuration resolution.
"""

from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
STRINGS_FILE = CONFIG_DIR / "strings.toml"


def load_strings_config(config_path=None):
    """Loads physical string catalog from TOML."""
    path = Path(config_path) if config_path else STRINGS_FILE
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return data.get("strings", {})


STRINGS = load_strings_config()


def get_instrument_string(instrument):
    """Resolves string configuration dictionary for a source instrument."""
    if not isinstance(instrument, dict):
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


def get_voice_string(voice_cfg):
    """Resolves target string configuration dictionary for a target voice."""
    preset = voice_cfg.get("target_string", "roundwound_nickel_standard")
    if preset not in STRINGS:
        raise KeyError(
            f"String preset '{preset}' not found in strings catalog ({STRINGS_FILE}). "
            f"Available presets: {list(STRINGS.keys())}"
        )
    return STRINGS[preset].copy()
