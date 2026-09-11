"""
Tests for pickup and target voice coil geometry and coordinate resolution.
"""

import math
from allomorph.config import (
    VOICES,
    load_instrument,
    resolve_pickup_coils,
    resolve_voice_pickups,
    resolve_voice_coils,
    compute_effective_position,
)


def test_resolve_pickup_coils():
    # 1. 30" MMTW (dual and single coil)
    inst_30 = load_instrument("30in")
    coils_30_dual = resolve_pickup_coils(inst_30["pickups"]["mmtw_dual"], inst_30)
    assert len(coils_30_dual) == 2
    assert all("all" in c["strings"] for c in coils_30_dual)

    coils_30_single = resolve_pickup_coils(inst_30["pickups"]["mmtw_single"], inst_30)
    assert len(coils_30_single) == 1
    assert math.isclose(coils_30_single[0]["position_from_bridge_m"], 0.06607, abs_tol=1e-4)

    # 2. 34" P (split coils with E/A and D/G binding)
    inst_p = load_instrument("34in_standard_p")
    coils_p = resolve_pickup_coils(inst_p["pickups"]["split_p"], inst_p)
    assert len(coils_p) == 2
    assert coils_p[0]["strings"] == [3, 4]
    assert coils_p[1]["strings"] == [1, 2]
    assert math.isclose(coils_p[0]["position_from_bridge_m"], 0.1390, abs_tol=1e-4)
    assert math.isclose(coils_p[1]["position_from_bridge_m"], 0.1110, abs_tol=1e-4)

    # 3. 34" Jazz (composite pair_parallel)
    inst_j = load_instrument("34in_standard_jazz")
    coils_j = resolve_pickup_coils(inst_j["pickups"]["pair_parallel"], inst_j)
    assert len(coils_j) == 2
    assert math.isclose(coils_j[0]["position_from_bridge_m"], 0.1556, abs_tol=1e-4)
    assert math.isclose(coils_j[1]["position_from_bridge_m"], 0.0635, abs_tol=1e-4)
    assert coils_j[0]["weight"] == 0.5
    assert coils_j[1]["weight"] == 0.5


def test_resolve_voice_pickups():
    # 1. Multi-pickup: 01_modern_jazz_active
    p_act = resolve_voice_pickups(VOICES["01_modern_jazz_active"])
    assert len(p_act) == 2
    assert p_act[0]["fr"] == 5200.0
    assert p_act[0]["Q"] == 1.7
    assert p_act[1]["fr"] == 4600.0
    assert p_act[1]["Q"] == 1.8

    # 2. Multi-pickup: 02_jazz_bass_pair
    p_jazz = resolve_voice_pickups(VOICES["02_jazz_bass_pair"])
    assert len(p_jazz) == 2
    assert p_jazz[0]["fr"] == 3600.0
    assert p_jazz[0]["Q"] == 1.5
    assert p_jazz[1]["fr"] == 3200.0
    assert p_jazz[1]["Q"] == 1.6

    # 3. Multi-pickup: 07_modern_pj_active
    p_pj_act = resolve_voice_pickups(VOICES["07_modern_pj_active"])
    assert len(p_pj_act) == 2
    assert p_pj_act[0]["fr"] == 4800.0
    assert p_pj_act[0]["Q"] == 1.7
    assert p_pj_act[0]["weight"] == 0.5
    assert len(p_pj_act[0]["coils"]) == 2  # P-split E/A + D/G
    assert p_pj_act[1]["fr"] == 4600.0
    assert p_pj_act[1]["Q"] == 1.8
    assert p_pj_act[1]["weight"] == 0.5
    assert len(p_pj_act[1]["coils"]) == 1  # J-bridge

    # 4. Multi-pickup: 08_vintage_pj_passive
    p_pj_pas = resolve_voice_pickups(VOICES["08_vintage_pj_passive"])
    assert len(p_pj_pas) == 2
    assert p_pj_pas[0]["fr"] == 2600.0
    assert p_pj_pas[0]["Q"] == 1.3
    assert p_pj_pas[1]["fr"] == 2800.0
    assert p_pj_pas[1]["Q"] == 1.3

    # 5. Multi-pickup: 11_pmm_hybrid_series & 11_modern_pmm_active
    p_pmm = resolve_voice_pickups(VOICES["11_pmm_hybrid_series"])
    assert len(p_pmm) == 2
    assert p_pmm[0]["fr"] == 2200.0
    assert p_pmm[1]["fr"] == 3500.0

    p_pmm_act = resolve_voice_pickups(VOICES["11_modern_pmm_active"])
    assert len(p_pmm_act) == 2
    assert p_pmm_act[0]["fr"] == 3200.0
    assert p_pmm_act[1]["fr"] == 3500.0

    # 6. Single-pickup voice auto-wrapping: 04_modern_p_ceramic
    p_p = resolve_voice_pickups(VOICES["04_modern_p_ceramic"])
    assert len(p_p) == 1
    assert p_p[0]["fr"] == 2200.0
    assert p_p[0]["Q"] == 1.8
    assert p_p[0]["weight"] == 1.0
    assert len(p_p[0]["coils"]) == 2


def test_resolve_voice_coils():
    # 01 Modern active jazz should have 2 coils, each with strings=["all"]
    c01 = resolve_voice_coils(VOICES["01_modern_jazz_active"])
    assert len(c01) == 2
    assert c01[0]["position_from_bridge_m"] == 0.1556
    assert c01[1]["position_from_bridge_m"] == 0.0635
    assert c01[0]["strings"] == ["all"]

    # 04 Modern P ceramic should have 2 split coils with specific string bindings
    c04 = resolve_voice_coils(VOICES["04_modern_p_ceramic"])
    assert len(c04) == 2
    assert c04[0]["strings"] == [3, 4]
    assert c04[0]["position_from_bridge_m"] == 0.1390
    assert c04[1]["strings"] == [1, 2]
    assert c04[1]["position_from_bridge_m"] == 0.1110

    # 07 Modern PJ active should have 3 coils (split P + J bridge)
    c07 = resolve_voice_coils(VOICES["07_modern_pj_active"])
    assert len(c07) == 3
    assert c07[0]["strings"] == [3, 4]
    assert c07[1]["strings"] == [1, 2]
    assert c07[2]["strings"] == ["all"]

    # 11 P/MM hybrid should have 4 coils (split P + MM humbucker pair)
    c11 = resolve_voice_coils(VOICES["11_pmm_hybrid_series"])
    assert len(c11) == 4
    assert c11[0]["strings"] == [3, 4]
    assert c11[1]["strings"] == [1, 2]
    assert c11[2]["strings"] == ["all"]
    assert c11[3]["strings"] == ["all"]

    c11_act = resolve_voice_coils(VOICES["11_modern_pmm_active"])
    assert len(c11_act) == 4
    assert c11_act[0]["strings"] == [3, 4]
    assert c11_act[1]["strings"] == [1, 2]
    assert c11_act[2]["strings"] == ["all"]
    assert c11_act[3]["strings"] == ["all"]

    # Check effective positions are calculated correctly
    eff01 = compute_effective_position(c01)
    assert 0.10 < eff01 < 0.12  # Average of 0.1556 and 0.0635 is 0.10955

    # Legacy backward compatibility test: dict with pos_34, w, d
    legacy_cfg = {"pos_34": 0.066, "w": 0.75, "d": 0.75}
    c_legacy = resolve_voice_coils(legacy_cfg)
    assert len(c_legacy) == 2
    assert c_legacy[0]["strings"] == ["all"]
