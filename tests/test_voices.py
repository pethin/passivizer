from pathlib import Path
from scripts.model_physics import VOICES, SCALES

EXPECTED_VOICES = [
    "01_jazz_bass_pair",
    "02_jazz_bridge_70s",
    "03_modern_p_ceramic",
    "04_vintage_62_p_alnico",
    "05_p_bass_47nf_rolloff",
    "06_pj_hybrid_parallel",
    "07_stingray_mm_parallel",
    "08_rickenbacker_bridge_hpf",
    "09_pmm_hybrid_series",
    "10_mudbucker_ultra_series",
    "11_dingwall_multiscale_bridge"
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
        assert cfg["pos_34"] > 0, f"{vid} invalid pos_34: {cfg['pos_34']}"
        assert cfg["w"] > 0, f"{vid} invalid aperture w: {cfg['w']}"
        assert cfg["d"] >= 0, f"{vid} invalid spacing d: {cfg['d']}"
        assert isinstance(cfg["gain_db"], (int, float)), f"{vid} gain_db not float"

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

    assert len(SCALES["30in"]["speeds"]) == 4
    assert len(SCALES["32in"]["speeds"]) == 4
    assert len(SCALES["34in"]["speeds"]) == 4
    assert len(SCALES["multiscale"]["speeds"]) == 4

    # 30" wave speeds should be lower than 34" wave speeds
    for s30, s34 in zip(SCALES["30in"]["speeds"], SCALES["34in"]["speeds"]):
        assert s30 < s34

def test_resolve_voices():
    from scripts.model_physics import resolve_voices

    # "all" should return all 11 voices
    all_voices = resolve_voices("all")
    assert len(all_voices) == 11
    assert all_voices == list(VOICES.keys())

    # Single voice
    single = resolve_voices("03_modern_p_ceramic")
    assert single == ["03_modern_p_ceramic"]

    # Comma-separated voices
    multi = resolve_voices("01_jazz_bass_pair, 07_stingray_mm_parallel")
    assert multi == ["01_jazz_bass_pair", "07_stingray_mm_parallel"]

    # Prefix shorthand matching
    shorthand = resolve_voices("01, 04")
    assert shorthand == ["01_jazz_bass_pair", "04_vintage_62_p_alnico"]
