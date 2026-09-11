"""
Source instrument configuration loading, alias resolution, and pickup lookup.
"""

from pathlib import Path
import tomllib

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


def load_instrument(identifier_or_path):
    """
    Loads an instrument configuration from a file path, known ID, or shorthand alias.
    Aliases: '30in' -> '30in_emg_mmtw', '32in' -> '32in_custom_pmm', '34in' -> '34in_standard_p'.
    """
    if isinstance(identifier_or_path, dict):
        return identifier_or_path

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
        return tomllib.load(f)


def load_all_instruments(instruments_dir=None):
    """Loads all instrument definitions found in instruments_dir."""
    idir = Path(instruments_dir) if instruments_dir else INSTRUMENTS_DIR
    instruments = {}
    if idir.exists():
        for p in sorted(idir.glob("*.toml")):
            with open(p, "rb") as f:
                cfg = tomllib.load(f)
                inst_id = cfg.get("id", p.stem)
                instruments[inst_id] = cfg
    return instruments


INSTRUMENTS = load_all_instruments()


def get_source_pickup(instrument, voice_id):
    """
    Determines which pickup on the source instrument should be used for the target voice.
    Checks explicit pickup_mapping, falls back to default_pickup, or selects first pickup.
    """
    pickups = instrument.get("pickups", {})
    if not pickups:
        raise ValueError(f"Instrument '{instrument.get('id', 'unknown')}' has no pickups defined.")

    # 1. Explicit voice mapping
    mapping = instrument.get("pickup_mapping", {})
    if voice_id in mapping and mapping[voice_id] in pickups:
        p = pickups[mapping[voice_id]].copy()
        p["id"] = mapping[voice_id]
        return p

    # 2. Default pickup declared on instrument
    default_key = instrument.get("default_pickup")
    if default_key:
        if default_key in pickups:
            p = pickups[default_key].copy()
            p["id"] = default_key
            return p
        raise KeyError(
            f"Instrument '{instrument.get('id', 'unknown')}' default_pickup '{default_key}' "
            f"not found in pickups: {list(pickups.keys())}"
        )

    raise ValueError(
        f"Instrument '{instrument.get('id', 'unknown')}' defines no 'default_pickup' "
        f"and has no pickup_mapping for voice '{voice_id}'."
    )
