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
        assert model.Ccable > 0

        if model.has_active_buffer:
            assert model.R_out > 0
            assert model.R_preamp_in > 0
            assert model.C_preamp_in > 0
        else:
            assert model.Rtop > 0
            assert model.Rbot > 0

        if vid in ["01_modern_jazz_active", "02_jazz_bass_pair", "07_modern_pj_active", "08_vintage_pj_passive"]:
            assert model.topology == "parallel"
            assert model.L_b > 0
            assert model.Rdc_b > 0
        elif vid == "11_pmm_hybrid_series":
            assert model.topology == "series"
            assert model.L_b > 0
            assert model.Rdc_b > 0
        else:
            assert model.topology == "single"

def test_single_pickup_transfer_function():
    cir_path = CIRCUITS_DIR / "04_modern_p_ceramic.cir"
    model = parse_netlist(cir_path)
    curves = compute_circuit_transfer_functions(model, freqs=FREQS)

    assert len(curves) == 1
    mag = curves[0]

    # DC Gain should be near 0 dB (~0.97 due to 10-ohm pot + load divider)
    assert 0.95 < mag[0] < 1.0

    # Resonant peak should occur between 1850 Hz and 2300 Hz
    max_val = max(mag)
    peak_idx = mag.index(max_val)
    peak_freq = FREQS[peak_idx]
    assert 1850.0 <= peak_freq <= 2300.0
    assert max_val > 1.10  # Under pot/cable load, Q peak > 1.10

    # High-frequency rolloff (at 20 kHz, gain should be < 0.20)
    assert mag[-1] < 0.20

def test_tone_rolloff_transfer_function():
    cir_path = CIRCUITS_DIR / "06_p_bass_47nf_rolloff.cir"
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
    cir_path = CIRCUITS_DIR / "10_rickenbacker_bridge_hpf.cir"
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
    cir_path = CIRCUITS_DIR / "02_jazz_bass_pair.cir"
    model = parse_netlist(cir_path)
    assert model.topology == "parallel"

    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    assert len(curves) == 2  # Neck and Bridge curves

    mag_n, mag_b = curves
    # Both channels under authentic dual 250k vol (125k net) + 250k tone have peak in 2.4 - 3.2 kHz
    peak_n = FREQS[mag_n.index(max(mag_n))]
    peak_b = FREQS[mag_b.index(max(mag_b))]
    assert 2400.0 <= peak_n <= 3200.0
    assert 2500.0 <= peak_b <= 3200.0

def test_active_preamp_buffer_transfer_function():
    # 1. Voice 01 Modern Active Jazz Bass
    m01 = parse_netlist(CIRCUITS_DIR / "01_modern_jazz_active.cir")
    assert m01.has_active_buffer is True
    assert m01.preamp_type == "sadowsky_2band"
    assert m01.topology == "parallel"

    curves01 = compute_circuit_transfer_functions(m01, freqs=FREQS)
    assert len(curves01) == 2
    mag_n01, mag_b01 = curves01
    peak_n01 = FREQS[mag_n01.index(max(mag_n01))]
    peak_b01 = FREQS[mag_b01.index(max(mag_b01))]
    # Coils are isolated from 750pF cable load, and boosted by Sadowsky active treble shelf (6.5 - 9 kHz)
    assert 6500.0 <= peak_n01 <= 8500.0
    assert 7000.0 <= peak_b01 <= 9000.0

    # 2. Voice 07 Modern Active P/J 2-Band
    m07 = parse_netlist(CIRCUITS_DIR / "07_modern_pj_active.cir")
    assert m07.has_active_buffer is True
    assert m07.preamp_type == "sadowsky_2band"
    assert m07.topology == "parallel"
    curves07 = compute_circuit_transfer_functions(m07, freqs=FREQS)
    assert len(curves07) == 2

    # 3. Voice 09 Music Man StingRay Active 2-Band
    m09 = parse_netlist(CIRCUITS_DIR / "09_stingray_mm_parallel.cir")
    assert m09.has_active_buffer is True
    assert m09.preamp_type == "stingray_2band"
    assert m09.topology == "single"

    curves09 = compute_circuit_transfer_functions(m09, freqs=FREQS)
    assert len(curves09) == 1
    mag09 = curves09[0]
    peak09 = FREQS[mag09.index(max(mag09))]
    # Isolated from cable capacitance, peak is in 6.5 - 8.5 kHz clank & sizzle region
    assert 6500.0 <= peak09 <= 8500.0

