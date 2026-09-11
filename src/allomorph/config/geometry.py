"""
Pickup coil geometry resolution, multi-coil component decomposition,
and magnetic pole piece geometry inference.
"""


from collections.abc import Sequence
from typing import Any


def _infer_pole_type(pickup_or_voice: Any = None, coil: Any = None) -> str:
    """
    Infers magnetic pole geometry: 'rod' (cylindrical Alnico rod, Airy/Bessel spatial window)
    or 'blade' (continuous steel/ceramic bar blade, 1D rectangular slit).
    """
    if coil and coil.get("pole_type"):
        return str(coil["pole_type"]).lower()
    if pickup_or_voice:
        if pickup_or_voice.get("pole_type"):
            return str(pickup_or_voice["pole_type"]).lower()
        mag = str(pickup_or_voice.get("magnet_type", pickup_or_voice.get("magnet", ""))).lower()
        p_type = str(pickup_or_voice.get("type", pickup_or_voice.get("topology", ""))).lower()
        p_name = str(pickup_or_voice.get("name", "")).lower()
        if "blade" in p_name or "blade" in p_type or "bar" in p_name:
            return "blade"
        if "emg" in p_name or "emg" in p_type:
            return "blade"
        if "active" in mag:
            return "blade"
        if "alnico" in mag or "single_coil" in p_type or "split" in p_type:
            return "rod"
    return "rod"


def resolve_pickup_coils(pickup_dict: dict[str, Any], instrument: Any = None) -> list[dict[str, Any]]:
    """
    Resolves an instrument pickup configuration into a canonical list of coil dicts.
    Handles:
      - Composite pickups ('components' referencing other pickups with weights)
      - Explicit coil arrays ('coils' with per-string bindings)
      - Dual-coil humbuckers with coil spacing 'd'
      - Single-coil / split-coil fallbacks
    """
    # 1. Composite blend / sum
    if pickup_dict.get("type") == "composite" or "components" in pickup_dict:
        resolved: list[dict[str, Any]] = []
        components = pickup_dict.get("components", [])
        empty_pickups: dict[str, Any] = {}
        pickups_map: dict[str, Any] = instrument.get("pickups", empty_pickups) if instrument else empty_pickups
        for comp in components:
            p_ref = comp.get("pickup")
            c_weight = comp.get("weight", 1.0)
            c_pol = comp.get("polarity", 1.0)
            if p_ref:
                if p_ref not in pickups_map:
                    raise KeyError(
                        f"Composite pickup references non-existent pickup '{p_ref}' in instrument "
                        f"'{instrument.get('id', 'unknown') if instrument else 'unknown'}'. "
                        f"Available pickups: {list(pickups_map.keys())}"
                    )
                sub_coils = resolve_pickup_coils(pickups_map[p_ref], instrument)
                for sc in sub_coils:
                    sc_copy = sc.copy()
                    sc_copy["weight"] = sc.get("weight", 1.0) * c_weight
                    sc_copy["polarity"] = sc.get("polarity", 1.0) * c_pol
                    if "pole_type" not in sc_copy:
                        sc_copy["pole_type"] = _infer_pole_type(pickups_map[p_ref], sc)
                    resolved.append(sc_copy)
            elif "position_from_bridge_m" in comp:
                resolved.append({
                    "position_from_bridge_m": comp["position_from_bridge_m"],
                    "aperture_width_in": comp.get("aperture_width_in", 0.75),
                    "weight": c_weight,
                    "polarity": c_pol,
                    "strings": comp.get("strings", ["all"]),
                    "pole_type": _infer_pole_type(pickup_dict, comp),
                })
            else:
                raise ValueError(
                    f"Composite pickup component in '{instrument.get('id', 'unknown') if instrument else 'unknown'}' "
                    f"must specify either 'pickup' or 'position_from_bridge_m'."
                )
        if resolved:
            return resolved

    # 2. Explicit coils list
    if pickup_dict.get("coils"):
        coils = []
        for c in pickup_dict["coils"]:
            coils.append({
                "position_from_bridge_m": c["position_from_bridge_m"],
                "aperture_width_in": c.get("aperture_width_in", pickup_dict.get("aperture_width_in", 0.75)),
                "weight": c.get("weight", 1.0),
                "polarity": c.get("polarity", 1.0),
                "strings": c.get("strings", ["all"]),
                "pole_type": _infer_pole_type(pickup_dict, c),
            })
        return coils

    # 3. Dual-coil humbucker via coil_spacing_in
    pos_m = pickup_dict.get("position_from_bridge_m", 0.08)
    w_in = pickup_dict.get("aperture_width_in", 0.75)
    d_in = pickup_dict.get("coil_spacing_in", 0.0)
    d_m = d_in * 0.0254
    p_pole = _infer_pole_type(pickup_dict)
    if d_in > 0:
        return [
            {
                "position_from_bridge_m": pos_m - d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"],
                "pole_type": p_pole,
            },
            {
                "position_from_bridge_m": pos_m + d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"],
                "pole_type": p_pole,
            }
        ]

    # 4. Standard single coil
    return [
        {
            "position_from_bridge_m": pos_m,
            "aperture_width_in": w_in,
            "weight": 1.0,
            "polarity": 1.0,
            "strings": ["all"],
            "pole_type": p_pole,
        }
    ]


