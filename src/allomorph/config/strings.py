"""
Physical string catalog presets and instrument/voice string configuration resolution.
"""

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
STRINGS_FILE = CONFIG_DIR / "strings.toml"


from allomorph.config.schema import (
    AllomorphBaseModel,
    ResolvedStringConfig,
    StringPresetConfig,
    StringsCatalog,
)


def load_strings_config(config_path: str | Path | None = None) -> dict[str, StringPresetConfig]:
    """Loads physical string catalog from TOML into validated StringPresetConfig models."""
    path = Path(config_path) if config_path else STRINGS_FILE
    if not path.exists():
        empty_res: dict[str, StringPresetConfig] = {}
        return empty_res
    with open(path, "rb") as f:
        data = tomllib.load(f)
    catalog = StringsCatalog.model_validate(data)
    return catalog.strings


STRINGS: dict[str, StringPresetConfig] = load_strings_config()


def get_instrument_string(
    instrument: dict[str, Any] | AllomorphBaseModel | str | None = None,
) -> ResolvedStringConfig:
    """Resolves string configuration for a source instrument."""
    if instrument is None:
        from allomorph.config.instruments import load_instrument

        inst: dict[str, Any] | AllomorphBaseModel = load_instrument("30in")
    elif isinstance(instrument, str):
        from allomorph.config.instruments import load_instrument

        inst = load_instrument(instrument)
    else:
        inst = instrument

    s_block = inst.get("strings", {}) if hasattr(inst, "get") else getattr(inst, "strings", {})
    preset = s_block.get("preset", "roundwound_nickel_standard") if hasattr(s_block, "get") else getattr(s_block, "preset", "roundwound_nickel_standard")

    if preset not in STRINGS:
        raise KeyError(
            f"String preset '{preset}' not found in strings catalog ({STRINGS_FILE}). "
            f"Available presets: {list(STRINGS.keys())}"
        )

    base_dict = STRINGS[preset].model_dump()
    s_dict: dict[str, Any] = s_block.model_dump() if hasattr(s_block, "model_dump") else (dict(s_block) if isinstance(s_block, dict) else {})
    base_dict.update({k: v for k, v in s_dict.items() if v is not None})
    return ResolvedStringConfig.model_validate(base_dict)


def get_voice_string(voice_cfg: dict[str, Any] | AllomorphBaseModel) -> StringPresetConfig:
    """Resolves target string configuration for a target voice."""
    preset = voice_cfg.get("target_string") if hasattr(voice_cfg, "get") else getattr(voice_cfg, "target_string", None)
    if not preset:
        preset = "roundwound_nickel_standard"

    if preset not in STRINGS:
        raise KeyError(
            f"String preset '{preset}' not found in strings catalog ({STRINGS_FILE}). "
            f"Available presets: {list(STRINGS.keys())}"
        )
    return STRINGS[preset]