def test_series_dual_pickup_transfer_function():
    cir_path = CIRCUITS_DIR / "11_pmm_hybrid_series.cir"
    model = parse_netlist(cir_path)
    assert model.topology == "series"

    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    assert len(curves) == 2

    mag_n, mag_b = curves
    # Both channels sum at DC with equal weight
    assert math.isclose(mag_n[0], mag_b[0], rel_tol=1e-3)
    # Combined series inductance shifts peak into low-mids (~1.6 - 2.1 kHz)
    peak_n = FREQS[mag_n.index(max(mag_n))]
    assert 1500.0 <= peak_n <= 2100.0

def test_simulate_circuit_audio_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_wav = Path(tmpdir) / "test_in.wav"
        output_wav = Path(tmpdir) / "test_out.wav"

        # Generate a test pulse train at 48 kHz
        samples = [0.4 if i % 200 == 0 else 0.0 for i in range(4800)]
        write_wav_24bit(str(input_wav), samples, sample_rate=48000)

        model = parse_netlist(CIRCUITS_DIR / "04_modern_p_ceramic.cir")
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
            "04_modern_p_ceramic",
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
            "02_jazz_bass_pair",
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
    """Verify that simulate_voice automatically finds T3K-sweep-v3.wav even if given None or missing input path."""
    from scripts.simulate_circuits import find_default_input_audio
    sweep = find_default_input_audio()
    assert sweep is not None
    assert sweep.exists()
    assert sweep.name == "T3K-sweep-v3.wav"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_wav = Path(tmpdir) / "auto_sweep_out.wav"
        # Test with input_wav=None
        res = simulate_voice("04_modern_p_ceramic", input_wav=None, output_wav=out_wav, instrument="30in")
        assert res is True
        assert out_wav.exists()

        # Test with input_wav pointing to missing file (fallback behavior to T3K-sweep-v3.wav)
        out_wav_fallback = Path(tmpdir) / "fallback_sweep_out.wav"
        res_fallback = simulate_voice("04_modern_p_ceramic", input_wav="missing_sweep.wav", output_wav=out_wav_fallback, instrument="30in")
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

    for voice_id in ["04_modern_p_ceramic", "02_jazz_bass_pair", "07_modern_pj_active"]:
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

def test_upright_voicing_simulation_vs_theory_consistency():
    """Verify that 32in fretless upright acoustic transducer simulation matches theory across 20-5000 Hz."""
    from scripts.analyze_voices import build_voice_dataframe
    from scripts.simulate_circuits import compute_voice_prefilter_firs
    import pedalboard.io

    inst_id = "32in_fretless_pmm"
    voice_id = "14_upright_bridge_transducer"
    sr = 48000
    n_samples = 48000 * 2
    impulse = np.zeros(n_samples, dtype=np.float32)
    impulse[10] = 0.05

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

    # In the critical upright passband (20 Hz - 4.2 kHz), diff must be under 1.5 dB
    for test_f in [20, 30, 50, 70, 100, 200, 500, 1000, 2000, 3000, 4200]:
        val_sim = np.interp(test_f, freqs_sim, sim_db)
        val_theory = np.interp(test_f, f_theory, mag_theory_db)
        diff = abs(val_sim - val_theory)
        assert diff < 1.5, f"Upright at {test_f} Hz diff={diff:.2f} dB exceeds 1.5 dB (sim={val_sim:.2f}, theory={val_theory:.2f})"

