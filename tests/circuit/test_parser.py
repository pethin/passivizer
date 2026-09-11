"""
Tests for circuit parser, netlist validation, and audio discovery utilities.
"""

from pathlib import Path
import tempfile
import pytest

from allomorph.circuit import (
    parse_spice_val,
    parse_netlist,
    find_default_input_audio,
    simulate_voice,
    AUDIO_DIR,
    CIRCUITS_DIR,
    REPO_ROOT,
)
from allomorph.config import VOICES, load_instrument


def test_parse_spice_val():
    assert parse_spice_val("4.8") == pytest.approx(4.8)
    assert parse_spice_val("9.5k") == pytest.approx(9500.0)
    assert parse_spice_val("110k") == pytest.approx(110000.0)
    assert parse_spice_val("80p") == pytest.approx(80e-12)
    assert parse_spice_val("47n") == pytest.approx(47e-9)
    assert parse_spice_val("20u") == pytest.approx(20e-6)
    assert parse_spice_val("1Meg") == pytest.approx(1e6)
    assert parse_spice_val("10") == pytest.approx(10.0)


def test_parse_all_circuit_netlists():
    for vid, cfg in VOICES.items():
        cir_path = REPO_ROOT / cfg["circuit"]
        assert cir_path.exists(), f"Netlist missing: {cir_path}"
        model = parse_netlist(cir_path)

        assert model.L > 0
        assert model.Rdc > 0
        assert model.Reddy > 0
        assert model.Ccoil > 0
        assert model.Ccable > 0

        if model.has_active_buffer:
            assert model.R_out > 0
            assert model.R_preamp_in > 0
            assert model.C_preamp_in > 0
        else:
            assert model.Rtop > 0
            assert model.Rbot > 0

        if vid in [
            "01_modern_jazz_active",
            "02_jazz_bass_pair",
            "02b_jazz_bass_pair_22nf",
            "02c_jazz_bridge_growl_bias",
            "07_modern_pj_active",
            "08_vintage_pj_passive",
            "11_modern_pmm_active",
        ]:
            assert model.topology == "parallel"
            assert model.L_b > 0
            assert model.Rdc_b > 0
        elif vid in ["11_pmm_hybrid_series", "11b_pmm_hybrid_series"]:
            assert model.topology == "series"
            assert model.L_b > 0
            assert model.Rdc_b > 0
        else:
            assert model.topology == "single"


def test_default_output_directories():
    """Verify that default outputs are stored in audio/<inst_id>/ and circuits/ remains clean."""
    inst_cfg = load_instrument("30in")
    inst_id = inst_cfg["id"]
    assert inst_id == "30in_emg_mmtw"

    # Verify circuits/ directory contains only netlists (.cir) and no .wav files
    wav_files_in_circuits = list(CIRCUITS_DIR.glob("*.wav"))
    assert len(wav_files_in_circuits) == 0, f"Found .wav files in circuits/: {wav_files_in_circuits}"


def test_sweep_audio_auto_detection():
    """Verify that simulate_voice automatically finds T3K-sweep-v3.wav even if given None or missing input path."""
    sweep = find_default_input_audio()
    assert sweep is not None
    assert sweep.exists()
    assert sweep.name == "T3K-sweep-v3.wav"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_wav = Path(tmpdir) / "auto_sweep_out.wav"
        # Test with input_wav=None
        res = simulate_voice("04_modern_p_ceramic", input_wav=None, output_wav=out_wav, instrument="30in", max_samples=4800)
        assert res is True
        assert out_wav.exists() and out_wav.stat().st_size > 1000

        # Test with input_wav pointing to missing file (fallback behavior to T3K-sweep-v3.wav)
        out_wav_fallback = Path(tmpdir) / "fallback_sweep_out.wav"
        res_fallback = simulate_voice("04_modern_p_ceramic", input_wav="missing_sweep.wav", output_wav=out_wav_fallback, instrument="30in", max_samples=4800)
        assert res_fallback is True
        assert out_wav_fallback.exists() and out_wav_fallback.stat().st_size > 1000
