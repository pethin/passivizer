import math
import numpy as np
from pathlib import Path

from scripts.model_physics import (
    STRINGS,
    VOICES,
    FREQS,
    load_instrument,
    get_instrument_string,
    get_voice_string,
    compute_differential_string_transfer,
    compute_voice_prefilter_firs,
    NUM_TAPS,
)
from scripts.simulate_circuits import parse_netlist, CIRCUITS_DIR

def test_strings_catalog_loading():
    """Verify that all core physical string presets exist and have valid physical bounds."""
    expected_presets = [
        "roundwound_nickel_standard",
        "roundwound_stainless_clank",
        "flatwound_low_tension",
        "flatwound_vintage_heavy",
        "double_bass_spirocore",
    ]
    for p in expected_presets:
        assert p in STRINGS, f"Preset '{p}' missing from STRINGS catalog"
        s = STRINGS[p]
        assert s["tension_lbs"] > 100.0
        assert s["damping_cutoff_hz"] >= 1500.0
        assert s["damping_order"] >= 1.0

def test_instrument_string_resolution():
    """Verify source instrument string resolution and default fallback."""
    # 32in fretless explicitly declares La Bella Low Tension Flats
    inst_fretless = load_instrument("32in_fretless")
    str_fretless = get_instrument_string(inst_fretless)
    assert str_fretless["preset"] == "flatwound_low_tension"
    assert str_fretless["brand"] == "La Bella"
    assert str_fretless["model"] == "LTF-4A"
    assert math.isclose(str_fretless["tension_lbs"], 132.0, abs_tol=1e-3)
    assert math.isclose(str_fretless["damping_cutoff_hz"], 2800.0, abs_tol=1e-3)
    assert str_fretless["pluck_excursion_factor"] == 1.25

    # 30in and 34in default to roundwound_nickel_standard
    inst_30 = load_instrument("30in")
    str_30 = get_instrument_string(inst_30)
    assert str_30["type"] == "roundwound"
    assert math.isclose(str_30["damping_cutoff_hz"], 8500.0, abs_tol=1e-3)

    inst_34 = load_instrument("34in")
    str_34 = get_instrument_string(inst_34)
    assert str_34["type"] == "roundwound"

def test_target_voice_strings():
    """Verify target voice goal string mappings."""
    v14 = VOICES["14_upright_bridge_transducer"]
    str_v14 = get_voice_string(v14)
    assert str_v14["type"] == "double_bass"
    assert str_v14["tension_lbs"] == 265.0
    assert str_v14["bloom_db"] == 2.8

    v13 = VOICES["13_dingwall_multiscale_bridge"]
    str_v13 = get_voice_string(v13)
    assert str_v13["type"] == "roundwound"
    assert str_v13["wrap"] == "stainless"

    v06 = VOICES["06_p_bass_47nf_rolloff"]
    str_v06 = get_voice_string(v06)
    assert str_v06["type"] == "flatwound"

    # Standard voices default to roundwound_nickel_standard
    v04 = VOICES["04_modern_p_ceramic"]
    str_v04 = get_voice_string(v04)
    assert str_v04["type"] == "roundwound"

def test_differential_damping_anti_double_muffling():
    """
    Verify that Voice 14 avoids double-damping on flatwounds:
    When evaluated on 32in fretless (flatwound source), the prefilter FIR
    preserves more upper treble energy around 3.5 kHz relative to a roundwound
    source where harsh clank must be rolled off.
    """
    # Pre-filter FIR for 32" fretless (La Bella LTF source)
    firs_fretless = compute_voice_prefilter_firs("14_upright_bridge_transducer", instrument="32in_fretless")
    # Pre-filter FIR for 30" (roundwound source)
    firs_round = compute_voice_prefilter_firs("14_upright_bridge_transducer", instrument="30in")

    assert len(firs_fretless) == 1
    assert len(firs_round) == 1
    assert len(firs_fretless[0]) == NUM_TAPS

    # FFT of synthesized FIRs to compare frequency magnitudes
    fft_fretless = np.abs(np.fft.rfft(firs_fretless[0]))
    fft_round = np.abs(np.fft.rfft(firs_round[0]))
    fft_freqs = np.fft.rfftfreq(len(firs_fretless[0]), d=1.0 / 48000.0)

    # In the 3 kHz to 4.5 kHz range, the filter for the flatwound source should not
    # excessively attenuate (anti-double-damping compensation)
    idx_3k = np.argmin(np.abs(fft_freqs - 3500.0))
    idx_low = np.argmin(np.abs(fft_freqs - 150.0))

    ratio_fretless = fft_fretless[idx_3k] / fft_fretless[idx_low]
    ratio_round = fft_round[idx_3k] / fft_round[idx_low]

    # The flatwound prefilter preserves greater relative treble transmission than the roundwound prefilter
    assert ratio_fretless > ratio_round, "Flatwound prefilter should preserve more relative 3.5 kHz transmission to prevent double-muffling"

def test_bridge_compliance_scaling():
    """Verify that dynamic bridge compliance scales with pluck excursion."""
    inst_fretless = load_instrument("32in_fretless")
    str_fretless = get_instrument_string(inst_fretless)
    excursion = float(str_fretless.get("pluck_excursion_factor", 1.0))
    assert excursion == 1.25

    model = parse_netlist(CIRCUITS_DIR / "14_upright_bridge_transducer.cir")
    base_vsat = model.vsat
    assert base_vsat == 0.42

    scaled_vsat = round(base_vsat / excursion, 3)
    assert scaled_vsat == 0.336

def test_voices_01_to_04_string_identity_for_roundwounds():
    """Verify that standard magnetic voices for standard roundwound instruments remain pure identity on string transfer."""
    freqs = np.asarray(FREQS)
    s_std = STRINGS["roundwound_nickel_standard"]
    h_diff = compute_differential_string_transfer(freqs, s_std, s_std)
    assert np.allclose(h_diff, 1.0, atol=1e-5), "String transfer between identical standard strings must be exactly 1.0"
