"""
Tests for reusable onboard active preamps and buffer catalog configuration.
"""

from allomorph.config import PREAMPS, get_preamp


def test_preamps_catalog_loading():
    """Verify that all standard active preamp presets exist and have valid structure."""
    expected_presets = [
        "flat_buffer",
        "sadowsky_2band",
        "stingray_2band",
        "aguilar_3band",
        "dingwall_active",
    ]
    for pid in expected_presets:
        assert pid in PREAMPS, f"Missing preamp preset '{pid}'"
        cfg = PREAMPS[pid]
        assert "name" in cfg
        assert "input_impedance_meg" in cfg and cfg["input_impedance_meg"] >= 0.5
        assert "output_impedance_ohm" in cfg and cfg["output_impedance_ohm"] <= 1000.0
        assert "bands" in cfg
        assert isinstance(cfg["bands"], list)

        for b in cfg["bands"]:
            assert "type" in b
            assert b["type"] in ["low_shelf", "high_shelf", "bell", "low_pass", "high_pass"]
            assert "freq_hz" in b and 20.0 <= b["freq_hz"] <= 20000.0
            assert "gain_db" in b and -20.0 <= b["gain_db"] <= 20.0


def test_get_preamp_resolution():
    """Verify get_preamp resolves presets, default fallbacks, and inline overrides."""
    # 1. None/empty returns flat buffer
    default_pre = get_preamp(None)
    assert default_pre["name"] == "Flat Studio Active Buffer"
    assert len(default_pre["bands"]) == 0

    # 2. String preset lookup
    sad = get_preamp("sadowsky_2band")
    assert sad["name"] == "Sadowsky 2-Band Boost-Only Preamp"
    assert len(sad["bands"]) == 2
    assert sad["bands"][0]["freq_hz"] == 60.0
    assert sad["bands"][0]["gain_db"] == 3.5
    assert sad["bands"][1]["freq_hz"] == 3500.0
    assert sad["bands"][1]["gain_db"] == 3.5

    # 3. Dict with preset override
    overridden = get_preamp({"preset": "sadowsky_2band", "gain_db": 2.0})
    assert overridden["gain_db"] == 2.0
    assert len(overridden["bands"]) == 2

    # 4. Pure custom dict
    custom = get_preamp({
        "name": "Custom 1-Band",
        "output_impedance_ohm": 150.0,
        "bands": [{"type": "low_shelf", "freq_hz": 50.0, "gain_db": 4.0}]
    })
    assert custom["name"] == "Custom 1-Band"
    assert len(custom["bands"]) == 1
