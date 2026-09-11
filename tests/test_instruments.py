import math
import tempfile
from pathlib import Path
import tomllib
from scripts.model_physics import (
    INSTRUMENTS,
    VOICES,
    STRINGS,
    load_instrument,
    load_all_instruments,
    get_source_pickup,
    compute_aperture_prefilter_fir,
    resolve_instruments,
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
        "34in_standard_pj",
        "34in_active_stingray",
        "34in_active_soapbar",
        "30in_mustang_pj",
        "37in_multiscale_dingwall",
        "34in_dingwall_sp1",
    ]
    for iid in expected_ids:
        assert iid in instruments, f"Default instrument '{iid}' not found"

    for iid, cfg in instruments.items():
        assert "id" in cfg
        assert "name" in cfg
        assert cfg["scale_length_in"] > 0
        assert len(cfg["string_wave_speeds"]) in [4, 5]
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
    j_pickup = get_source_pickup(inst, "03_jazz_bridge_60s")
    assert j_pickup["name"] == "EMG MMTW Single-Coil (Bridge Coil)"
    assert math.isclose(j_pickup["position_from_bridge_m"], 0.06607, abs_tol=1e-4)

    # StingRay should route to dual-coil mode
    mm_pickup = get_source_pickup(inst, "09_stingray_mm_parallel")
    assert mm_pickup["name"] == "EMG MMTW Dual-Coil (Centerline)"
    assert math.isclose(mm_pickup["position_from_bridge_m"], 0.0775, abs_tol=1e-4)
    assert math.isclose(mm_pickup["coil_spacing_in"], 0.90, abs_tol=1e-4)

def test_30in_mm_legacy_routing():
    inst = load_instrument("30in_emg_mm")
    assert inst["id"] == "30in_emg_mmtw"
    pickup = get_source_pickup(inst, "09_stingray_mm_parallel")
    assert pickup["name"] == "EMG MMTW Dual-Coil (Centerline)"
    assert math.isclose(pickup["position_from_bridge_m"], 0.0775, abs_tol=1e-4)
    assert math.isclose(pickup["coil_spacing_in"], 0.90, abs_tol=1e-4)

