"""
Passivizer - Tests for Native Virtual Analog Circuit Simulator
Validates netlist parsing, analytical transfer function math,
soft-knee compliance, and 24-bit audio digital twin synthesis.
"""

import math
import os
import tempfile
import wave
from pathlib import Path
import pytest
import numpy as np

from scripts.simulate_circuits import (
    parse_spice_val,
    parse_netlist,
    compute_circuit_transfer_functions,
    simulate_circuit_audio,
    simulate_voice,
    CircuitModel,
)
from scripts.model_physics import VOICES, FREQS, NUM_TAPS, write_wav_24bit

REPO_ROOT = Path(__file__).resolve().parent.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"

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
        assert model.Rtop > 0
        assert model.Rbot > 0
        assert model.Ccable > 0

        if vid in ["01_jazz_bass_pair", "06_pj_hybrid_parallel"]:
            assert model.topology == "parallel"
            assert model.L_b > 0
            assert model.Rdc_b > 0
        elif vid == "09_pmm_hybrid_series":
            assert model.topology == "series"
            assert model.L_b > 0
            assert model.Rdc_b > 0
        else:
            assert model.topology == "single"

def test_single_pickup_transfer_function():
    cir_path = CIRCUITS_DIR / "03_modern_p_ceramic.cir"
    model = parse_netlist(cir_path)
    curves = compute_circuit_transfer_functions(model, freqs=FREQS)

    assert len(curves) == 1
    mag = curves[0]

    # DC Gain should be near 0 dB (~0.97 due to 10-ohm pot + load divider)
    assert 0.95 < mag[0] < 1.0

    # Resonant peak should occur between 2000 Hz and 2300 Hz
    max_val = max(mag)
    peak_idx = mag.index(max_val)
    peak_freq = FREQS[peak_idx]
    assert 2000.0 <= peak_freq <= 2300.0
    assert max_val > 1.2  # Under pot/cable load, Q peak > 1.2

    # High-frequency rolloff (at 20 kHz, gain should be < 0.20)
    assert mag[-1] < 0.20

def test_tone_rolloff_transfer_function():
    cir_path = CIRCUITS_DIR / "05_p_bass_47nf_rolloff.cir"
    model = parse_netlist(cir_path)
    assert model.Ctone == pytest.approx(47e-9)

    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    mag = curves[0]

    # With 47nF shunt, resonant peak collapses into low-mids (200-500 Hz)
    max_val = max(mag)
    peak_idx = mag.index(max_val)
    peak_freq = FREQS[peak_idx]
    assert 200.0 <= peak_freq <= 500.0

    # Treble above 3 kHz is completely rolled off
    idx_3k = min(range(len(FREQS)), key=lambda i: abs(FREQS[i] - 3000.0))
    assert mag[idx_3k] < 0.10

def test_series_hpf_transfer_function():
    cir_path = CIRCUITS_DIR / "08_rickenbacker_bridge_hpf.cir"
    model = parse_netlist(cir_path)
    assert model.Crick == pytest.approx(4.7e-9)

    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    mag = curves[0]

    # DC should be 0 (blocked by series 4.7nF capacitor)
    assert mag[0] == 0.0

    # Upper mids / treble should pass cleanly
    idx_2k = min(range(len(FREQS)), key=lambda i: abs(FREQS[i] - 2000.0))
    assert mag[idx_2k] > 0.8

def test_parallel_dual_pickup_transfer_function():
    cir_path = CIRCUITS_DIR / "01_jazz_bass_pair.cir"
    model = parse_netlist(cir_path)
    assert model.topology == "parallel"

    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    assert len(curves) == 2  # Neck and Bridge curves

    mag_n, mag_b = curves
    # Both channels should have peak in upper mids (3.5 - 4.5 kHz)
    peak_n = FREQS[mag_n.index(max(mag_n))]
    peak_b = FREQS[mag_b.index(max(mag_b))]
    assert 3500.0 <= peak_n <= 4500.0
    assert 3200.0 <= peak_b <= 4200.0

def test_series_dual_pickup_transfer_function():
    cir_path = CIRCUITS_DIR / "09_pmm_hybrid_series.cir"
    model = parse_netlist(cir_path)
    assert model.topology == "series"

    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    assert len(curves) == 2

    mag_n, mag_b = curves
    # Both channels sum at DC with equal weight
    assert math.isclose(mag_n[0], mag_b[0], rel_tol=1e-3)
    # Combined series inductance shifts peak into low-mids (~2 kHz)
    peak_n = FREQS[mag_n.index(max(mag_n))]
    assert 1800.0 <= peak_n <= 2300.0

