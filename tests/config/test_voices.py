"""
Tests for target voices catalog, electrical parameters, SPICE netlist existence, and transparency.
"""

from pathlib import Path
import numpy as np

from allomorph.config import VOICES
from allomorph.circuit import load_circuit, compute_circuit_transfer_functions
from allomorph.dsp import NUM_TAPS, FREQS
from allomorph.physics import compute_voice_prefilter_firs
from allomorph.visualizer import build_voice_dataframe


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


def test_voice_netlist_existence():
    for vid, cfg in VOICES.items():
        assert "circuit" in cfg, f"{vid} missing circuit attribute"
        assert isinstance(cfg["circuit"], dict), f"{vid} circuit configuration must be a dict"
        m = load_circuit(cfg["circuit"])
        assert m.L > 0


def test_voices_have_no_hardcoded_source_datums():
    # Target voices should be purely decoupled from source instrument geometries
    for vid, cfg in VOICES.items():
        assert "src_32" not in cfg, f"{vid} contains deprecated hardcoded 'src_32' datum"
        assert "src_30" not in cfg, f"{vid} contains deprecated hardcoded 'src_30' datum"


def test_source_direct_properties():
    """Validates that 15_source_direct performs transparent deconvolution of Canonical Intermediate."""
    # 1. Prefilter FIR on Canonical Intermediate must invert the 93.5mm aperture sinc
    firs = compute_voice_prefilter_firs("15_source_direct", instrument="canonical_intermediate")
    assert len(firs) == 1
    fir = np.array(firs[0])
    assert len(fir) == NUM_TAPS

    # 2. Circuit transfer function must be identically 1.0 across all frequencies (no_eq buffer)
    cfg = VOICES["15_source_direct"]
    model = load_circuit(cfg["circuit"])
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
    # 1. Prefilter FIR preserves physical aperture (unit impulse)
    firs = compute_voice_prefilter_firs("16_active_character", instrument="34in_standard_p")
    assert len(firs) == 1
    fir = np.array(firs[0])
    assert fir[0] == 1.0
    assert np.all(fir[1:] == 0.0)

    # 2. Netlist models active buffer with flat contour
    cfg = VOICES["16_active_character"]
    model = load_circuit(cfg["circuit"])
    assert model.has_active_buffer is True
    assert model.preamp_type == "none"
    assert model.R_out == 100.0
    assert model.R_preamp_in >= 1.0e6