def test_32in_custom_pmm_routing():
    inst = load_instrument("32in")
    assert inst["id"] == "32in_custom_pmm"

    # P-Bass voices route to neck PX split-coil
    p_pickup = get_source_pickup(inst, "04_modern_p_ceramic")
    assert p_pickup["name"] == "Reverse EMG PX Split-Coil (Neck)"
    assert math.isclose(p_pickup["position_from_bridge_m"], 0.1228, abs_tol=1e-4)

    # 60s Jazz Bridge routes to bridge single coil
    j_pickup = get_source_pickup(inst, "03_jazz_bridge_60s")
    assert j_pickup["name"] == "EMG MMTWX Single-Coil (Bridge)"
    assert math.isclose(j_pickup["position_from_bridge_m"], 0.0508, abs_tol=1e-4)

    # StingRay MM routes to dual coil centerline
    mm_pickup = get_source_pickup(inst, "09_stingray_mm_parallel")
    assert mm_pickup["name"] == "EMG MMTWX Dual-Coil (Centerline)"
    assert math.isclose(mm_pickup["position_from_bridge_m"], 0.0622, abs_tol=1e-4)

    # P/J hybrid routes to parallel P/J pair (Reverse PX + MMTWX single-coil)
    pj_pickup = get_source_pickup(inst, "07_modern_pj_active")
    assert pj_pickup["name"] == "EMG PX + MMTWX Single Parallel (P/J Mode)"
    assert pj_pickup["type"] == "composite"
    assert len(pj_pickup["components"]) == 2
    assert pj_pickup["components"][0]["pickup"] == "px"
    assert pj_pickup["components"][1]["pickup"] == "mmtwx_single"
    assert math.isclose(pj_pickup["position_from_bridge_m"], 0.0868, abs_tol=1e-4)

    # P/MM series & active voices route to physical parallel center detent blend
    pmm_pickup = get_source_pickup(inst, "11_pmm_hybrid_series")
    assert pmm_pickup["name"] == "EMG PX + MMTWX Parallel (Center Detent)"
    assert math.isclose(pmm_pickup["position_from_bridge_m"], 0.0868, abs_tol=1e-4)

    pmm_act_pickup = get_source_pickup(inst, "11_modern_pmm_active")
    assert pmm_act_pickup["name"] == "EMG PX + MMTWX Parallel (Center Detent)"
    assert math.isclose(pmm_act_pickup["position_from_bridge_m"], 0.0868, abs_tol=1e-4)

    # Mudbucker routes to neck PX
    mud_pickup = get_source_pickup(inst, "12_mudbucker_ultra_series")
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
    assert pcsx["coils"][0]["strings"] == [1, 2]
    assert math.isclose(pcsx["coils"][0]["position_from_bridge_m"], 0.1544, abs_tol=1e-4)
    assert pcsx["coils"][1]["strings"] == [3, 4]
    assert math.isclose(pcsx["coils"][1]["position_from_bridge_m"], 0.1264, abs_tol=1e-4)

    # Upright voice routes to solo reverse PCSX neck split-coil (100%)
    up_pickup = get_source_pickup(inst, "14_upright_bridge_transducer")
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
"04_modern_p_ceramic" = "neck_soapbar"
"09_stingray_mm_parallel" = "bridge_soapbar"
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = Path(tmpdir) / "my_custom_bass.toml"
        tmp_file.write_text(custom_toml, encoding="utf-8")

        inst = load_instrument(tmp_file)
        assert inst["id"] == "custom_35in_soapbar"
        assert inst["scale_length_in"] == 35.0

        p_pick = get_source_pickup(inst, "04_modern_p_ceramic")
        assert p_pick["name"] == "Neck Dual Soapbar"

        # Compute prefilter FIR using the custom user bass
        fir = compute_aperture_prefilter_fir("04_modern_p_ceramic", instrument=tmp_file, num_taps=NUM_TAPS)
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

    inst_pj = load_instrument("34in_standard_pj")
    pj_p = inst_pj["pickups"]["p"]
    assert pj_p["resonant_frequency_hz"] == 2800.0
    assert pj_p["q_factor"] == 1.40

    pj_j = inst_pj["pickups"]["j"]
    assert pj_j["resonant_frequency_hz"] == 3200.0
    assert pj_j["q_factor"] == 1.60

    pj_pair = inst_pj["pickups"]["pair_parallel"]
    assert pj_pair["resonant_frequency_hz"] == 2800.0
    assert pj_pair["q_factor"] == 1.20


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
        assert inst["pickup_mapping"]["07_modern_pj_active"] == "pj_blend_parallel"
        assert inst["pickup_mapping"]["08_vintage_pj_passive"] == "pj_blend_parallel"

