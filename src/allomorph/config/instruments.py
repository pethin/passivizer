"""
Source instrument configuration loading, alias resolution, and pickup lookup.
"""

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
INSTRUMENTS_DIR = CONFIG_DIR / "instruments"

INSTRUMENT_ALIASES = {
    "30in": "30in_emg_mmtw",
    "30in_mm": "30in_emg_mmtw",
    "30in_mmtw": "30in_emg_mmtw",
    "30in_emg_mm": "30in_emg_mmtw",
    "30in_emg_mmtw": "30in_emg_mmtw",
    "32in": "32in_custom_pmm",
    "32in_fretless": "32in_fretless_pmm",
    "fretless": "32in_fretless_pmm",
    "34in": "34in_standard_p",
    "standard_p": "34in_standard_p",
    "34in_standard_jazz": "34in_standard_jazz",
    "standard_jazz": "34in_standard_jazz",
    "34in_standard_pj": "34in_standard_pj",
    "standard_pj": "34in_standard_pj",
    "34in_pj": "34in_standard_pj",
    "pj": "34in_standard_pj",
    "34in_active_stingray": "34in_active_stingray",
    "active_stingray": "34in_active_stingray",
    "stingray": "34in_active_stingray",
    "ray": "34in_active_stingray",
    "34in_active_soapbar": "34in_active_soapbar",
    "active_soapbar": "34in_active_soapbar",
    "soapbar": "34in_active_soapbar",
    "30in_mustang_pj": "30in_mustang_pj",
    "mustang_pj": "30in_mustang_pj",
    "30in_mustang": "30in_mustang_pj",
    "mustang": "30in_mustang_pj",
    "30in_standard_mustang": "30in_mustang_pj",
    "standard_mustang": "30in_mustang_pj",
    "37in_multiscale_dingwall": "37in_multiscale_dingwall",
    "multiscale_dingwall": "37in_multiscale_dingwall",
    "dingwall": "37in_multiscale_dingwall",
    "combustion": "37in_multiscale_dingwall",
    "ng": "37in_multiscale_dingwall",
    "dingwall_ng": "37in_multiscale_dingwall",
    "ng2": "37in_multiscale_dingwall",
    "ng3": "37in_multiscale_dingwall",
    "37in_dingwall_ng": "37in_multiscale_dingwall",
    "34in_dingwall_sp1": "34in_dingwall_sp1",
    "35in_dingwall_sp1": "34in_dingwall_sp1",
    "dingwall_sp1": "34in_dingwall_sp1",
    "sp1": "34in_dingwall_sp1",
    "super_p": "34in_dingwall_sp1",
    "dingwall_super_p": "34in_dingwall_sp1",
    "canonical": "canonical_intermediate",
    "canonical_intermediate": "canonical_intermediate",
}


from allomorph.config.schema import AllomorphBaseModel, InstrumentConfig, PickupConfig


def load_instrument(identifier_or_path: str | Path | dict[str, Any] | AllomorphBaseModel) -> InstrumentConfig:
    """
    Loads and validates an instrument configuration from a file path, known ID, shorthand alias, or dict.
    Aliases: '30in' -> '30in_emg_mmtw', '32in' -> '32in_custom_pmm', '34in' -> '34in_standard_p'.
    """
    if isinstance(identifier_or_path, InstrumentConfig):
        return identifier_or_path

    if isinstance(identifier_or_path, dict):
        return InstrumentConfig.model_validate(identifier_or_path)

    raw = str(identifier_or_path).strip()
    key = INSTRUMENT_ALIASES.get(raw, raw)

    path = Path(key)
    if not path.exists():
        if (INSTRUMENTS_DIR / f"{key}.toml").exists():
            path = INSTRUMENTS_DIR / f"{key}.toml"
        elif (INSTRUMENTS_DIR / key).exists():
            path = INSTRUMENTS_DIR / key
        elif (CONFIG_DIR / f"{key}.toml").exists():
            path = CONFIG_DIR / f"{key}.toml"
        else:
            raise FileNotFoundError(f"Instrument configuration not found: '{identifier_or_path}' (searched in {INSTRUMENTS_DIR})")

    with open(path, "rb") as f:
        data = tomllib.load(f)
    return InstrumentConfig.model_validate(data)


def load_all_instruments(instruments_dir: str | Path | None = None) -> dict[str, InstrumentConfig]:
    """Loads all instrument definitions found in instruments_dir into validated InstrumentConfig models."""
    idir = Path(instruments_dir) if instruments_dir else INSTRUMENTS_DIR
    instruments: dict[str, InstrumentConfig] = {}
    if idir.exists():
        for p in sorted(idir.glob("*.toml")):
            with open(p, "rb") as f:
                cfg = tomllib.load(f)
                inst = InstrumentConfig.model_validate(cfg)
                instruments[inst.id] = inst
    return instruments


INSTRUMENTS: dict[str, InstrumentConfig] = load_all_instruments()


def get_source_pickup(instrument: dict[str, Any] | AllomorphBaseModel, voice_id: str) -> PickupConfig:
    """
    Determines which pickup on the source instrument should be used for the target voice.
    Checks explicit pickup_mapping, falls back to default_pickup, or raises diagnostic error.
    """
    pickups = instrument.get("pickups", {}) if hasattr(instrument, "get") else getattr(instrument, "pickups", {})
    if not pickups:
        inst_id = instrument.get("id", "unknown") if hasattr(instrument, "get") else getattr(instrument, "id", "unknown")
        raise ValueError(f"Instrument '{inst_id}' has no pickups defined.")

    # 1. Explicit voice mapping
    mapping = instrument.get("pickup_mapping", {}) if hasattr(instrument, "get") else getattr(instrument, "pickup_mapping", {})
    if voice_id in mapping and mapping[voice_id] in pickups:
        p_raw = pickups[mapping[voice_id]]
        if isinstance(p_raw, PickupConfig):
            p = p_raw.model_copy(deep=True)
            p.id = mapping[voice_id]
            return p
        p = PickupConfig.model_validate(p_raw)
        p.id = mapping[voice_id]
        return p

    # 2. Default pickup declared on instrument
    default_key = instrument.get("default_pickup") if hasattr(instrument, "get") else getattr(instrument, "default_pickup", None)
    if default_key:
        if default_key in pickups:
            p_raw = pickups[default_key]
            if isinstance(p_raw, PickupConfig):
                p = p_raw.model_copy(deep=True)
                p.id = default_key
                return p
            p = PickupConfig.model_validate(p_raw)
            p.id = default_key
            return p
        inst_id = instrument.get("id", "unknown") if hasattr(instrument, "get") else getattr(instrument, "id", "unknown")
        raise KeyError(
            f"Instrument '{inst_id}' default_pickup '{default_key}' "
            f"not found in pickups: {list(pickups.keys())}"
        )

    inst_id = instrument.get("id", "unknown") if hasattr(instrument, "get") else getattr(instrument, "id", "unknown")
    raise ValueError(
        f"Instrument '{inst_id}' defines no 'default_pickup' "
        f"and has no pickup_mapping for voice '{voice_id}'."
    )