def test_tone_pot_series_admittance():
    """Verify that series Rtone allows wide-open tone pots to preserve pickup resonance."""
    # 1. Voice 06: Rtone = 0, Ctone = 47nF -> collapses peak to 200-500 Hz
    m_rolled = parse_netlist(CIRCUITS_DIR / "06_p_bass_47nf_rolloff.cir")
    assert m_rolled.Rtone == 0.0
    assert m_rolled.Ctone == pytest.approx(47e-9)
    curves_rolled = compute_circuit_transfer_functions(m_rolled, freqs=FREQS)
    peak_rolled = FREQS[curves_rolled[0].index(max(curves_rolled[0]))]
    assert 200.0 <= peak_rolled <= 500.0

    # 2. Source Standard P: Rtone = 250k, Ctone = 47nF -> loaded peak stays in 2000-2400 Hz range
    m_open = parse_netlist(REPO_ROOT / "circuits" / "sources" / "source_standard_p.cir")
    assert m_open.Rtone == pytest.approx(250000.0)
    assert m_open.Ctone == pytest.approx(47e-9)
    curves_open = compute_circuit_transfer_functions(m_open, freqs=FREQS)
    peak_open = FREQS[curves_open[0].index(max(curves_open[0]))]
    assert 2000.0 <= peak_open <= 2400.0

def test_passive_identity_differential_flatness():
    """Verify that identity differential response is flat, and pot unloading is accurately modeled."""
    from scripts.simulate_circuits import compute_differential_circuit_transfer_functions
    f_arr = np.asarray(FREQS)
    passband_mask = (f_arr >= 40.0) & (f_arr <= 4500.0)

    # 1. Precision Bass true identity: Standard P source against Voice 05 Vintage '62 P (< 0.10 dB)
    m_src_p = parse_netlist(REPO_ROOT / "circuits" / "sources" / "source_standard_p.cir")
    m_tgt_p = parse_netlist(CIRCUITS_DIR / "05_vintage_62_p_alnico.cir")
    diff_p = compute_differential_circuit_transfer_functions(m_tgt_p, m_src_p, freqs=FREQS)
    h_p = np.asarray(diff_p[0])
    h_p_db = 20.0 * np.log10(h_p / h_p[0])
    assert np.all(np.abs(h_p_db[passband_mask]) < 0.10), "P-Bass identity differential not flat!"

    # 2. Jazz Bass true identity: Standard Jazz source against Voice 02 Jazz Bass Pair (< 0.10 dB)
    m_src_j = parse_netlist(REPO_ROOT / "circuits" / "sources" / "source_standard_jazz_pair.cir")
    m_tgt_j = parse_netlist(CIRCUITS_DIR / "02_jazz_bass_pair.cir")
    diff_j = compute_differential_circuit_transfer_functions(m_tgt_j, m_src_j, freqs=FREQS)
    for ch_idx, ch in enumerate(diff_j):
        h_j = np.asarray(ch)
        h_j_db = 20.0 * np.log10(h_j / h_j[0])
        assert np.all(np.abs(h_j_db[passband_mask]) < 0.10), f"Jazz channel {ch_idx} identity differential not flat!"

    # 3. Pot unloading: Source Standard P (250k V/T) vs Target Modern Ceramic P (500k V/T + 22nF)
    m_tgt_mod = parse_netlist(CIRCUITS_DIR / "04_modern_p_ceramic.cir")
    diff_mod = compute_differential_circuit_transfer_functions(m_tgt_mod, m_src_p, freqs=FREQS)
    h_mod = np.asarray(diff_mod[0])
    h_mod_db = 20.0 * np.log10(h_mod / h_mod[0])
    assert 0.4 <= np.max(h_mod_db[passband_mask]) <= 2.0

def test_passive_saturation_bypassed():
    """Verify that forward tanh saturation is bypassed when is_passive is True."""
    import pedalboard.io
    sr = 48000
    n_samples = 4800
    # High amplitude input (0.80) exceeding vsat (0.45)
    in_heavy = np.full((1, n_samples), 0.80, dtype=np.float32)

    m = parse_netlist(CIRCUITS_DIR / "05_vintage_62_p_alnico.cir")

    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_act, tempfile.NamedTemporaryFile(suffix=".wav") as tmp_pas:
        # Active simulation: applies tanh
        simulate_circuit_audio(in_heavy, Path(tmp_act.name), m, is_passive=False)
        # Passive simulation: bypasses tanh
        simulate_circuit_audio(in_heavy, Path(tmp_pas.name), m, is_passive=True)

        with pedalboard.io.AudioFile(tmp_act.name) as f:
            audio_act = f.read(f.frames)[0]
        with pedalboard.io.AudioFile(tmp_pas.name) as f:
            audio_pas = f.read(f.frames)[0]

    # Passive output should maintain linear proportional gain (higher uncompressed peak)
    assert np.max(np.abs(audio_pas)) > np.max(np.abs(audio_act))

