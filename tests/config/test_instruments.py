"""
Tests for source instrument configuration loaders, validation, and electrical parameters.
"""

import math
import tempfile
from pathlib import Path

from allomorph.config import (
    STRINGS,
    VOICES,
    get_source_pickup,
    load_all_instruments,
    load_instrument,
)
from allomorph.dsp import NUM_TAPS
from allomorph.naming import resolve_instruments, resolve_voices
from allomorph.physics import compute_aperture_prefilter_fir


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

        for pcfg in cfg["pickups"].values():
            assert "name" in pcfg
            assert pcfg["position_from_bridge_m"] > 0
            assert pcfg["aperture_width_in"] > 0
            assert pcfg["coil_spacing_in"] >= 0


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


def test_all_instruments_have_valid_string_presets():
    """Verify that every default instrument declares a string preset that exists in STRINGS catalog."""
    instruments = load_all_instruments()
    for iid, cfg in instruments.items():
        if "strings" in cfg and "preset" in cfg["strings"]:
            preset = cfg["strings"]["preset"]
            assert preset in STRINGS, f"Instrument '{iid}' declares unknown string preset '{preset}'"


def test_active_identity_differential_flatness():
    """Verify that active source instruments matching their target voice evaluate to 0.00 dB flat."""
    import numpy as np

    from allomorph.visualizer import build_voice_dataframe

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
    import numpy as np

    from allomorph.visualizer import build_voice_dataframe

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


def test_resolve_voices():
    """Verify voice resolution with shorthand, aliases, and comma separation."""
    all_voices = resolve_voices("all")
    assert len(all_voices) == len(VOICES)
    assert all_voices == list(VOICES.keys())

    # Single voice
    assert resolve_voices("04_modern_p_ceramic") == ["04_modern_p_ceramic"]
    # Shorthand prefix matching
    assert resolve_voices("14") == ["14_upright_bridge_transducer"]
    assert resolve_voices("01, 03") == ["01_modern_jazz_active", "03_jazz_bridge_60s"]
    assert resolve_voices("02b") == ["02b_jazz_bass_pair_22nf"]
    assert resolve_voices("02") == ["02_jazz_bass_pair", "02b_jazz_bass_pair_22nf", "02c_jazz_bridge_growl_bias"]
    assert resolve_voices("05b") == ["05b_vintage_62_p_22nf"]
    assert resolve_voices("05c") == ["05c_vintage_62_p_47nf"]
    assert resolve_voices("05d") == ["05d_vintage_50s_p_100nf"]
    assert resolve_voices("05") == [
        "05_vintage_62_p_alnico",
        "05b_vintage_62_p_22nf",
        "05c_vintage_62_p_47nf",
        "05d_vintage_50s_p_100nf",
    ]
    assert resolve_voices("09b") == ["09b_stingray_mm_series"]
    assert resolve_voices("09") == ["09_stingray_mm_parallel", "09b_stingray_mm_series"]
    assert resolve_voices("15") == ["15_source_direct"]
    assert resolve_voices("16") == ["16_active_character"]


def test_get_source_pickup_strict_errors():
    """Verify that get_source_pickup raises clear configuration errors instead of silent fallbacks."""
    import pytest

    # 1. Empty pickups dictionary
    with pytest.raises(ValueError, match="has no pickups defined"):
        get_source_pickup({"id": "broken_bass", "pickups": {}}, "04_modern_p_ceramic")

    # 2. No default_pickup and no mapping
    no_default = {
        "id": "no_default_bass",
        "pickups": {"neck": {"name": "Neck"}},
    }
    with pytest.raises(ValueError, match="defines no 'default_pickup' and has no pickup_mapping"):
        get_source_pickup(no_default, "04_modern_p_ceramic")

    # 3. default_pickup specifies a non-existent pickup key
    bad_default = {
        "id": "bad_default_bass",
        "default_pickup": "non_existent",
        "pickups": {"neck": {"name": "Neck"}},
    }
    with pytest.raises(KeyError, match="default_pickup 'non_existent' not found in pickups"):
        get_source_pickup(bad_default, "04_modern_p_ceramic")


def test_string_preset_strict_errors():
    """Verify that invalid string presets raise KeyError instead of silent fallbacks."""
    import pytest

    from allomorph.config.strings import get_instrument_string, get_voice_string

    with pytest.raises(KeyError, match="String preset 'imaginary_flats' not found"):
        get_instrument_string({"strings": {"preset": "imaginary_flats"}})

    with pytest.raises(KeyError, match="String preset 'unknown_target_wire' not found"):
        get_voice_string({"target_string": "unknown_target_wire"})


def test_scale_resolution_strict_errors():
    """Verify that invalid scale parameters raise ValueError/TypeError instead of silent 34in fallback."""
    import pytest

    from allomorph.config.scales import resolve_scale_range

    # 1. Valid None returns standard 34" baseline
    assert resolve_scale_range(None) == (0.8636, 0.8636)

    # 2. Unknown scale name
    with pytest.raises(ValueError, match="Unknown scale or instrument identifier '99in_super_bass'"):
        resolve_scale_range("99in_super_bass")

    # 3. Dictionary missing scale keys
    with pytest.raises(ValueError, match="no valid scale specification"):
        resolve_scale_range({"name": "No Scale Bass"})

    # 4. Invalid types
    with pytest.raises(TypeError, match="Cannot resolve scale range"):
        resolve_scale_range(object())
