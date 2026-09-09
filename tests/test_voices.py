from pathlib import Path
from scripts.model_physics import VOICES, SCALES

EXPECTED_VOICES = [
    "01_modern_jazz_active",
    "02_jazz_bass_pair",
    "03_jazz_bridge_60s",
    "04_modern_p_ceramic",
    "05_vintage_62_p_alnico",
    "06_p_bass_47nf_rolloff",
    "07_modern_pj_active",
    "08_vintage_pj_passive",
    "09_stingray_mm_parallel",
    "10_rickenbacker_bridge_hpf",
    "11_pmm_hybrid_series",
    "12_mudbucker_ultra_series",
    "13_dingwall_multiscale_bridge",
    "14_upright_bridge_transducer"
]

def test_all_expected_voices_exist():
    for vid in EXPECTED_VOICES:
        assert vid in VOICES, f"Voice {vid} missing from VOICES catalog"

def test_voice_parameter_validity():
    for vid, cfg in VOICES.items():
        assert "name" in cfg, f"{vid} missing name"
        assert "topology" in cfg, f"{vid} missing topology"
        assert "description" in cfg, f"{vid} missing description"
        assert cfg["fr"] > 0, f"{vid} invalid resonant frequency fr: {cfg['fr']}"
        assert 200.0 <= cfg["fr"] <= 6000.0, f"{vid} fr outside audible musical range: {cfg['fr']}"
        assert cfg["Q"] > 0, f"{vid} invalid Q: {cfg['Q']}"
        assert isinstance(cfg["gain_db"], (int, float)), f"{vid} gain_db not float"
        assert "coils" in cfg, f"{vid} missing coils array"
        assert len(cfg["coils"]) >= 1, f"{vid} has empty coils list"
        for i, c in enumerate(cfg["coils"]):
            assert "position_from_bridge_m" in c, f"{vid} coil {i} missing position_from_bridge_m"
            assert c["position_from_bridge_m"] > 0, f"{vid} coil {i} invalid position: {c['position_from_bridge_m']}"
            assert c.get("aperture_width_in", 0.75) > 0, f"{vid} coil {i} invalid aperture"
            assert c.get("weight", 1.0) > 0, f"{vid} coil {i} invalid weight"
            assert "strings" in c, f"{vid} coil {i} missing strings binding"
            assert isinstance(c["strings"], list) and len(c["strings"]) >= 1

        if "pickups" in cfg:
            assert len(cfg["pickups"]) >= 2, f"{vid} pickups list has fewer than 2 pickups"
            for j, p in enumerate(cfg["pickups"]):
                assert "name" in p, f"{vid} pickup {j} missing name"
                assert p.get("fr", 0) > 0, f"{vid} pickup {j} invalid fr: {p.get('fr')}"
                assert p.get("Q", 0) > 0, f"{vid} pickup {j} invalid Q: {p.get('Q')}"
                assert p.get("weight", 0) > 0, f"{vid} pickup {j} invalid weight"
                assert "coils" in p and len(p["coils"]) >= 1, f"{vid} pickup {j} missing coils"

def test_resolve_voice_pickups():
    from scripts.model_physics import resolve_voice_pickups

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

    # 5. Multi-pickup: 11_pmm_hybrid_series
    p_pmm = resolve_voice_pickups(VOICES["11_pmm_hybrid_series"])
    assert len(p_pmm) == 2
    assert p_pmm[0]["fr"] == 2200.0
    assert p_pmm[1]["fr"] == 3500.0

    # 6. Single-pickup voice auto-wrapping: 04_modern_p_ceramic
    p_p = resolve_voice_pickups(VOICES["04_modern_p_ceramic"])
    assert len(p_p) == 1
    assert p_p[0]["fr"] == 2200.0
    assert p_p[0]["Q"] == 1.8
    assert p_p[0]["weight"] == 1.0
    assert len(p_p[0]["coils"]) == 2

