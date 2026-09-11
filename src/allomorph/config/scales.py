"""
Scale lengths, wave speeds, and physical scale range resolution.
"""

from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
SCALES_FILE = CONFIG_DIR / "scales.toml"


def load_scales(config_path=None):
    """Loads scale lengths and wave speeds from TOML."""
    path = Path(config_path) if config_path else SCALES_FILE
    with open(path, "rb") as f:
        data = tomllib.load(f)
    scales = {}
    for sid, scfg in data.get("scales", {}).items():
        scales[sid] = {
            "name": scfg.get("name", sid),
            "scale_m": scfg.get("scale_length_m", scfg.get("scale_length_in", 34.0) * 0.0254),
            "scale_length_in": scfg.get("scale_length_in", 34.0),
            "scale_min_in": scfg.get("scale_min_in"),
            "scale_max_in": scfg.get("scale_max_in"),
            "is_multiscale": scfg.get("is_multiscale", False),
            "speeds": scfg.get("string_wave_speeds", []),
        }
    return scales


SCALES = load_scales()


def resolve_scale_range(inst_or_scale):
    """
    Resolves the vibrating scale length range (scale_min_m, scale_max_m) in meters.
    Returns (L, L) for standard single-scale instruments, or (min_m, max_m) for multi-scale.
    If None is provided, defaults to the canonical standard 34" reference scale (0.8636 m).
    """
    if inst_or_scale is None:
        return (0.8636, 0.8636)

    if isinstance(inst_or_scale, (tuple, list)):
        if len(inst_or_scale) == 2 and all(float(v) <= 5.0 for v in inst_or_scale):
            return (float(min(inst_or_scale)), float(max(inst_or_scale)))
        raise ValueError(f"Invalid scale length tuple/list: {inst_or_scale}")

    if isinstance(inst_or_scale, (int, float)):
        val = float(inst_or_scale)
        val_m = val * 0.0254 if val > 5.0 else val
        return (val_m, val_m)

    if isinstance(inst_or_scale, str):
        if inst_or_scale in SCALES:
            s_info = SCALES[inst_or_scale]
            if s_info.get("is_multiscale"):
                min_m = s_info.get("scale_min_in", 34.0) * 0.0254
                max_m = s_info.get("scale_max_in", 37.0) * 0.0254
                return (min_m, max_m)
            l_m = s_info.get("scale_m", s_info.get("scale_length_m", 0.8636))
            return (l_m, l_m)
        try:
            from allomorph.config.instruments import load_instrument
            inst = load_instrument(inst_or_scale)
            return resolve_scale_range(inst)
        except Exception as e:
            raise ValueError(f"Unknown scale or instrument identifier '{inst_or_scale}': {e}")

    if isinstance(inst_or_scale, dict):
        if inst_or_scale.get("is_multiscale"):
            min_in = inst_or_scale.get("scale_min_in")
            max_in = inst_or_scale.get("scale_max_in", inst_or_scale.get("scale_length_in", 37.0))
            if min_in is not None and max_in is not None:
                return (float(min_in) * 0.0254, float(max_in) * 0.0254)
        l_in = inst_or_scale.get("scale_length_in")
        if l_in is not None:
            return (float(l_in) * 0.0254, float(l_in) * 0.0254)
        l_m = inst_or_scale.get("scale_length_m", inst_or_scale.get("scale_m"))
        if l_m is not None:
            return (float(l_m), float(l_m))
        raise ValueError(f"Dictionary configuration has no valid scale specification: {inst_or_scale}")

    raise TypeError(f"Cannot resolve scale range from object of type {type(inst_or_scale)}: {inst_or_scale}")