def test_34in_standard_pj_routing():
    inst = load_instrument("34in_standard_pj")
    assert inst["id"] == "34in_standard_pj"
    assert inst["scale_length_in"] == 34.0
    assert inst["electronics"] == "passive"
    assert "p" in inst["pickups"]
    assert "j" in inst["pickups"]
    assert "pair_parallel" in inst["pickups"]
    assert inst["default_pickup"] == "pair_parallel"

    # Split-P pickup
    p_pickup = inst["pickups"]["p"]
    assert p_pickup["type"] == "split_coil"
    assert math.isclose(p_pickup["position_from_bridge_m"], 0.1250, abs_tol=1e-4)
    assert p_pickup["circuit"] == "circuits/sources/source_standard_p.cir"
    assert len(p_pickup["coils"]) == 2

    # Jazz Bridge pickup
    j_pickup = inst["pickups"]["j"]
    assert j_pickup["type"] == "single_coil"
    assert math.isclose(j_pickup["position_from_bridge_m"], 0.0635, abs_tol=1e-4)
    assert j_pickup["circuit"] == "circuits/sources/source_standard_jazz_bridge.cir"
    assert len(j_pickup["coils"]) == 1

    # Parallel composite pair
    pair = inst["pickups"]["pair_parallel"]
    assert pair["type"] == "composite"
    assert pair["circuit"] == "circuits/sources/source_standard_pj_pair.cir"
    assert len(pair["components"]) == 2
    assert pair["components"][0]["pickup"] == "p"
    assert pair["components"][1]["pickup"] == "j"

    # Shorthand aliases check
    assert load_instrument("standard_pj")["id"] == "34in_standard_pj"
    assert load_instrument("pj")["id"] == "34in_standard_pj"
    assert load_instrument("34in_pj")["id"] == "34in_standard_pj"

    # Routing checks: P voices
    assert get_source_pickup(inst, "04_modern_p_ceramic")["id"] == "p"
    assert get_source_pickup(inst, "05_vintage_62_p_alnico")["id"] == "p"
    assert get_source_pickup(inst, "05c_vintage_62_p_47nf")["id"] == "p"
    assert get_source_pickup(inst, "12_mudbucker_ultra_series")["id"] == "p"
    assert get_source_pickup(inst, "14_upright_bridge_transducer")["id"] == "p"

    # Routing checks: Bridge voices
    assert get_source_pickup(inst, "03_jazz_bridge_60s")["id"] == "j"
    assert get_source_pickup(inst, "09_stingray_mm_parallel")["id"] == "j"
    assert get_source_pickup(inst, "10_rickenbacker_bridge_hpf")["id"] == "j"
    assert get_source_pickup(inst, "13_dingwall_multiscale_bridge")["id"] == "j"

    # Routing checks: Parallel pair voices
    assert get_source_pickup(inst, "01_modern_jazz_active")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "02_jazz_bass_pair")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "07_modern_pj_active")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "08_vintage_pj_passive")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "11_pmm_hybrid_series")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "11_modern_pmm_active")["id"] == "pair_parallel"

def test_34in_active_stingray_routing():
    inst = load_instrument("34in_active_stingray")
    assert inst["id"] == "34in_active_stingray"
    assert inst["scale_length_in"] == 34.0
    assert inst["electronics"] == "active"
    assert "mm_parallel" in inst["pickups"]
    assert inst["default_pickup"] == "mm_parallel"

    # MM pickup definition
    mm = inst["pickups"]["mm_parallel"]
    assert mm["type"] == "dual_coil_parallel"
    assert math.isclose(mm["position_from_bridge_m"], 0.0660, abs_tol=1e-4)
    assert mm["resonant_frequency_hz"] == 4200.0
    assert mm["q_factor"] == 1.60
    assert len(mm["coils"]) == 2

    # Shorthand aliases check
    assert load_instrument("active_stingray")["id"] == "34in_active_stingray"
    assert load_instrument("stingray")["id"] == "34in_active_stingray"
    assert load_instrument("ray")["id"] == "34in_active_stingray"

    # All target voices map to mm_parallel
    for vid in VOICES:
        pickup = get_source_pickup(inst, vid)
        assert pickup["id"] == "mm_parallel"