def test_resolve_voice_coils():
    from scripts.model_physics import resolve_voice_coils, compute_effective_position

    # 01 Modern active jazz should have 2 coils, each with strings=["all"]
    c01 = resolve_voice_coils(VOICES["01_modern_jazz_active"])
    assert len(c01) == 2
    assert c01[0]["position_from_bridge_m"] == 0.1556
    assert c01[1]["position_from_bridge_m"] == 0.0635
    assert c01[0]["strings"] == ["all"]

    # 04 Modern P ceramic should have 2 split coils with specific string bindings
    c04 = resolve_voice_coils(VOICES["04_modern_p_ceramic"])
    assert len(c04) == 2
    assert c04[0]["strings"] == ["E", "A"]
    assert c04[0]["position_from_bridge_m"] == 0.1390
    assert c04[1]["strings"] == ["D", "G"]
    assert c04[1]["position_from_bridge_m"] == 0.1110

    # 07 Modern PJ active should have 3 coils (split P + J bridge)
    c07 = resolve_voice_coils(VOICES["07_modern_pj_active"])
    assert len(c07) == 3
    assert c07[0]["strings"] == ["E", "A"]
    assert c07[1]["strings"] == ["D", "G"]
    assert c07[2]["strings"] == ["all"]

    # 11 P/MM hybrid should have 4 coils (split P + MM humbucker pair)
    c11 = resolve_voice_coils(VOICES["11_pmm_hybrid_series"])
    assert len(c11) == 4
    assert c11[0]["strings"] == ["E", "A"]
    assert c11[1]["strings"] == ["D", "G"]
    assert c11[2]["strings"] == ["all"]
    assert c11[3]["strings"] == ["all"]

    # Check effective positions are calculated correctly
    eff01 = compute_effective_position(c01)
    assert 0.10 < eff01 < 0.12  # Average of 0.1556 and 0.0635 is 0.10955

    # Legacy backward compatibility test: dict with pos_34, w, d
    legacy_cfg = {"pos_34": 0.066, "w": 0.75, "d": 0.75}
    c_legacy = resolve_voice_coils(legacy_cfg)
    assert len(c_legacy) == 2
    assert c_legacy[0]["strings"] == ["all"]

def test_voice_netlist_existence():
    for vid, cfg in VOICES.items():
        assert "circuit" in cfg, f"{vid} missing circuit netlist attribute"
        circuit_file = Path(cfg["circuit"])
        assert circuit_file.exists(), f"Circuit file {circuit_file} for {vid} not found on disk"

def test_voices_have_no_hardcoded_source_datums():
    # Target voices should be purely decoupled from source instrument geometries
    for vid, cfg in VOICES.items():
        assert "src_32" not in cfg, f"{vid} contains deprecated hardcoded 'src_32' datum"
        assert "src_30" not in cfg, f"{vid} contains deprecated hardcoded 'src_30' datum"

def test_scales_structure():
    assert "30in" in SCALES
    assert "32in" in SCALES
    assert "34in" in SCALES
    assert "multiscale" in SCALES
    assert "upright" in SCALES

    assert len(SCALES["30in"]["speeds"]) == 4
    assert len(SCALES["32in"]["speeds"]) == 4
    assert len(SCALES["34in"]["speeds"]) == 4
    assert len(SCALES["multiscale"]["speeds"]) == 4
    assert len(SCALES["upright"]["speeds"]) == 4

    # 30" wave speeds should be lower than 34" wave speeds, and 34" lower than upright
    for s30, s34, sup in zip(SCALES["30in"]["speeds"], SCALES["34in"]["speeds"], SCALES["upright"]["speeds"]):
        assert s30 < s34 < sup

def test_resolve_voices():
    from scripts.model_physics import resolve_voices

    # "all" should return all 14 voices
    all_voices = resolve_voices("all")
    assert len(all_voices) == 14
    assert all_voices == list(VOICES.keys())

    # Single voice
    single = resolve_voices("04_modern_p_ceramic")
    assert single == ["04_modern_p_ceramic"]

    # Upright voice
    upright = resolve_voices("14")
    assert upright == ["14_upright_bridge_transducer"]

    # Comma-separated voices
    multi = resolve_voices("01_modern_jazz_active, 09_stingray_mm_parallel")
    assert multi == ["01_modern_jazz_active", "09_stingray_mm_parallel"]

    # Prefix shorthand matching
    shorthand = resolve_voices("01, 05")
    assert shorthand == ["01_modern_jazz_active", "05_vintage_62_p_alnico"]