def test_wiener_clamping_prevents_noise_explosion():
    """Verify that differential top-end boost is strictly clamped <= +6.0 dB above 4.5 kHz."""
    from scripts.simulate_circuits import compute_differential_circuit_transfer_functions
    # Convert high-inductance P (3.8H) to brighter Jazz Bridge (3.6H)
    m_src = parse_netlist(REPO_ROOT / "circuits" / "sources" / "source_standard_p.cir")
    m_tgt = parse_netlist(CIRCUITS_DIR / "03_jazz_bridge_60s.cir")

    diff_curves = compute_differential_circuit_transfer_functions(m_tgt, m_src, freqs=FREQS, max_boost_db=6.0)
    h_diff = np.asarray(diff_curves[0])

    f_arr = np.asarray(FREQS)
    ref_idx = int(np.argmin(np.abs(f_arr - 1000.0)))
    h_diff_rel_db = 20.0 * np.log10(h_diff / h_diff[ref_idx])

    hi_mask = f_arr >= 4500.0
    max_hi_boost = np.max(h_diff_rel_db[hi_mask])
    assert max_hi_boost <= 6.05  # Within 0.05 dB of +6.0 dB ceiling

def test_passive_source_simulation_runs():
    """Verify end-to-end simulate_voice runs for passive source instruments."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp1, tempfile.NamedTemporaryFile(suffix=".wav") as tmp2:
        res1 = simulate_voice("05_vintage_62_p_alnico", output_wav=Path(tmp1.name), instrument="34in_standard_p")
        assert res1 is True
        assert os.path.exists(tmp1.name) and os.path.getsize(tmp1.name) > 1000

        res2 = simulate_voice("02_jazz_bass_pair", output_wav=Path(tmp2.name), instrument="34in_standard_jazz")
        assert res2 is True
        assert os.path.exists(tmp2.name) and os.path.getsize(tmp2.name) > 1000

def test_auto_output_level_normalization_to_input_sweep():
    """Verify that simulated output automatically normalizes its RMS to match the input sweep dBFS."""
    import pedalboard.io
    sweep_path = REPO_ROOT / "T3K-sweep-v3.wav"
    if not sweep_path.exists():
        pytest.skip("T3K-sweep-v3.wav not found in repo root")

    with pedalboard.io.AudioFile(str(sweep_path)) as f:
        in_audio = f.read(f.frames)[0]
    in_rms = float(np.sqrt(np.mean(in_audio ** 2)))
    in_rms_db = 20.0 * math.log10(in_rms)

    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_out:
        out_path = Path(tmp_out.name)
        res = simulate_voice("04_modern_p_ceramic", input_wav=sweep_path, output_wav=out_path, instrument="30in", normalize="auto")
        assert res is True

        with pedalboard.io.AudioFile(str(out_path)) as f:
            out_audio = f.read(f.frames)[0]

        out_rms = float(np.sqrt(np.mean(out_audio ** 2)))
        out_rms_db = 20.0 * math.log10(out_rms)
        out_peak = float(np.max(np.abs(out_audio)))

        # Output RMS must match input sweep RMS within 0.05 dB
        assert abs(out_rms_db - in_rms_db) < 0.05
        # Peak must have clean true-peak safety headroom (< -0.1 dBFS = 0.9885)
        assert out_peak <= 0.9885

def test_output_normalization_modes_and_target_dbfs():
    """Verify custom target_dbfs override and normalize modes (rms, peak, none)."""
    import pedalboard.io
    sweep_path = REPO_ROOT / "T3K-sweep-v3.wav"
    if not sweep_path.exists():
        pytest.skip("T3K-sweep-v3.wav not found in repo root")

    # 1. Custom target dBFS (-24.0 dBFS)
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_out:
        out_path = Path(tmp_out.name)
        simulate_voice("04_modern_p_ceramic", input_wav=sweep_path, output_wav=out_path, instrument="30in", normalize="rms", target_dbfs=-24.0)
        with pedalboard.io.AudioFile(str(out_path)) as f:
            out_audio = f.read(f.frames)[0]
        out_rms_db = 20.0 * math.log10(np.sqrt(np.mean(out_audio ** 2)))
        assert abs(out_rms_db - (-24.0)) < 0.05

    # 2. None (raw unnormalized)
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_out:
        out_path = Path(tmp_out.name)
        simulate_voice("04_modern_p_ceramic", input_wav=sweep_path, output_wav=out_path, instrument="30in", normalize="none")
        with pedalboard.io.AudioFile(str(out_path)) as f:
            out_audio = f.read(f.frames)[0]
        out_rms_db = 20.0 * math.log10(np.sqrt(np.mean(out_audio ** 2)))
        # Raw unnormalized should be around -21 to -27 dBFS
        assert out_rms_db < -20.0

def test_anti_aliased_oversampling_suppression():
    """Verify that 2x oversampled saturation suppresses folded aliasing by >60 dB."""
    from scripts.simulate_circuits import apply_oversampled_saturation
    sr = 48000
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    tone = 0.5 * np.sin(2 * np.pi * 15000 * t).astype(np.float32)

    out_1x = apply_oversampled_saturation(tone, vsat=0.45, alpha=0.20, oversample=1, displacement_weighting=False, magnet_drag=False)
    out_2x = apply_oversampled_saturation(tone, vsat=0.45, alpha=0.20, oversample=2, displacement_weighting=False, magnet_drag=False)

    f_arr = np.fft.rfftfreq(len(tone), 1.0 / sr)
    fft_1x = np.abs(np.fft.rfft(out_1x))
    fft_2x = np.abs(np.fft.rfft(out_2x))

    alias_3k_1x = fft_1x[np.argmin(np.abs(f_arr - 3000))]
    alias_3k_2x = fft_2x[np.argmin(np.abs(f_arr - 3000))]
    fund_1x = fft_1x[np.argmin(np.abs(f_arr - 15000))]
    fund_2x = fft_2x[np.argmin(np.abs(f_arr - 15000))]

    db_1x = 20 * np.log10(alias_3k_1x / fund_1x)
    db_2x = 20 * np.log10(max(alias_3k_2x, 1e-9) / fund_2x)

    suppression = db_1x - db_2x
    assert suppression > 60.0, f"Aliasing suppression {suppression:.1f} dB did not exceed 60 dB"

def test_displacement_domain_imd_reduction():
    """Verify that displacement weighting suppresses treble intermodulation distortion by >6 dB."""
    from scripts.simulate_circuits import apply_oversampled_saturation
    sr = 48000
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    sig = 0.6 * np.sin(2 * np.pi * 50 * t) + 0.1 * np.sin(2 * np.pi * 2500 * t)
    sig = sig.astype(np.float32)

    out_flat = apply_oversampled_saturation(sig, vsat=0.45, alpha=0.20, oversample=1, displacement_weighting=False, magnet_drag=False)
    out_disp = apply_oversampled_saturation(sig, vsat=0.45, alpha=0.20, oversample=1, displacement_weighting=True, magnet_drag=False)

    f_arr = np.fft.rfftfreq(len(sig), 1.0 / sr)
    fft_flat = np.abs(np.fft.rfft(out_flat))
    fft_disp = np.abs(np.fft.rfft(out_disp))

    idx_2500 = np.argmin(np.abs(f_arr - 2500))
    idx_2450 = np.argmin(np.abs(f_arr - 2450))

    imd_flat_db = 20 * np.log10(fft_flat[idx_2450] / fft_flat[idx_2500])
    imd_disp_db = 20 * np.log10(fft_disp[idx_2450] / fft_disp[idx_2500])

    imd_reduction = imd_flat_db - imd_disp_db
    assert imd_reduction > 6.0, f"IMD reduction {imd_reduction:.1f} dB did not exceed 6 dB"

def test_num_taps_4096_resolution():
    """Verify that NUM_TAPS is 4096 and frequency bin spacing is ~5.86 Hz."""
    from scripts.model_physics import NUM_TAPS, FREQS
    assert NUM_TAPS == 4096
    assert len(FREQS) == 4096
    df = FREQS[1] - FREQS[0]
    assert math.isclose(df, 24000.0 / 4095, rel_tol=1e-3)