def test_34in_active_soapbar_routing():
    inst = load_instrument("34in_active_soapbar")
    assert inst["id"] == "34in_active_soapbar"
    assert inst["scale_length_in"] == 34.0
    assert inst["electronics"] == "active"
    assert "neck" in inst["pickups"]
    assert "bridge" in inst["pickups"]
    assert "pair_parallel" in inst["pickups"]
    assert inst["default_pickup"] == "pair_parallel"

    # Neck soapbar
    neck = inst["pickups"]["neck"]
    assert math.isclose(neck["position_from_bridge_m"], 0.1350, abs_tol=1e-4)
    assert neck["resonant_frequency_hz"] == 3800.0
    assert neck["q_factor"] == 1.40
    assert len(neck["coils"]) == 2

    # Bridge soapbar
    bridge = inst["pickups"]["bridge"]
    assert math.isclose(bridge["position_from_bridge_m"], 0.0550, abs_tol=1e-4)
    assert bridge["resonant_frequency_hz"] == 4100.0
    assert bridge["q_factor"] == 1.40
    assert len(bridge["coils"]) == 2

    # Composite pair
    pair = inst["pickups"]["pair_parallel"]
    assert pair["type"] == "composite"
    assert len(pair["components"]) == 2
    assert pair["components"][0]["pickup"] == "neck"
    assert pair["components"][1]["pickup"] == "bridge"

    # Shorthand aliases check
    assert load_instrument("active_soapbar")["id"] == "34in_active_soapbar"
    assert load_instrument("soapbar")["id"] == "34in_active_soapbar"

    # P voices route to neck soapbar
    assert get_source_pickup(inst, "04_modern_p_ceramic")["id"] == "neck"
    assert get_source_pickup(inst, "05_vintage_62_p_alnico")["id"] == "neck"
    assert get_source_pickup(inst, "12_mudbucker_ultra_series")["id"] == "neck"
    assert get_source_pickup(inst, "14_upright_bridge_transducer")["id"] == "neck"

    # Bridge voices route to bridge soapbar
    assert get_source_pickup(inst, "03_jazz_bridge_60s")["id"] == "bridge"
    assert get_source_pickup(inst, "09_stingray_mm_parallel")["id"] == "bridge"
    assert get_source_pickup(inst, "10_rickenbacker_bridge_hpf")["id"] == "bridge"
    assert get_source_pickup(inst, "13_dingwall_multiscale_bridge")["id"] == "bridge"

    # Parallel voices route to pair_parallel
    assert get_source_pickup(inst, "01_modern_jazz_active")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "02_jazz_bass_pair")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "07_modern_pj_active")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "08_vintage_pj_passive")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "11_pmm_hybrid_series")["id"] == "pair_parallel"
    assert get_source_pickup(inst, "11_modern_pmm_active")["id"] == "pair_parallel"

def test_30in_mustang_pj_routing():
    inst = load_instrument("30in_mustang_pj")
    assert inst["id"] == "30in_mustang_pj"
    assert inst["scale_length_in"] == 30.0
    assert inst["electronics"] == "passive"
    assert "p" in inst["pickups"]
    assert "j" in inst["pickups"]
    assert "pair_parallel" in inst["pickups"]
    assert inst["default_pickup"] == "pair_parallel"

    p = inst["pickups"]["p"]
    assert p["type"] == "split_coil"
    assert math.isclose(p["position_from_bridge_m"], 0.1550, abs_tol=1e-4)
    assert p["resonant_frequency_hz"] == 2800.0
    assert len(p["coils"]) == 2

    j = inst["pickups"]["j"]
    assert j["type"] == "single_coil"
    assert math.isclose(j["position_from_bridge_m"], 0.0550, abs_tol=1e-4)
    assert j["resonant_frequency_hz"] == 3200.0

    # Aliases
    assert load_instrument("mustang")["id"] == "30in_mustang_pj"
    assert load_instrument("30in_mustang")["id"] == "30in_mustang_pj"
    assert load_instrument("mustang_pj")["id"] == "30in_mustang_pj"

    # Smart voice routing
    assert get_source_pickup(inst, "05_vintage_62_p_alnico")["id"] == "p"
    assert get_source_pickup(inst, "03_jazz_bridge_60s")["id"] == "j"
    assert get_source_pickup(inst, "02_jazz_bass_pair")["id"] == "pair_parallel"

