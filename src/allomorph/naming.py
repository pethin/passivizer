"""
Allomorph - Naming Conventions & CLI Resolution Engine
Provides pedalboard display slugs, dynamic tier prefixes, baked filename generation,
and tolerant CLI argument parsing for instruments and voices.
"""

from collections.abc import Sequence

from allomorph.base import AllomorphBaseModel
from allomorph.config.instruments import INSTRUMENTS, load_instrument
from allomorph.config.voices import VOICES


class TierSpec(AllomorphBaseModel):
    """Specification of an Allomorph processing/export tier."""

    name: str
    folder_name: str
    prefix: str
    description: str = ""


TIER_SPECS: dict[str, TierSpec] = {
    "dynamic": TierSpec(
        name="dynamic",
        folder_name="00_dynamic",
        prefix="dyn_",
        description="Dynamic non-linear saturation model",
    ),
    "clean": TierSpec(
        name="clean",
        folder_name="01_studio_clean",
        prefix="cln_",
        description="Studio clean linear model",
    ),
    "standard": TierSpec(
        name="standard",
        folder_name="02_standard_dynamic",
        prefix="std_",
        description="Standard dynamic model",
    ),
    "hotrod": TierSpec(
        name="hotrod",
        folder_name="03_hot_rod",
        prefix="hot_",
        description="Hot-rod high-gain model",
    ),
}
TIER_SPECS["dyn"] = TIER_SPECS["dynamic"]
TIER_SPECS["std"] = TIER_SPECS["standard"]


def get_tier_spec(tier: str | None = None) -> TierSpec:
    """Resolves a processing/export tier specification with alias normalization."""
    key = (tier or "dynamic").lower().strip()
    if key not in TIER_SPECS:
        raise KeyError(f"Unknown tier '{tier}'. Available tiers: {list(TIER_SPECS.keys())}")
    return TIER_SPECS[key]


VOICE_CONCISE_SLUGS: dict[str, str] = {
    "00_canonical_intermediate": "00_canonical",
    "01_modern_jazz_active": "01_jazz_act",
    "02_jazz_bass_pair": "02_jazz_pair",
    "02b_jazz_bass_pair_22nf": "02b_j_22nf",
    "02c_jazz_bridge_growl_bias": "02c_jaco_growl",
    "03_jazz_bridge_60s": "03_jazz_bridge",
    "04_modern_p_ceramic": "04_modern_p",
    "05_vintage_62_p_alnico": "05_vintage_p",
    "05b_vintage_62_p_22nf": "05b_p_22nf",
    "05c_vintage_62_p_47nf": "05c_p_47nf",
    "05d_vintage_50s_p_100nf": "05d_p_100nf",
    "07_modern_pj_active": "07_pj_act",
    "08_vintage_pj_passive": "08_pj_pass",
    "09_stingray_mm_parallel": "09_stingray",
    "09b_stingray_mm_series": "09b_mm_series",
    "10_rickenbacker_bridge_hpf": "10_rick_hpf",
    "11_modern_pmm_active": "11_pmm_act",
    "11b_pmm_hybrid_series": "11b_pmm_series",
    "12_mudbucker_ultra_series": "12_mudbucker",
    "13_dingwall_multiscale_bridge": "13_dingwall",
    "14_upright_bridge_transducer": "14_upright",
    "15_neutral_character": "15_neutral",
    "15b_active_character": "15b_active",
    "15c_passive_character": "15c_passive",
}


def get_baked_basename(voice_id: str, tier: str = "dynamic", pickup: str = "auto") -> str:
    """
    Generates a concise, distinct model/wav basename for baked voice transformations.
    Format:
      - Default auto-routed pickup: '{tier_prefix}{voice_slug}' (e.g. 'dyn_04_modern_p')
      - Explicit non-auto pickup override: '{tier_prefix}{voice_slug}_{pickup}' (e.g. 'dyn_04_modern_p_bridge')
    """
    tier_spec = get_tier_spec(tier)
    prefix = tier_spec.prefix
    slug = VOICE_CONCISE_SLUGS.get(voice_id, voice_id)

    if pickup and pickup != "auto":
        return f"{prefix}{slug}_{pickup}"
    return f"{prefix}{slug}"


def resolve_voices(voice_arg: str | Sequence[str] | None) -> list[str]:
    """
    Parses a voice argument into a list of valid target voice IDs.
    Supports:
      - 'all' -> all configured voices in VOICES
      - Comma-separated list: '01_jazz_bass_pair,03_modern_p_ceramic'
      - Single voice ID: '03_modern_p_ceramic'
      - Partial / prefix matching: '01', '03'
    """
    if not voice_arg or str(voice_arg).strip().lower() == "all":
        return list(VOICES.keys())

    tokens = [t.strip() for t in str(voice_arg).split(",") if t.strip()]
    resolved: list[str] = []
    for token in tokens:
        if token in VOICES:
            if token not in resolved:
                resolved.append(token)
        else:
            matches = [vid for vid in VOICES if vid.startswith(token) or token in vid]
            if matches:
                for m in matches:
                    if m not in resolved:
                        resolved.append(m)
            else:
                print(f"Warning: Unknown voice identifier '{token}'.")
    return resolved if resolved else list(VOICES.keys())


def resolve_instruments(instrument_arg: str | Sequence[str] | None) -> list[str]:
    """
    Parses an instrument argument into a list of valid source instrument IDs.
    Supports:
      - 'all' -> all configured playable source instruments in INSTRUMENTS (excluding canonical_intermediate)
      - Comma-separated list: '30in,32in_fretless,34in_standard_p'
      - Single instrument ID or alias: '30in', 'fretless', 'jazz'
      - Partial / alias matching
    """
    all_playable: list[str] = [
        str(iid) for iid in sorted(INSTRUMENTS.keys()) if str(iid) != "canonical_intermediate"
    ]
    if not instrument_arg or str(instrument_arg).strip().lower() == "all":
        return all_playable

    tokens = [t.strip() for t in str(instrument_arg).split(",") if t.strip()]
    resolved: list[str] = []
    for token in tokens:
        if token.lower() == "all":
            for iid in all_playable:
                if iid not in resolved:
                    resolved.append(iid)
            continue
        try:
            cfg = load_instrument(token)
            iid = cfg.id
            if iid != "canonical_intermediate" and iid not in resolved:
                resolved.append(iid)
        except FileNotFoundError:
            matches = [iid for iid in all_playable if iid.startswith(token) or token in iid]
            if matches:
                for m in matches:
                    if m not in resolved:
                        resolved.append(m)
            else:
                print(f"Warning: Unknown instrument identifier '{token}'.")
    return resolved if resolved else all_playable