def resolve_voice_pickups(voice_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Resolves a target voice configuration into a canonical list of pickup dicts.
    Handles multi-pickup voices and single-pickup fallbacks.
    """
    if voice_cfg.get("pickups"):
        resolved = []
        for p in voice_cfg["pickups"]:
            p_coils = []
            for c in p.get("coils", []):
                p_coils.append({
                    "position_from_bridge_m": float(c["position_from_bridge_m"]),
                    "aperture_width_in": float(c.get("aperture_width_in", 0.75)),
                    "weight": float(c.get("weight", 1.0)),
                    "polarity": float(c.get("polarity", 1.0)),
                    "strings": list(c.get("strings", ["all"])),
                    "pole_type": _infer_pole_type(p, c),
                })
            resolved.append({
                "name": str(p.get("name", "Pickup")),
                "type": str(p.get("type", "single_coil")),
                "fr": float(p.get("fr", voice_cfg.get("fr", 3000.0))),
                "Q": float(p.get("Q", voice_cfg.get("Q", 1.5))),
                "weight": float(p.get("weight", 1.0)),
                "polarity": float(p.get("polarity", 1.0)),
                "coils": p_coils,
            })
        if resolved:
            return resolved

    # Fallback for single-pickup voices: wrap top-level voice coils/fr/Q
    return [
        {
            "name": str(voice_cfg.get("name", "Target Pickup")),
            "type": str(voice_cfg.get("topology", "single")),
            "fr": float(voice_cfg.get("fr", 3000.0)),
            "Q": float(voice_cfg.get("Q", 1.5)),
            "weight": 1.0,
            "polarity": 1.0,
            "coils": resolve_voice_coils(voice_cfg, _from_pickups=False),
        }
    ]


def resolve_voice_coils(voice_cfg: dict[str, Any], _from_pickups: bool = True) -> list[dict[str, Any]]:
    """Resolves target voice configuration into a canonical list of coil dicts."""
    if _from_pickups and "pickups" in voice_cfg and voice_cfg["pickups"]:
        all_coils = []
        for p in voice_cfg["pickups"]:
            p_weight = float(p.get("weight", 1.0))
            p_pol = float(p.get("polarity", 1.0))
            for c in p.get("coils", []):
                all_coils.append({
                    "position_from_bridge_m": float(c["position_from_bridge_m"]),
                    "aperture_width_in": float(c.get("aperture_width_in", 0.75)),
                    "weight": float(c.get("weight", 1.0)) * p_weight,
                    "polarity": float(c.get("polarity", 1.0)) * p_pol,
                    "strings": list(c.get("strings", ["all"])),
                    "pole_type": _infer_pole_type(p, c),
                })
        if all_coils:
            return all_coils

    if "coils" in voice_cfg:
        normalized = []
        for c in voice_cfg["coils"]:
            normalized.append({
                "position_from_bridge_m": float(c["position_from_bridge_m"]),
                "aperture_width_in": float(c.get("aperture_width_in", 0.75)),
                "weight": float(c.get("weight", 1.0)),
                "polarity": float(c.get("polarity", 1.0)),
                "strings": list(c.get("strings", ["all"])),
                "pole_type": _infer_pole_type(voice_cfg, c),
            })
        return normalized
    pos_m = float(voice_cfg.get("pos_34", 0.088))
    w_in = float(voice_cfg.get("w", 0.75))
    d_in = float(voice_cfg.get("d", 0.0))
    d_m = d_in * 0.0254
    v_pole = _infer_pole_type(voice_cfg)
    if d_in > 0:
        return [
            {
                "position_from_bridge_m": pos_m - d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"],
                "pole_type": v_pole,
            },
            {
                "position_from_bridge_m": pos_m + d_m / 2.0,
                "aperture_width_in": w_in / 2.0,
                "weight": 0.5,
                "polarity": 1.0,
                "strings": ["all"],
                "pole_type": v_pole,
            }
        ]
    return [
        {
            "position_from_bridge_m": pos_m,
            "aperture_width_in": w_in,
            "weight": 1.0,
            "polarity": 1.0,
            "strings": ["all"],
            "pole_type": v_pole,
        }
    ]


def compute_effective_position(coils: Sequence[dict[str, Any]]) -> float:
    """Computes weighted average physical position from bridge in meters."""
    if not coils:
        return 0.08
    total_w = sum(c.get("weight", 1.0) for c in coils)
    if total_w == 0:
        return coils[0]["position_from_bridge_m"]
    return sum(c["position_from_bridge_m"] * c.get("weight", 1.0) for c in coils) / total_w
