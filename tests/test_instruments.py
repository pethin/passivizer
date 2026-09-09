import math
import tempfile
from pathlib import Path
import tomllib
from scripts.model_physics import (
    INSTRUMENTS,
    VOICES,
    load_instrument,
    load_all_instruments,
    get_source_pickup,
    compute_aperture_prefilter_fir,
    NUM_TAPS
)

def test_load_all_default_instruments():
    instruments = load_all_instruments()
    expected_ids = [
        "30in_emg_mmtw",
        "32in_custom_pmm",
        "32in_fretless_pmm",
        "34in_standard_p",
        "34in_standard_jazz",
        "34in_active_p",
        "34in_active_jazz",
        "34in_active_pj",
    ]
    for iid in expected_ids:
        assert iid in instruments, f"Default instrument '{iid}' not found"

    for iid, cfg in instruments.items():
        assert "id" in cfg
        assert "name" in cfg
        assert cfg["scale_length_in"] > 0
        assert len(cfg["string_wave_speeds"]) == 4
        assert "pickups" in cfg and len(cfg["pickups"]) > 0
        assert "default_pickup" in cfg
        assert cfg["default_pickup"] in cfg["pickups"]

        for pid, pcfg in cfg["pickups"].items():
            assert "name" in pcfg
            assert pcfg["position_from_bridge_m"] > 0
            assert pcfg["aperture_width_in"] > 0
            assert pcfg["coil_spacing_in"] >= 0

def test_30in_mmtw_routing():
    inst = load_instrument("30in")
    assert inst["id"] == "30in_emg_mmtw"
    assert "mmtw_dual" in inst["pickups"]
    assert "mmtw_single" in inst["pickups"]

    # 60s Jazz Bridge should route to single-coil mode
    j_pickup = get_source_pickup(inst, "02_jazz_bridge_60s")
    assert j_pickup["name"] == "EMG MMTW Single-Coil (Bridge Coil)"
    assert math.isclose(j_pickup["position_from_bridge_m"], 0.06607, abs_tol=1e-4)

    # StingRay should route to dual-coil mode
    mm_pickup = get_source_pickup(inst, "07_stingray_mm_parallel")
    assert mm_pickup["name"] == "EMG MMTW Dual-Coil (Centerline)"
    assert math.isclose(mm_pickup["position_from_bridge_m"], 0.0775, abs_tol=1e-4)
    assert math.isclose(mm_pickup["coil_spacing_in"], 0.90, abs_tol=1e-4)

def test_30in_mm_legacy_routing():
    inst = load_instrument("30in_emg_mm")
    assert inst["id"] == "30in_emg_mmtw"
    pickup = get_source_pickup(inst, "07_stingray_mm_parallel")
    assert pickup["name"] == "EMG MMTW Dual-Coil (Centerline)"
    assert math.isclose(pickup["position_from_bridge_m"], 0.0775, abs_tol=1e-4)
    assert math.isclose(pickup["coil_spacing_in"], 0.90, abs_tol=1e-4)

def test_32in_custom_pmm_routing():
    inst = load_instrument("32in")
    assert inst["id"] == "32in_custom_pmm"

    # P-Bass voices route to neck PX split-coil
    p_pickup = get_source_pickup(inst, "03_modern_p_ceramic")
    assert p_pickup["name"] == "Reverse EMG PX Split-Coil (Neck)"
    assert math.isclose(p_pickup["position_from_bridge_m"], 0.1228, abs_tol=1e-4)

    # 60s Jazz Bridge routes to bridge single coil
    j_pickup = get_source_pickup(inst, "02_jazz_bridge_60s")
    assert j_pickup["name"] == "EMG MMTWX Single-Coil (Bridge)"
    assert math.isclose(j_pickup["position_from_bridge_m"], 0.0508, abs_tol=1e-4)

    # StingRay MM routes to dual coil centerline
    mm_pickup = get_source_pickup(inst, "07_stingray_mm_parallel")
    assert mm_pickup["name"] == "EMG MMTWX Dual-Coil (Centerline)"
    assert math.isclose(mm_pickup["position_from_bridge_m"], 0.0622, abs_tol=1e-4)

    # P/J hybrid routes to parallel P/J pair (Reverse PX + MMTWX single-coil)
    pj_pickup = get_source_pickup(inst, "06_pj_hybrid_parallel")
    assert pj_pickup["name"] == "EMG PX + MMTWX Single Parallel (P/J Mode)"
    assert pj_pickup["type"] == "composite"
    assert len(pj_pickup["components"]) == 2
    assert pj_pickup["components"][0]["pickup"] == "px"
    assert pj_pickup["components"][1]["pickup"] == "mmtwx_single"
    assert math.isclose(pj_pickup["position_from_bridge_m"], 0.0868, abs_tol=1e-4)

    # P/MM series voice routes to physical parallel center detent blend
    pmm_pickup = get_source_pickup(inst, "09_pmm_hybrid_series")
    assert pmm_pickup["name"] == "EMG PX + MMTWX Parallel (Center Detent)"
    assert math.isclose(pmm_pickup["position_from_bridge_m"], 0.0868, abs_tol=1e-4)

    # Mudbucker routes to neck PX
    mud_pickup = get_source_pickup(inst, "10_mudbucker_ultra_series")
    assert mud_pickup["name"] == "Reverse EMG PX Split-Coil (Neck)"
    assert math.isclose(mud_pickup["position_from_bridge_m"], 0.1228, abs_tol=1e-4)