def test_37in_multiscale_dingwall_routing():
    inst = load_instrument("37in_multiscale_dingwall")
    assert inst["id"] == "37in_multiscale_dingwall"
    assert inst["scale_length_in"] == 37.0
    assert inst["electronics"] == "active"
    assert len(inst["string_wave_speeds"]) == 5
    assert inst["strings"]["gauge"] == "45-130"
    assert "bridge" in inst["pickups"]
    assert "middle" in inst["pickups"]
    assert "pair_parallel" in inst["pickups"]

    # Bridge pickup (1:1 with Voice 13)
    b = inst["pickups"]["bridge"]
    assert math.isclose(b["position_from_bridge_m"], 0.0480, abs_tol=1e-4)
    assert b["resonant_frequency_hz"] == 3400.0

    # Middle pickup
    mid = inst["pickups"]["middle"]
    assert math.isclose(mid["position_from_bridge_m"], 0.0960, abs_tol=1e-4)

    # Aliases
    assert load_instrument("dingwall")["id"] == "37in_multiscale_dingwall"
    assert load_instrument("combustion")["id"] == "37in_multiscale_dingwall"
    assert load_instrument("ng")["id"] == "37in_multiscale_dingwall"
    assert load_instrument("dingwall_ng")["id"] == "37in_multiscale_dingwall"
    assert load_instrument("ng2")["id"] == "37in_multiscale_dingwall"
    assert load_instrument("ng3")["id"] == "37in_multiscale_dingwall"
    assert load_instrument("37in_dingwall_ng")["id"] == "37in_multiscale_dingwall"
    assert inst.get("is_multiscale") is True
    assert inst.get("scale_min_in") == 34.0
    assert inst.get("scale_max_in") == 37.0

    # Voice 13 maps to bridge
    assert get_source_pickup(inst, "13_dingwall_multiscale_bridge")["id"] == "bridge"
    assert get_source_pickup(inst, "05_vintage_62_p_alnico")["id"] == "middle"
    assert get_source_pickup(inst, "01_modern_jazz_active")["id"] == "pair_parallel"

def test_34in_dingwall_sp1_routing():
    inst = load_instrument("34in_dingwall_sp1")
    assert inst["id"] == "34in_dingwall_sp1"
    assert inst["scale_length_in"] == 35.0
    assert inst.get("is_multiscale") is True
    assert inst.get("scale_min_in") == 32.0
    assert inst.get("scale_max_in") == 35.0
    assert inst["electronics"] == "passive"
    assert len(inst["string_wave_speeds"]) == 5
    assert inst["strings"]["gauge"] == "45-130"
    assert "p" in inst["pickups"]
    assert "bridge" in inst["pickups"]
    assert "pair_parallel" in inst["pickups"]

    # Dual-P split coil
    p = inst["pickups"]["p"]
    assert p["type"] == "split_coil"
    assert math.isclose(p["position_from_bridge_m"], 0.1250, abs_tol=1e-4)
    assert len(p["coils"]) == 2
    assert p["coils"][0]["strings"] == [3, 4, 5]
    assert p["coils"][1]["strings"] == [1, 2]

    # FD3n Bridge
    b = inst["pickups"]["bridge"]
    assert math.isclose(b["position_from_bridge_m"], 0.0580, abs_tol=1e-4)

    # Aliases
    assert load_instrument("sp1")["id"] == "34in_dingwall_sp1"
    assert load_instrument("dingwall_sp1")["id"] == "34in_dingwall_sp1"
    assert load_instrument("35in_dingwall_sp1")["id"] == "34in_dingwall_sp1"
    assert load_instrument("super_p")["id"] == "34in_dingwall_sp1"
    assert load_instrument("dingwall_super_p")["id"] == "34in_dingwall_sp1"

    # Routing
    assert get_source_pickup(inst, "05_vintage_62_p_alnico")["id"] == "p"
    assert get_source_pickup(inst, "03_jazz_bridge_60s")["id"] == "bridge"
    assert get_source_pickup(inst, "08_vintage_pj_passive")["id"] == "pair_parallel"

def test_all_instruments_have_valid_string_presets():
    """Verify that every default instrument declares a string preset that exists in STRINGS catalog."""
    instruments = load_all_instruments()
    for iid, cfg in instruments.items():
        if "strings" in cfg and "preset" in cfg["strings"]:
            preset = cfg["strings"]["preset"]
            assert preset in STRINGS, f"Instrument '{iid}' declares unknown string preset '{preset}'"

