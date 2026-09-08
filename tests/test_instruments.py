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
    expected_ids = ["30in_emg_mm", "32in_custom_pmm", "34in_standard_p", "34in_standard_jazz"]
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

def test_30in_mm_routing():
    inst = load_instrument("30in")
    assert inst["id"] == "30in_emg_mm"

    # All target voices should route to the single MM humbucker
    for vid in VOICES.keys():
        pickup = get_source_pickup(inst, vid)
        assert pickup["name"] == "EMG MM Dual Coil"
        assert math.isclose(pickup["position_from_bridge_m"], 0.0775, abs_tol=1e-4)
        assert math.isclose(pickup["aperture_width_in"], 1.50, abs_tol=1e-4)
        assert math.isclose(pickup["coil_spacing_in"], 0.75, abs_tol=1e-4)

def test_32in_custom_pmm_routing():
    inst = load_instrument("32in")
    assert inst["id"] == "32in_custom_pmm"

    # P-Bass voices route to neck PX split-coil
    p_pickup = get_source_pickup(inst, "03_modern_p_ceramic")
    assert p_pickup["name"] == "Reverse EMG PX Split-Coil (Neck)"
    assert math.isclose(p_pickup["position_from_bridge_m"], 0.1228, abs_tol=1e-4)

    # 70s Jazz Bridge routes to bridge single coil
    j_pickup = get_source_pickup(inst, "02_jazz_bridge_70s")
    assert j_pickup["name"] == "EMG MMTWX Single-Coil (Bridge)"
    assert math.isclose(j_pickup["position_from_bridge_m"], 0.0508, abs_tol=1e-4)

    # StingRay MM routes to dual coil centerline
    mm_pickup = get_source_pickup(inst, "07_stingray_mm_parallel")
    assert mm_pickup["name"] == "EMG MMTWX Dual-Coil (Centerline)"
    assert math.isclose(mm_pickup["position_from_bridge_m"], 0.0622, abs_tol=1e-4)

    # P/J hybrid routes to parallel pair
    pj_pickup = get_source_pickup(inst, "06_pj_hybrid_parallel")
    assert pj_pickup["name"] == "EMG PX + MMTWX Parallel (Center Detent)"
    assert math.isclose(pj_pickup["position_from_bridge_m"], 0.0868, abs_tol=1e-4)

    # P/MM series routes to series pair
    pmm_pickup = get_source_pickup(inst, "09_pmm_hybrid_series")
    assert pmm_pickup["name"] == "EMG PX + MMTWX Series Sum"
    assert math.isclose(pmm_pickup["position_from_bridge_m"], 0.0925, abs_tol=1e-4)

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