def test_32in_fretless_pmm_routing():
    inst = load_instrument("32in_fretless")
    assert inst["id"] == "32in_fretless_pmm"
    assert inst["scale_length_in"] == 32.0
    assert inst["default_pickup"] == "pcsx"

    # Alias check
    inst_alias = load_instrument("fretless")
    assert inst_alias["id"] == "32in_fretless_pmm"

    # PCSX reverse split placement: 266mm from 12th fret = 140.4mm from bridge
    pcsx = inst["pickups"]["pcsx"]
    assert math.isclose(pcsx["position_from_bridge_m"], 0.1404, abs_tol=1e-4)
    assert pcsx["resonant_frequency_hz"] == 2610.0
    assert pcsx["q_factor"] == 1.35
    assert len(pcsx["coils"]) == 2
    assert pcsx["coils"][0]["strings"] == ["D", "G"]
    assert math.isclose(pcsx["coils"][0]["position_from_bridge_m"], 0.1544, abs_tol=1e-4)
    assert pcsx["coils"][1]["strings"] == ["E", "A"]
    assert math.isclose(pcsx["coils"][1]["position_from_bridge_m"], 0.1264, abs_tol=1e-4)

    # Upright voice routes to solo pcsx
    up_pickup = get_source_pickup(inst, "12_upright_bridge_transducer")
    assert up_pickup["name"] == "Reverse EMG PCSX Split-Coil (Neck)"
    assert up_pickup["type"] == "split_coil"