def test_active_identity_differential_flatness():
    """Verify that active source instruments matching their target voice evaluate to 0.00 dB flat."""
    from scripts.analyze_voices import build_voice_dataframe
    import numpy as np

    # 1. 37" Multi-Scale Dingwall -> Voice 13 Dingwall Bridge (< 0.05 dB flat)
    df_ding = build_voice_dataframe("13_dingwall_multiscale_bridge", VOICES["13_dingwall_multiscale_bridge"], instrument="37in_multiscale_dingwall", mode="difference")
    mags_ding = df_ding["magnitude_db"].to_numpy()
    assert np.all(np.abs(mags_ding) < 0.05), f"Dingwall identity differential not flat: max abs={np.max(np.abs(mags_ding))}"

    # 2. 34" Active StingRay -> Voice 09 Music Man MM (< 0.05 dB flat)
    df_ray = build_voice_dataframe("09_stingray_mm_parallel", VOICES["09_stingray_mm_parallel"], instrument="34in_active_stingray", mode="difference")
    mags_ray = df_ray["magnitude_db"].to_numpy()
    assert np.all(np.abs(mags_ray) < 0.05), f"StingRay identity differential not flat: max abs={np.max(np.abs(mags_ray))}"

def test_small_sample_delay_inter_pickup_coherence_decay():
    """Verify that dual-pickup configurations with small inter-pickup sample delay (<= 5 samples) apply coherence decay."""
    from scripts.analyze_voices import build_voice_dataframe
    import numpy as np

    # 34" Active Soapbar Bass playing 01 Modern Active Jazz Pair has delta_samples = 5.
    # Must apply spatial coherence decay without plunging into unphysical -40 dB razor notches.
    df = build_voice_dataframe("01_modern_jazz_active", VOICES["01_modern_jazz_active"], instrument="34in_active_soapbar", mode="difference")
    mags = df["magnitude_db"].to_numpy()
    min_db = np.min(mags)
    assert min_db > -20.0, f"Soapbar on Jazz Pair has unregularized comb notch: min={min_db} dB"
    assert -16.0 <= min_db <= -12.0, f"Expected smooth authentic acoustic mid-scoop around -14 dB, got {min_db} dB"

def test_resolve_instruments():
    """Verify resolve_instruments handles 'all', defaults, comma lists, aliases, and unknown tokens."""
    # 1. 'all' returns all 11 playable instruments and excludes canonical_intermediate
    all_insts = resolve_instruments("all")
    assert len(all_insts) == 11
    assert "canonical_intermediate" not in all_insts
    expected_11 = {
        "30in_emg_mmtw",
        "30in_mustang_pj",
        "32in_custom_pmm",
        "32in_fretless_pmm",
        "34in_active_soapbar",
        "34in_active_stingray",
        "34in_dingwall_sp1",
        "34in_standard_jazz",
        "34in_standard_p",
        "34in_standard_pj",
        "37in_multiscale_dingwall",
    }
    assert set(all_insts) == expected_11

    # 2. None, empty string, or whitespace defaults to all playable
    assert resolve_instruments(None) == all_insts
    assert resolve_instruments("") == all_insts
    assert resolve_instruments("   ") == all_insts

    # 3. Comma-separated list with exact IDs and aliases
    res = resolve_instruments("30in, fretless, 34in_standard_p")
    assert res == ["30in_emg_mmtw", "32in_fretless_pmm", "34in_standard_p"]

    # 4. Aliases
    assert resolve_instruments("mustang") == ["30in_mustang_pj"]
    assert resolve_instruments("dingwall") == ["37in_multiscale_dingwall"]
    assert resolve_instruments("soapbar") == ["34in_active_soapbar"]
    assert resolve_instruments("ray") == ["34in_active_stingray"]

    # 5. Unknown tokens emit warning and don't break resolution when valid tokens present
    res_unknown = resolve_instruments("nonexistent_bass, 30in")
    assert res_unknown == ["30in_emg_mmtw"]

    # 6. Entirely unknown token falls back to all playable instruments
    res_all_unknown = resolve_instruments("completely_bogus_token")
    assert res_all_unknown == all_insts