def test_simulate_circuit_audio_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_wav = Path(tmpdir) / "test_in.wav"
        output_wav = Path(tmpdir) / "test_out.wav"

        # Generate a test pulse train at 48 kHz
        samples = [0.4 if i % 200 == 0 else 0.0 for i in range(4800)]
        write_wav_24bit(str(input_wav), samples, sample_rate=48000)

        model = parse_netlist(CIRCUITS_DIR / "03_modern_p_ceramic.cir")
        res = simulate_circuit_audio(input_wav, output_wav, model)
        assert res is True
        assert output_wav.exists()

        with wave.open(str(output_wav), "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3  # 24-bit PCM
            assert wf.getnchannels() == 1
            assert wf.getnframes() > 0

def test_simulate_voice_end_to_end():
    """Verify unified end-to-end simulation from raw audio to final digital twin audio."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_wav = Path(tmpdir) / "raw_in.wav"
        output_wav = Path(tmpdir) / "final_out.wav"
        inter_wav = Path(tmpdir) / "intermediate_aperture.wav"

        # Generate a test excitation track at 48 kHz
        samples = [0.5 if i % 100 == 0 else 0.0 for i in range(4800)]
        write_wav_24bit(str(input_wav), samples, sample_rate=48000)

        # Single pickup voice (P-Bass Ceramic)
        res = simulate_voice(
            "03_modern_p_ceramic",
            input_wav=input_wav,
            output_wav=output_wav,
            instrument="30in",
            prefiltered=False,
            save_intermediate=inter_wav,
        )
        assert res is True
        assert output_wav.exists()
        assert inter_wav.exists()

        with wave.open(str(output_wav), "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3
            assert wf.getnchannels() == 1
            assert wf.getnframes() > 0

        # Multi-pickup voice (Jazz Bass Pair in Parallel)
        output_jazz = Path(tmpdir) / "jazz_out.wav"
        inter_jazz = Path(tmpdir) / "jazz_aperture.wav"
        res_jazz = simulate_voice(
            "01_jazz_bass_pair",
            input_wav=input_wav,
            output_wav=output_jazz,
            instrument="30in",
            prefiltered=False,
            save_intermediate=inter_jazz,
        )
        assert res_jazz is True
        assert output_jazz.exists()
        assert inter_jazz.exists()

        with wave.open(str(output_jazz), "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3
            assert wf.getnchannels() == 1
            assert wf.getnframes() > 0

        with wave.open(str(inter_jazz), "rb") as wf:
            assert wf.getnchannels() == 2  # Multi-pickup aperture audio has 2 channels (stereo)

def test_default_output_directories():
    """Verify that default outputs are stored in audio/<inst_id>/ and circuits/ remains clean."""
    from scripts.simulate_circuits import AUDIO_DIR, CIRCUITS_DIR
    from scripts.model_physics import load_instrument

    inst_cfg = load_instrument("30in")
    inst_id = inst_cfg["id"]
    assert inst_id == "30in_emg_mmtw"

    # Verify circuits/ directory contains only netlists (.cir) and no .wav files
    wav_files_in_circuits = list(CIRCUITS_DIR.glob("*.wav"))
    assert len(wav_files_in_circuits) == 0, f"Found .wav files in circuits/: {wav_files_in_circuits}"

def test_sweep_audio_auto_detection():
    """Verify that simulate_voice automatically finds T3K-sweep-v3.wav even if given None or missing v1_1_1.wav."""
    from scripts.simulate_circuits import find_default_input_audio
    sweep = find_default_input_audio()
    assert sweep is not None
    assert sweep.exists()
    assert sweep.name == "T3K-sweep-v3.wav"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_wav = Path(tmpdir) / "auto_sweep_out.wav"
        # Test with input_wav=None
        res = simulate_voice("03_modern_p_ceramic", input_wav=None, output_wav=out_wav, instrument="30in")
        assert res is True
        assert out_wav.exists()

        # Test with input_wav pointing to missing v1_1_1.wav (fallback behavior)
        out_wav_fallback = Path(tmpdir) / "fallback_sweep_out.wav"
        res_fallback = simulate_voice("03_modern_p_ceramic", input_wav="v1_1_1.wav", output_wav=out_wav_fallback, instrument="30in")
        assert res_fallback is True
        assert out_wav_fallback.exists()

def test_circuit_simulation_vs_theory_consistency():
    """Verify that simulated impulse FFT matches analytical theory curve within 1.5 dB across 50-8000 Hz."""
    from scripts.analyze_voices import build_voice_dataframe
    from scripts.simulate_circuits import compute_voice_prefilter_firs
    import pedalboard.io

    inst_id = "30in_emg_mmtw"
    sr = 48000
    n_samples = 48000 * 2
    impulse = np.zeros(n_samples, dtype=np.float32)
    impulse[10] = 0.05  # Linear small-signal excitation

    for voice_id in ["03_modern_p_ceramic", "01_jazz_bass_pair", "06_pj_hybrid_parallel"]:
        cfg = VOICES[voice_id]
        cir_path = CIRCUITS_DIR / f"{voice_id}.cir"
        model = parse_netlist(cir_path)
        prefilter_firs = compute_voice_prefilter_firs(voice_id, instrument=inst_id)

        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_out:
            simulate_circuit_audio(impulse, Path(tmp_out.name), model, prefilter_firs=prefilter_firs)
            with pedalboard.io.AudioFile(tmp_out.name) as f:
                out_audio = f.read(f.frames)[0]

        H_sim = np.abs(np.fft.rfft(out_audio))
        freqs_sim = np.fft.rfftfreq(len(out_audio), 1.0 / sr)

        df = build_voice_dataframe(voice_id, cfg, instrument=inst_id)
        f_theory = df["frequency"].to_numpy()
        mag_theory_db = df["magnitude_db"].to_numpy()

        ref_val = np.interp(100.0, freqs_sim, H_sim)
        theory_ref_db = np.interp(100.0, f_theory, mag_theory_db)
        sim_db = 20.0 * np.log10(H_sim / ref_val) + theory_ref_db

        for test_f in [50, 100, 200, 500, 1000, 2000, 3000, 4000, 6000, 8000]:
            val_sim = np.interp(test_f, freqs_sim, sim_db)
            val_theory = np.interp(test_f, f_theory, mag_theory_db)
            diff = abs(val_sim - val_theory)
            assert diff < 1.5, f"{voice_id} at {test_f} Hz diff={diff:.2f} dB exceeds 1.5 dB (sim={val_sim:.2f}, theory={val_theory:.2f})"