def test_load_custom_user_bass_toml():
    """Verify that any future bass or external user bass can be loaded from an arbitrary TOML file."""
    custom_toml = """
id = "custom_35in_soapbar"
name = '35" Custom 5-String Soapbar'
scale_length_in = 35.0
scale_length_m = 0.889
string_wave_speeds = [73.2, 97.8, 130.5, 174.2]
default_pickup = "bridge_soapbar"

[pickups.neck_soapbar]
name = "Neck Dual Soapbar"
position_from_bridge_m = 0.1400
aperture_width_in = 1.35
coil_spacing_in = 0.65

[pickups.bridge_soapbar]
name = "Bridge Dual Soapbar"
position_from_bridge_m = 0.0550
aperture_width_in = 1.35
coil_spacing_in = 0.65

[pickup_mapping]
"03_modern_p_ceramic" = "neck_soapbar"
"07_stingray_mm_parallel" = "bridge_soapbar"
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "my_custom_bass.toml"
        tmp_file.write_text(custom_toml, encoding="utf-8")

        inst = load_instrument(tmp_file)
        assert inst["id"] == "custom_35in_soapbar"
        assert inst["scale_length_in"] == 35.0

        p_pick = get_source_pickup(inst, "03_modern_p_ceramic")
        assert p_pick["name"] == "Neck Dual Soapbar"

        # Compute prefilter FIR using the custom user bass
        fir = compute_aperture_prefilter_fir("03_modern_p_ceramic", instrument=tmp_file, num_taps=NUM_TAPS)
        assert len(fir) == NUM_TAPS
        max_peak = max(abs(x) for x in fir)
        assert math.isclose(max_peak, 0.99, rel_tol=1e-3)

def test_resolve_pickup_coils():
    from scripts.model_physics import load_instrument, resolve_pickup_coils

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
    assert coils_p[0]["strings"] == ["E", "A"]
    assert coils_p[1]["strings"] == ["D", "G"]
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

def test_standard_instruments_electrical_parameters():
    """Verify that standard instrument pickups specify resonant_frequency_hz and q_factor."""
    inst_p = load_instrument("34in_standard_p")
    p_pickup = inst_p["pickups"]["split_p"]
    assert p_pickup["resonant_frequency_hz"] == 2800.0
    assert p_pickup["q_factor"] == 1.40

    inst_j = load_instrument("34in_standard_jazz")
    j_neck = inst_j["pickups"]["neck"]
    assert j_neck["resonant_frequency_hz"] == 3600.0
    assert j_neck["q_factor"] == 1.50

    j_bridge = inst_j["pickups"]["bridge"]
    assert j_bridge["resonant_frequency_hz"] == 3200.0
    assert j_bridge["q_factor"] == 1.60

    j_pair = inst_j["pickups"]["pair_parallel"]
    assert j_pair["resonant_frequency_hz"] == 3900.0
    assert j_pair["q_factor"] == 1.30

def test_32in_pj_blend_parallel_definition():
    """Verify that both 32in P+TWX instruments define the parallel P/J mode (single-coil TWX)."""
    for iid in ["32in_custom_pmm", "32in_fretless_pmm"]:
        inst = load_instrument(iid)
        assert "pj_blend_parallel" in inst["pickups"]
        pj = inst["pickups"]["pj_blend_parallel"]
        assert pj["type"] == "composite"
        assert len(pj["components"]) == 2
        assert pj["components"][1]["pickup"] == "mmtwx_single"
        assert pj["resonant_frequency_hz"] > 0
        assert pj["q_factor"] > 0
        assert inst["pickup_mapping"]["06_pj_hybrid_parallel"] == "pj_blend_parallel"

def test_34in_active_p_routing():
    inst = load_instrument("34in_active_p")
    assert inst["id"] == "34in_active_p"
    assert inst["scale_length_in"] == 34.0
    assert "px" in inst["pickups"]
    px = inst["pickups"]["px"]
    assert px["resonant_frequency_hz"] == 3200.0
    assert px["q_factor"] == 1.40
    assert px["type"] == "split_coil"

    # All voices route to px
    for vid in VOICES:
        pickup = get_source_pickup(inst, vid)
        assert pickup["id"] == "px"

    # Shorthand alias check
    assert load_instrument("active_p")["id"] == "34in_active_p"

def test_34in_active_jazz_routing():
    inst = load_instrument("34in_active_jazz")
    assert inst["id"] == "34in_active_jazz"
    assert inst["scale_length_in"] == 34.0
    assert "neck" in inst["pickups"]
    assert "bridge" in inst["pickups"]
    assert "pair_parallel" in inst["pickups"]

    assert inst["pickups"]["neck"]["resonant_frequency_hz"] == 4050.0
    assert inst["pickups"]["bridge"]["resonant_frequency_hz"] == 4050.0
    assert inst["pickups"]["pair_parallel"]["resonant_frequency_hz"] == 4050.0

    # Bridge solo voices
    assert get_source_pickup(inst, "02_jazz_bridge_60s")["id"] == "bridge"
    assert get_source_pickup(inst, "07_stingray_mm_parallel")["id"] == "bridge"

    # Neck solo voices
    assert get_source_pickup(inst, "03_modern_p_ceramic")["id"] == "neck"

    # Parallel voices
    assert get_source_pickup(inst, "01_jazz_bass_pair")["id"] == "pair_parallel"

    # Shorthand alias check
    assert load_instrument("active_jazz")["id"] == "34in_active_jazz"

def test_34in_active_pj_routing():
    inst = load_instrument("34in_active_pj")
    assert inst["id"] == "34in_active_pj"
    assert inst["scale_length_in"] == 34.0
    assert "px" in inst["pickups"]
    assert "jx" in inst["pickups"]
    assert "pair_parallel" in inst["pickups"]

    assert inst["pickups"]["px"]["resonant_frequency_hz"] == 3200.0
    assert inst["pickups"]["jx"]["resonant_frequency_hz"] == 4050.0

    # P voices route to PX
    assert get_source_pickup(inst, "03_modern_p_ceramic")["id"] == "px"
    assert get_source_pickup(inst, "04_vintage_62_p_alnico")["id"] == "px"

    # Bridge voices route to JX
    assert get_source_pickup(inst, "02_jazz_bridge_60s")["id"] == "jx"
    assert get_source_pickup(inst, "07_stingray_mm_parallel")["id"] == "jx"

    # Hybrid voices route to parallel blend
    assert get_source_pickup(inst, "06_pj_hybrid_parallel")["id"] == "pair_parallel"

    # Shorthand alias check
    assert load_instrument("active_pj")["id"] == "34in_active_pj"




