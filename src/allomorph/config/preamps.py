"""
Reusable onboard active preamps and buffer catalog loader.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
PREAMPS_FILE = CONFIG_DIR / "preamps.toml"


from allomorph.config.schema import PreampConfig, PreampOverrideConfig, PreampsCatalog


def load_preamps_config(config_path: str | Path | None = None) -> dict[str, PreampConfig]:
    """Loads active preamps catalog from TOML into validated PreampConfig models."""
    path = Path(config_path) if config_path else PREAMPS_FILE
    if not path.exists():
        empty_res: dict[str, PreampConfig] = {}
        return empty_res
    with open(path, "rb") as f:
        data = tomllib.load(f)
    catalog = PreampsCatalog.model_validate(data)
    return catalog.preamps


PREAMPS: dict[str, PreampConfig] = load_preamps_config()


def get_preamp(
    preamp_spec: str | PreampConfig | PreampOverrideConfig | None = None,
) -> PreampConfig:
    """
    Resolves an active preamp configuration into a PreampConfig model.
    Accepts:
      - None, "", or "none": returns default flat active buffer with 0 EQ bands.
      - str (preset ID): looks up preset from PREAMPS catalog.
      - PreampConfig: returns a deep copy.
      - PreampOverrideConfig: inherits preset and overlays typed overrides.
    """
    if not preamp_spec or preamp_spec in ("none", "flat"):
        if "flat_buffer" in PREAMPS:
            return PREAMPS["flat_buffer"].model_copy(deep=True)
        return PreampConfig(
            id="flat_buffer",
            name="Flat Active Buffer",
            input_impedance_meg=1.0,
            output_impedance_ohm=100.0,
            gain_db=0.0,
            bands=[],
        )

    if isinstance(preamp_spec, PreampConfig):
        return preamp_spec.model_copy(deep=True)

    if isinstance(preamp_spec, str):
        if preamp_spec in PREAMPS:
            return PREAMPS[preamp_spec].model_copy(deep=True)
        raise KeyError(
            f"Unknown preamp preset '{preamp_spec}'. Available presets: {list(PREAMPS.keys())}"
        )

    if isinstance(preamp_spec, PreampOverrideConfig):
        preset_name = preamp_spec.preset
        if preset_name in PREAMPS:
            base = PREAMPS[preset_name].model_copy(deep=True)
            if preamp_spec.gain_db is not None:
                base.gain_db = preamp_spec.gain_db
            if preamp_spec.input_impedance_meg is not None:
                base.input_impedance_meg = preamp_spec.input_impedance_meg
            if preamp_spec.output_impedance_ohm is not None:
                base.output_impedance_ohm = preamp_spec.output_impedance_ohm
            if preamp_spec.bands:
                base.bands = [b.model_copy(deep=True) for b in preamp_spec.bands]
            return base
        raise KeyError(
            f"Unknown preamp preset '{preset_name}'. Available presets: {list(PREAMPS.keys())}"
        )

    raise TypeError(f"Invalid preamp specification type: {type(preamp_spec)}")
