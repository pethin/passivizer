from pathlib import Path
from scripts.model_physics import VOICES, SCALES


def test_voice_parameter_validity():
    for vid, cfg in VOICES.items():
        assert "name" in cfg, f"{vid} missing name"
        assert "topology" in cfg, f"{vid} missing topology"
        assert "description" in cfg, f"{vid} missing description"
        assert cfg["fr"] > 0, f"{vid} invalid resonant frequency fr: {cfg['fr']}"
        max_fr = 20000.0 if vid == "00_canonical_intermediate" else 6000.0
        assert 200.0 <= cfg["fr"] <= max_fr, f"{vid} fr outside audible musical range: {cfg['fr']}"
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

    # "all" should return all voices
    all_voices = resolve_voices("all")
    assert len(all_voices) == len(VOICES)
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
    shorthand = resolve_voices("01, 03")
    assert shorthand == ["01_modern_jazz_active", "03_jazz_bridge_60s"]

    # Shorthand matching specific 02b
    p2b = resolve_voices("02b")
    assert p2b == ["02b_jazz_bass_pair_22nf"]

    # Prefix 02 matches 02, 02b, and 02c
    p2_all = resolve_voices("02")
    assert p2_all == ["02_jazz_bass_pair", "02b_jazz_bass_pair_22nf", "02c_jazz_bridge_growl_bias"]

    # Shorthand matching specific 05b, 05c, 05d
    p5b = resolve_voices("05b")
    assert p5b == ["05b_vintage_62_p_22nf"]
    p5c = resolve_voices("05c")
    assert p5c == ["05c_vintage_62_p_47nf"]
    p5d = resolve_voices("05d")
    assert p5d == ["05d_vintage_50s_p_100nf"]

    # Prefix 05 matches 05, 05b, 05c, and 05d
    p5_all = resolve_voices("05")
    assert p5_all == [
        "05_vintage_62_p_alnico",
        "05b_vintage_62_p_22nf",
        "05c_vintage_62_p_47nf",
        "05d_vintage_50s_p_100nf",
    ]

    # Shorthand matching specific 09b
    p9b = resolve_voices("09b")
    assert p9b == ["09b_stingray_mm_series"]

    # Prefix 09 matches both 09 and 09b
    p9_all = resolve_voices("09")
    assert p9_all == [
        "09_stingray_mm_parallel",
        "09b_stingray_mm_series",
    ]

    # Shorthand matching 15 and 16
    p15 = resolve_voices("15")
    assert p15 == ["15_source_direct"]
    p16 = resolve_voices("16")
    assert p16 == ["16_active_character"]


def test_source_direct_properties():
    """Validates that 15_source_direct performs transparent deconvolution of Canonical Intermediate."""
    import numpy as np
    from scripts.model_physics import compute_voice_prefilter_firs, NUM_TAPS
    from scripts.analyze_voices import build_voice_dataframe
    from scripts.simulate_circuits import parse_netlist, compute_circuit_transfer_functions, FREQS, REPO_ROOT

    # 1. Prefilter FIR on Canonical Intermediate must invert the 93.5mm aperture sinc
    firs = compute_voice_prefilter_firs("15_source_direct", instrument="canonical_intermediate")
    assert len(firs) == 1
    fir = np.array(firs[0])
    assert len(fir) == NUM_TAPS

    # 2. Circuit transfer function must be identically 1.0 across all frequencies (no_eq buffer)
    cfg = VOICES["15_source_direct"]
    model = parse_netlist(REPO_ROOT / cfg["circuit"])
    assert getattr(model, "no_eq", False) is True
    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    assert len(curves) == 1
    assert np.all(np.array(curves[0]) == 1.0)

    # 3. Output mode dataframe must be bit-exact 0.00 dB (flat studio DI target)
    df_out = build_voice_dataframe("15_source_direct", cfg, instrument="canonical_intermediate", mode="output")
    mags_out = df_out["magnitude_db"].to_numpy()
    assert np.all(mags_out == 0.0)


def test_active_character_buffer_properties():
    """Validates that 16_active_character preserves aperture and acts as an uncolored active buffer."""
    import numpy as np
    from scripts.model_physics import compute_voice_prefilter_firs
    from scripts.simulate_circuits import parse_netlist, compute_circuit_transfer_functions, FREQS, REPO_ROOT

    # 1. Prefilter FIR preserves physical aperture (unit impulse)
    firs = compute_voice_prefilter_firs("16_active_character", instrument="34in_standard_p")
    assert len(firs) == 1
    fir = np.array(firs[0])
    assert fir[0] == 1.0
    assert np.all(fir[1:] == 0.0)

    # 2. Netlist models active buffer with flat contour
    cfg = VOICES["16_active_character"]
    model = parse_netlist(REPO_ROOT / cfg["circuit"])
    assert model.has_active_buffer is True
    assert model.preamp_type == "none"
    assert model.R_out == 100.0
    assert model.R_preamp_in >= 1.0e6

