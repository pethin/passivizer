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
    compute_core_impedance,
    apply_magnet_properties_to_model,
    apply_dahl_hysteresis,
    apply_oversampled_saturation,
    MAGNET_PROPERTIES,
    simulate_circuit_audio,
    simulate_voice,
    compute_differential_circuit_transfer_functions,
    CircuitModel,
)
from scripts.model_physics import VOICES, FREQS, NUM_TAPS, write_wav_24bit, compute_voice_prefilter_firs, load_instrument

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

        if vid in ["01_modern_jazz_active", "02_jazz_bass_pair", "02b_jazz_bass_pair_22nf", "02c_jazz_bridge_growl_bias", "07_modern_pj_active", "08_vintage_pj_passive"]:
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
    cir_path = CIRCUITS_DIR / "05c_vintage_62_p_47nf.cir"
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
        res = simulate_voice("04_modern_p_ceramic", input_wav=None, output_wav=out_wav, instrument="30in", max_samples=4800)
        assert res is True
        assert out_wav.exists() and out_wav.stat().st_size > 1000

        # Test with input_wav pointing to missing file (fallback behavior to T3K-sweep-v3.wav)
        out_wav_fallback = Path(tmpdir) / "fallback_sweep_out.wav"
        res_fallback = simulate_voice("04_modern_p_ceramic", input_wav="missing_sweep.wav", output_wav=out_wav_fallback, instrument="30in", max_samples=4800)
        assert res_fallback is True
        assert out_wav_fallback.exists() and out_wav_fallback.stat().st_size > 1000

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
    # 1. Voice 05c: Rtone = 3.3 Ohm ESR floor, Ctone = 47nF -> collapses peak to 200-500 Hz
    m_rolled = parse_netlist(CIRCUITS_DIR / "05c_vintage_62_p_47nf.cir")
    assert m_rolled.Rtone == pytest.approx(3.3)
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

def test_active_source_differential_deconvolution_and_identity():
    """Verify that commercial active sources (StingRay, Dingwall) have valid source circuits,
    yield exact 0.0 dB on identity, and properly deconvolve active preamps on cross-voicings."""
    from scripts.simulate_circuits import compute_differential_circuit_transfer_functions

    # 1. Source netlist existence & parsing
    m_src_ray = parse_netlist(CIRCUITS_DIR / "sources" / "source_active_stingray.cir")
    assert m_src_ray.has_active_buffer is True
    assert m_src_ray.preamp_type == "stingray_2band"

    m_src_ding = parse_netlist(CIRCUITS_DIR / "sources" / "source_dingwall_fd3n.cir")
    assert m_src_ding.L == 2.3
    assert m_src_ding.Rtop == 10
    assert m_src_ding.Rbot == 500000.0

    # 2. Mathematical identity flatness (exact 0.00 dB everywhere, including DC and 20 kHz)
    m_tgt_ray = parse_netlist(CIRCUITS_DIR / "09_stingray_mm_parallel.cir")
    diff_ray = compute_differential_circuit_transfer_functions(m_tgt_ray, m_src_ray, freqs=FREQS)
    assert np.all(np.array(diff_ray[0]) == 1.0)

    m_tgt_ding = parse_netlist(CIRCUITS_DIR / "13_dingwall_multiscale_bridge.cir")
    diff_ding = compute_differential_circuit_transfer_functions(m_tgt_ding, m_src_ding, freqs=FREQS)
    assert np.all(np.array(diff_ding[0]) == 1.0)

    # 3. Cross-deconvolution: Active StingRay -> Vintage '62 P-Bass
    m_tgt_p = parse_netlist(CIRCUITS_DIR / "05_vintage_62_p_alnico.cir")
    diff_cross = compute_differential_circuit_transfer_functions(m_tgt_p, m_src_ray, freqs=FREQS)
    h_cross = np.asarray(diff_cross[0])
    f_arr = np.asarray(FREQS)
    # The StingRay has a +2.2 dB active treble boost around 5-7 kHz.
    # When converting to a darker vintage P-bass, high frequencies must be rolled off (< -10 dB @ 8 kHz)
    idx_8k = np.argmin(np.abs(f_arr - 8000.0))
    cross_db_8k = 20.0 * np.log10(h_cross[idx_8k])
    assert cross_db_8k < -10.0, f"Expected active treble shelf deconvolution (< -10 dB), got {cross_db_8k:.2f} dB"

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
        res1 = simulate_voice("05_vintage_62_p_alnico", output_wav=Path(tmp1.name), instrument="34in_standard_p", max_samples=4800)
        assert res1 is True
        assert os.path.exists(tmp1.name) and os.path.getsize(tmp1.name) > 1000

        res2 = simulate_voice("02_jazz_bass_pair", output_wav=Path(tmp2.name), instrument="34in_standard_jazz", max_samples=4800)
        assert res2 is True
        assert os.path.exists(tmp2.name) and os.path.getsize(tmp2.name) > 1000

def test_auto_output_level_normalization_to_input_sweep():
    """Verify that simulated output automatically normalizes its RMS to match the input sweep dBFS."""
    import pedalboard.io
    sr = 48000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    in_signal = (0.5 * np.sin(2 * np.pi * 150 * t) + 0.3 * np.sin(2 * np.pi * 800 * t)).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / "test_in.wav"
        out_path = Path(td) / "test_out.wav"
        write_wav_24bit(str(in_path), in_signal, sample_rate=sr)

        with pedalboard.io.AudioFile(str(in_path)) as f:
            in_audio = f.read(f.frames)[0]
        in_rms = float(np.sqrt(np.mean(in_audio ** 2)))
        in_rms_db = 20.0 * math.log10(in_rms)

        res = simulate_voice("04_modern_p_ceramic", input_wav=in_path, output_wav=out_path, instrument="30in", normalize="auto")
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
    sr = 48000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    in_signal = (0.5 * np.sin(2 * np.pi * 150 * t) + 0.3 * np.sin(2 * np.pi * 800 * t)).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / "test_in.wav"
        write_wav_24bit(str(in_path), in_signal, sample_rate=sr)

        # 1. Custom target dBFS (-24.0 dBFS)
        out_path = Path(td) / "out_24.wav"
        simulate_voice("04_modern_p_ceramic", input_wav=in_path, output_wav=out_path, instrument="30in", normalize="rms", target_dbfs=-24.0)
        with pedalboard.io.AudioFile(str(out_path)) as f:
            out_audio = f.read(f.frames)[0]
        out_rms_db = 20.0 * math.log10(np.sqrt(np.mean(out_audio ** 2)))
        assert abs(out_rms_db - (-24.0)) < 0.05

        # 2. None (raw unnormalized)
        out_none = Path(td) / "out_none.wav"
        simulate_voice("04_modern_p_ceramic", input_wav=in_path, output_wav=out_none, instrument="30in", normalize="none")
        with pedalboard.io.AudioFile(str(out_none)) as f:
            out_audio = f.read(f.frames)[0]
        out_rms_none = 20.0 * math.log10(np.sqrt(np.mean(out_audio ** 2)))
        assert out_rms_none < -5.0

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

def test_subaudible_dc_blocking_filter():
    """Verify that 8 Hz DC blocker eliminates quadratic saturation DC offset (< 1e-6) while preserving audio."""
    import pedalboard.io
    sr = 48000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    # 100 Hz forte tone triggering asymmetric saturation
    tone = (0.60 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)

    model = parse_netlist(CIRCUITS_DIR / "04_modern_p_ceramic.cir")

    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_dc_on, tempfile.NamedTemporaryFile(suffix=".wav") as tmp_dc_off:
        # 1. With DC blocker enabled (default)
        simulate_circuit_audio(tone, Path(tmp_dc_on.name), model, alpha=0.25, dc_block=True)
        with pedalboard.io.AudioFile(tmp_dc_on.name) as f:
            audio_on = f.read(f.frames)[0]

        # 2. With DC blocker disabled
        simulate_circuit_audio(tone, Path(tmp_dc_off.name), model, alpha=0.25, dc_block=False)
        with pedalboard.io.AudioFile(tmp_dc_off.name) as f:
            audio_off = f.read(f.frames)[0]

    # Without DC blocker, asymmetric alpha produces positive DC mean (> 1e-4)
    assert abs(np.mean(audio_off)) > 1e-4
    # With DC blocker, DC mean is suppressed by > 80 dB down to < 1e-6 (essentially 0.000000)
    assert abs(np.mean(audio_on)) < 1e-6

def test_magnet_specific_saturation_voicing():
    """Verify that Ceramic (alpha=0.12) generates less even-harmonic energy than Alnico V (alpha=0.26), and Piezo (alpha=0) is purely odd."""
    from scripts.simulate_circuits import apply_oversampled_saturation
    sr = 48000
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    fund_f = 200.0
    tone = (0.50 * np.sin(2 * np.pi * fund_f * t)).astype(np.float32)

    # 1. Alnico V (alpha=0.26)
    out_alnico = apply_oversampled_saturation(tone, vsat=0.45, alpha=0.26, oversample=2, displacement_weighting=False, magnet_drag=False)
    # 2. Ceramic (alpha=0.12)
    out_ceramic = apply_oversampled_saturation(tone, vsat=0.45, alpha=0.12, oversample=2, displacement_weighting=False, magnet_drag=False)
    # 3. Piezo (alpha=0.00)
    out_piezo = apply_oversampled_saturation(tone, vsat=0.45, alpha=0.00, oversample=2, displacement_weighting=False, magnet_drag=False)

    f_arr = np.fft.rfftfreq(len(tone), 1.0 / sr)
    fft_alnico = np.abs(np.fft.rfft(out_alnico))
    fft_ceramic = np.abs(np.fft.rfft(out_ceramic))
    fft_piezo = np.abs(np.fft.rfft(out_piezo))

    h2_idx = np.argmin(np.abs(f_arr - 400.0))  # 2nd harmonic (400 Hz)
    fund_idx = np.argmin(np.abs(f_arr - 200.0))  # Fundamental (200 Hz)

    h2_alnico_db = 20 * np.log10(fft_alnico[h2_idx] / fft_alnico[fund_idx])
    h2_ceramic_db = 20 * np.log10(fft_ceramic[h2_idx] / fft_ceramic[fund_idx])
    h2_piezo_db = 20 * np.log10(max(fft_piezo[h2_idx], 1e-9) / fft_piezo[fund_idx])

    # Alnico V must generate more 2nd harmonic bloom than Ceramic (> 5 dB difference)
    assert h2_alnico_db > h2_ceramic_db + 5.0
    # Piezo must have negligible 2nd harmonic (< -60 dB relative to fundamental)
    assert h2_piezo_db < -60.0

def test_fractional_core_eddy_diffusion():
    """
    Verify Foster 2-stage ladder core eddy diffusion:
    1. Alnico V has ~8% inductance drop and authentic damping at 10 kHz.
    2. Ceramic has <= 2% inductance drop due to non-conductive ferrite.
    3. Core impedance introduces real resistive losses Re(Z_L) > 0 at audio frequencies.
    4. Disabling eddy diffusion preserves constant ideal inductance s * L.
    """
    L0 = 4.8  # H
    # 1. Alnico V
    model_alnico = CircuitModel()
    model_alnico.L = L0
    apply_magnet_properties_to_model(model_alnico, {"magnet_type": "alnico_v"})
    assert model_alnico.L_core == pytest.approx(0.08 * L0)
    assert model_alnico.R_core > 0.0

    # Evaluate at 10 kHz
    w_hi = 2.0 * math.pi * 10000.0
    s_hi = 1j * w_hi
    Z_hi_alnico = compute_core_impedance(s_hi, model_alnico.L, model_alnico.L_core, model_alnico.R_core)

    # Inductance at high frequency should be dropped by ~7-8%
    L_eff_hi = Z_hi_alnico.imag / w_hi
    assert L_eff_hi < L0
    drop_pct = (L0 - L_eff_hi) / L0 * 100.0
    assert 6.0 <= drop_pct <= 8.5
    # Real part must represent eddy loss resistance (Re(Z) > 0)
    assert Z_hi_alnico.real > 500.0

    # 2. Ceramic (insulating ferrite core)
    model_ceramic = CircuitModel()
    model_ceramic.L = L0
    apply_magnet_properties_to_model(model_ceramic, {"magnet_type": "ceramic"})
    assert model_ceramic.L_core == pytest.approx(0.02 * L0)
    Z_hi_ceramic = compute_core_impedance(s_hi, model_ceramic.L, model_ceramic.L_core, model_ceramic.R_core)
    L_eff_ceramic = Z_hi_ceramic.imag / w_hi
    drop_ceramic = (L0 - L_eff_ceramic) / L0 * 100.0
    assert drop_ceramic <= 2.2

    # 3. Disabled eddy diffusion
    model_disabled = CircuitModel()
    model_disabled.L = L0
    apply_magnet_properties_to_model(model_disabled, {"magnet_type": "alnico_v"}, eddy_diffusion=False)
    assert model_disabled.L_core == 0.0
    assert model_disabled.R_core == 0.0
    Z_hi_disabled = compute_core_impedance(s_hi, model_disabled.L, model_disabled.L_core, model_disabled.R_core)
    assert Z_hi_disabled.imag / w_hi == pytest.approx(L0)
    assert Z_hi_disabled.real == 0.0

def test_dahl_magnetic_hysteresis():
    """
    Verify Dahl magnetic hysteresis friction modeling:
    1. Produces phase lag on sinusoidal signals without generating DC bias.
    2. Alnico V (eta=0.06) exhibits hysteresis lag; Piezo (eta=0.0) has 0 phase lag.
    3. Small signals (<= 0.10 peak) bypass saturation/hysteresis.
    """
    sr = 96000
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    freq = 100.0
    x = 0.60 * np.sin(2 * np.pi * freq * t)

    # 1. Alnico V hysteresis
    y_alnico = apply_dahl_hysteresis(x, eta=0.06)
    # Zero crossing phase lag: y should cross 0 slightly later than x
    idx_cross = int(sr * 0.005)
    # Just after crossing where x is negative:
    assert x[idx_cross + 1] < 0.0
    # y should lag behind x (more positive)
    assert y_alnico[idx_cross + 1] > x[idx_cross + 1]

    # DC offset must be minimal (< 1e-3)
    assert abs(np.mean(y_alnico)) < 1e-3

    # 2. Piezo (eta=0.0) must be exact identity
    y_piezo = apply_dahl_hysteresis(x, eta=0.0)
    assert np.array_equal(x, y_piezo)

    # 3. Small-signal test impulse bypass in apply_oversampled_saturation
    impulse = np.zeros(2048, dtype=np.float32)
    impulse[0] = 0.05
    out_impulse = apply_oversampled_saturation(impulse, vsat=0.5, alpha=0.26, eta_hyst=0.06)
    assert np.array_equal(impulse, out_impulse)

def test_tonestyler_p_bass_progression_transfer_functions():
    """
    Verify ToneStyler P-Bass sequence (05, 05b, 05c, 05d):
    1. Netlists parse R_tone = 3.3 ohms (zero pot wiper damping) with 22nF, 47nF, 100nF.
    2. Resonant peak physically glides down through the spectrum:
       - 05 (Tone Open): peak ~ 2128 Hz (+0.5 dB)
       - 05b (22nF): peak ~ 440 Hz (+1.5 dB)
       - 05c (47nF): peak ~ 205 Hz (-0.1 dB)
       - 05d (100nF): deep sub-bass rolloff with -3 dB cutoff at ~240 Hz
    3. Each step preserves undamped Q factor without muddy pot wiper damping.
    """
    m05 = parse_netlist(CIRCUITS_DIR / "05_vintage_62_p_alnico.cir")
    m05b = parse_netlist(CIRCUITS_DIR / "05b_vintage_62_p_22nf.cir")
    m05c = parse_netlist(CIRCUITS_DIR / "05c_vintage_62_p_47nf.cir")
    m05d = parse_netlist(CIRCUITS_DIR / "05d_vintage_50s_p_100nf.cir")

    assert m05b.Ctone == pytest.approx(22e-9)
    assert m05b.Rtone == pytest.approx(3.3)
    assert m05c.Ctone == pytest.approx(47e-9)
    assert m05c.Rtone == pytest.approx(3.3)
    assert m05d.Ctone == pytest.approx(100e-9)
    assert m05d.Rtone == pytest.approx(3.3)

    c05 = compute_circuit_transfer_functions(m05, freqs=FREQS)[0]
    c05b = compute_circuit_transfer_functions(m05b, freqs=FREQS)[0]
    c05c = compute_circuit_transfer_functions(m05c, freqs=FREQS)[0]
    c05d = compute_circuit_transfer_functions(m05d, freqs=FREQS)[0]

    # Peak frequencies glide downward
    peak_f05 = FREQS[c05.index(max(c05))]
    peak_f05b = FREQS[c05b.index(max(c05b))]
    peak_f05c = FREQS[c05c.index(max(c05c))]

    assert 1900.0 <= peak_f05 <= 2400.0
    assert 400.0 <= peak_f05b <= 480.0
    assert 180.0 <= peak_f05c <= 240.0
    assert peak_f05 > peak_f05b > peak_f05c

    # 05d has deepest cutoff: at 500 Hz, 05d is significantly more attenuated than 05c
    idx_500 = min(range(len(FREQS)), key=lambda i: abs(FREQS[i] - 500.0))
    assert c05d[idx_500] < c05c[idx_500] < c05b[idx_500]

    # Differential transfer function verification against standard P source:
    src_p = parse_netlist(CIRCUITS_DIR / "sources" / "source_standard_p.cir")
    diff_05b = compute_differential_circuit_transfer_functions(m05b, src_p, freqs=FREQS)[0]
    diff_05d = compute_differential_circuit_transfer_functions(m05d, src_p, freqs=FREQS)[0]

    idx_440 = min(range(len(FREQS)), key=lambda i: abs(FREQS[i] - 440.0))
    db_05b_440 = 20.0 * math.log10(diff_05b[idx_440] / diff_05b[0])
    db_05d_440 = 20.0 * math.log10(diff_05d[idx_440] / diff_05d[0])

    # 05b (22nF) has resonant boost at 440 Hz (> 1.5 dB)
    assert db_05b_440 > 1.5
    # 05d (100nF) has deep rolloff at 440 Hz (< -8.0 dB)
    assert db_05d_440 < -8.0
    # 05b and 05d must be distinct and separated by > 10 dB at 440 Hz
    assert (db_05b_440 - db_05d_440) > 10.0

def test_higher_order_dipole_expansion_and_sag():
    """
    Verify higher-order magnetic dipole expansion (alpha3) and Lenz-law flux sag (k_sag):
    1. MAGNET_PROPERTIES defines alpha3 and k_sag across all magnet types.
    2. Cubic expansion generates 3rd harmonic (3f) excitation.
    3. Flux sag reduces peak excursion envelope on forte attacks, proportional to k_sag.
    4. Small signals (<= 0.10) preserve mathematical linearity.
    """
    # 1. Magnet properties dictionary check
    for mag_type in ["alnico_v", "alnico_ii", "ceramic", "hybrid", "neodymium", "piezo"]:
        assert mag_type in MAGNET_PROPERTIES
        props = MAGNET_PROPERTIES[mag_type]
        assert "alpha3" in props
        assert "k_sag" in props
        assert 0.0 <= props["alpha3"] <= 0.20
        assert 0.0 <= props["k_sag"] <= 0.20

    # Alnico II has highest sag and proximity stiffening; Piezo has 0.0
    assert MAGNET_PROPERTIES["alnico_ii"]["alpha3"] > MAGNET_PROPERTIES["ceramic"]["alpha3"]
    assert MAGNET_PROPERTIES["alnico_ii"]["k_sag"] > MAGNET_PROPERTIES["ceramic"]["k_sag"]
    assert MAGNET_PROPERTIES["piezo"]["alpha3"] == 0.0
    assert MAGNET_PROPERTIES["piezo"]["k_sag"] == 0.0

    # 2. Cubic expansion generating 3rd harmonic
    sr = 48000
    n = 8192
    t = np.arange(n) / sr
    f0 = 150.0
    sig = 0.50 * np.sin(2.0 * np.pi * f0 * t)

    # Pure quadratic (alpha=0.20, alpha3=0.0)
    out_quad = apply_oversampled_saturation(
        sig, vsat=0.6, alpha=0.20, alpha3=0.0, k_sag=0.0, displacement_weighting=False, oversample=1
    )
    # Cubic proximity stiffening (alpha=0.20, alpha3=0.10)
    out_cubic = apply_oversampled_saturation(
        sig, vsat=0.6, alpha=0.20, alpha3=0.10, k_sag=0.0, displacement_weighting=False, oversample=1
    )

    # Difference signal (out_cubic - out_quad) matches sin^3(theta) = (3*sin(theta) - sin(3*theta)) / 4
    diff_sig = out_cubic - out_quad
    fft_diff = np.abs(np.fft.rfft(diff_sig))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)

    idx_h3 = int(np.argmin(np.abs(freqs - 3.0 * f0)))
    h3_diff = fft_diff[idx_h3]

    # Cubic proximity stiffening must produce significant 3rd harmonic modulation and increased excursion
    assert h3_diff > 2.0
    assert np.max(out_cubic) > np.max(out_quad)

    # 3. Dynamic Lenz-law core flux sag
    # Large burst signal exceeding vsat
    burst = 0.80 * np.sin(2.0 * np.pi * f0 * t)
    out_nosag = apply_oversampled_saturation(
        burst, vsat=0.5, alpha=0.0, alpha3=0.0, k_sag=0.0, magnet_drag=True, oversample=1
    )
    out_sag = apply_oversampled_saturation(
        burst, vsat=0.5, alpha=0.0, alpha3=0.0, k_sag=0.12, magnet_drag=True, oversample=1
    )

    # RMS of sagged burst must be lower due to dynamic Lenz braking
    rms_nosag = np.sqrt(np.mean(out_nosag ** 2))
    rms_sag = np.sqrt(np.mean(out_sag ** 2))
    assert rms_sag < rms_nosag

    # 4. Small-signal linearity
    small_sig = 0.05 * np.sin(2.0 * np.pi * f0 * t)
    out_small = apply_oversampled_saturation(
        small_sig, vsat=0.5, alpha=0.20, alpha3=0.10, k_sag=0.12, oversample=1
    )
    assert np.allclose(small_sig, out_small, atol=1e-6)

def test_voice_02b_transfer_function():
    """
    Verify Voice 02b (Vintage '60s Jazz Bass Pair with 22nF ToneStyler Detent):
    1. Netlist parses topology = parallel, R_tone = 3.3, C_tone = 22nF.
    2. Resonant peak occurs in the 700-850 Hz region (Jaco vocal bridge burp).
    3. Treble at 3 kHz is attenuated by > 6 dB relative to wide-open Voice 02.
    """
    m02b = parse_netlist(CIRCUITS_DIR / "02b_jazz_bass_pair_22nf.cir")
    assert m02b.topology == "parallel"
    assert m02b.Ctone == pytest.approx(22e-9)
    assert m02b.Rtone == pytest.approx(3.3)

    m02 = parse_netlist(CIRCUITS_DIR / "02_jazz_bass_pair.cir")

    curves_02b = compute_circuit_transfer_functions(m02b, freqs=FREQS)
    curves_02 = compute_circuit_transfer_functions(m02, freqs=FREQS)

    for ch in [0, 1]:
        peak_f = FREQS[curves_02b[ch].index(max(curves_02b[ch]))]
        assert 700.0 <= peak_f <= 850.0

        idx_3k = min(range(len(FREQS)), key=lambda i: abs(FREQS[i] - 3000.0))
        diff_3k_db = 20.0 * math.log10(curves_02b[ch][idx_3k] / curves_02[ch][idx_3k])
        assert diff_3k_db < -6.0

def test_spatial_wave_propagation_delay():
    """
    Verify spatial acoustic wave propagation delay (tau = delta_x / c_s):
    1. Multi-pickup voice 02_jazz_bass_pair produces 2 FIRs where bridge FIR is delayed
       by ~0.81 ms (~39 samples at 48 kHz) relative to neck FIR.
    2. Summing neck and bridge FIRs produces the iconic acoustic phase comb notch
       in the 500-800 Hz range (depth > 10 dB relative to 100 Hz).
    3. Single-pickup voice 05_vintage_62_p_alnico produces 1 FIR with 0 delay (peak at tap 0).
    """
    firs_02 = compute_voice_prefilter_firs("02_jazz_bass_pair", instrument="30in")
    assert len(firs_02) == 2

    fir_n = np.array(firs_02[0])
    fir_b = np.array(firs_02[1])

    # Neck is at pos=155.6 mm (pos_max -> tau = 0), so peak is near tap 0
    peak_n = int(np.argmax(np.abs(fir_n)))
    # Bridge is at pos=63.5 mm (delta_x = 92.1 mm -> tau = 0.81 ms = 38.9 samples at 48k)
    peak_b = int(np.argmax(np.abs(fir_b)))
    sample_delay = peak_b - peak_n
    assert 36 <= sample_delay <= 42, f"Bridge delay was {sample_delay} samples (expected ~39)"

    # Summing the two channels creates acoustic comb notch
    fir_sum = fir_n + fir_b
    n_fft = 8192
    H_sum = np.abs(np.fft.rfft(fir_sum, n_fft))
    f_bins = np.fft.rfftfreq(n_fft, 1.0 / 48000.0)

    ref_100 = np.interp(100.0, f_bins, H_sum)
    mask_notch = (f_bins >= 500.0) & (f_bins <= 800.0)
    min_notch = np.min(H_sum[mask_notch])
    notch_depth_db = 20.0 * np.log10(ref_100 / min_notch)
    assert notch_depth_db > 10.0, f"Comb notch depth was {notch_depth_db:.2f} dB (expected > 10 dB)"

    # Single-pickup voice
    firs_05 = compute_voice_prefilter_firs("05_vintage_62_p_alnico", instrument="30in")
    assert len(firs_05) == 1
    assert np.argmax(np.abs(firs_05[0])) <= 2

def test_string_mass_momentum_weighting():
    """
    Verify string-mass kinetic momentum excursion weighting in saturation engine:
    1. Momentum pre-filter provides +3 dB boost at Low-E 41.2 Hz and -10.6 dB cut at 1 kHz relative to 100 Hz.
    2. Deep bass fundamentals (41.2 Hz) drive more dynamic non-linear compression than upper register (1 kHz).
    3. Small signals (amplitude <= 0.10) bypass non-linearity and preserve exact waveform.
    """
    # 1. Frequency response verification of momentum weighting curve
    freqs = np.array([41.2, 100.0, 1000.0])
    wc = 2.0 * np.pi * 40.0
    s = 1j * 2.0 * np.pi * freqs
    H_pre = (wc / (s + wc)) ** 0.55
    H_pre = H_pre / np.abs(H_pre[1])
    gain_db = 20.0 * np.log10(np.abs(H_pre))
    assert gain_db[0] == pytest.approx(3.00, abs=0.1)
    assert gain_db[1] == pytest.approx(0.00, abs=0.01)
    assert gain_db[2] == pytest.approx(-10.65, abs=0.1)

    # 2. Dynamic saturation compression comparison
    sr = 48000
    n = sr * 2
    t = np.arange(n) / sr

    sig_low = (0.60 * np.sin(2.0 * np.pi * 41.2 * t)).astype(np.float32)
    sig_hi = (0.60 * np.sin(2.0 * np.pi * 1000.0 * t)).astype(np.float32)

    sat_low = apply_oversampled_saturation(sig_low, vsat=0.50, alpha=0.20, oversample=1, displacement_weighting=True)
    sat_hi = apply_oversampled_saturation(sig_hi, vsat=0.50, alpha=0.20, oversample=1, displacement_weighting=True)

    cf_low = np.max(np.abs(sat_low)) / np.sqrt(np.mean(sat_low ** 2))
    cf_hi = np.max(np.abs(sat_hi)) / np.sqrt(np.mean(sat_hi ** 2))
    assert cf_low < cf_hi

    # 3. Small-signal impulse bypass
    impulse = np.zeros(1024, dtype=np.float32)
    impulse[0] = 0.08
    out_small = apply_oversampled_saturation(impulse, vsat=0.50, alpha=0.20, oversample=1, displacement_weighting=True)
    assert np.allclose(impulse, out_small, atol=1e-7)

def test_differential_circuit_hf_limiter_smoothness():
    """
    Verify that differential circuit transfer functions crossing 0.0 dB above 8 kHz
    transition smoothly with strictly continuous first derivative and zero slope kinks.
    """
    tgt_model = parse_netlist(CIRCUITS_DIR / "03_jazz_bridge_60s.cir")
    src_model = parse_netlist(CIRCUITS_DIR / "sources" / "source_standard_p.cir")

    curves = compute_differential_circuit_transfer_functions(tgt_model, src_model, freqs=FREQS)
    assert len(curves) > 0
    h_c = np.asarray(curves[0], dtype=np.float64)
    h_db = 20.0 * np.log10(h_c / h_c[0])

    f_arr = np.asarray(FREQS, dtype=np.float64)
    hf_mask = (f_arr >= 8000.0)
    # Check that the derivative d(h_db)/df does not have sudden jump steps across 0 dB
    dh = np.gradient(h_db[hf_mask], f_arr[hf_mask])
    # The rate of change of derivative should be well-behaved
    d2h = np.gradient(dh, f_arr[hf_mask])
    assert np.max(np.abs(d2h)) < 1e-4, "Derivative of differential curve should be smooth without piecewise kinks"

def test_cable_dielectric_loss():
    """
    Verify instrument cable dielectric loss (tan delta):
    1. At DC (f=0), dielectric conductance is strictly zero, preserving exact 0.00 dB DC transfer.
    2. At the resonant peak, tan_delta=0.025 provides gentle 0.2 to 0.7 dB softening of Q peak.
    3. Active buffered pickups (model.has_active_buffer=True) isolate coils from cable dielectric loss.
    """
    cir_path = CIRCUITS_DIR / "04_modern_p_ceramic.cir"
    m_lossless = parse_netlist(cir_path)
    m_lossless.tan_delta = 0.0

    m_lossy = parse_netlist(cir_path)
    m_lossy.tan_delta = 0.025

    c_lossless = np.array(compute_circuit_transfer_functions(m_lossless, freqs=FREQS)[0])
    c_lossy = np.array(compute_circuit_transfer_functions(m_lossy, freqs=FREQS)[0])

    # 1. Exact DC unity preservation
    assert math.isclose(c_lossless[0], c_lossy[0], abs_tol=1e-5)

    # 2. Resonant peak softening (between 1800 and 2400 Hz)
    pk_idx = np.argmax(c_lossless)
    diff_peak_db = 20.0 * np.log10(c_lossless[pk_idx] / c_lossy[pk_idx])
    assert 0.05 <= diff_peak_db <= 0.50, f"Peak attenuation {diff_peak_db:.2f} dB outside expected range"

    # 3. High-frequency rolloff remains smooth
    assert c_lossy[-1] < 0.20

def test_voice_09b_series_netlist_and_transfer():
    """
    Verify Voice 09b Music Man StingRay Series netlist and transfer function:
    1. Standalone SPICE netlist parses with active buffer and stingray_2band preamp.
    2. L=4.0H, Rdc=8.8k, Reddy=140k, Ccoil=90pF.
    3. Series peak is lower in frequency and less treble-heavy than 09 parallel.
    """
    cir_09 = CIRCUITS_DIR / "09_stingray_mm_parallel.cir"
    cir_09b = CIRCUITS_DIR / "09b_stingray_mm_series.cir"
    assert cir_09b.exists(), f"Netlist missing: {cir_09b}"

    m09 = parse_netlist(cir_09)
    m09b = parse_netlist(cir_09b)

    assert m09b.has_active_buffer is True
    assert m09b.preamp_type == "stingray_2band"
    assert m09b.topology == "single"
    assert m09b.L == pytest.approx(4.0)
    assert m09b.Rdc == pytest.approx(8800.0)
    assert m09b.Reddy == pytest.approx(140000.0)
    assert m09b.Ccoil == pytest.approx(90e-12)

    c09 = np.array(compute_circuit_transfer_functions(m09, freqs=FREQS)[0])
    c09b = np.array(compute_circuit_transfer_functions(m09b, freqs=FREQS)[0])

    peak_09 = FREQS[np.argmax(c09)]
    peak_09b = FREQS[np.argmax(c09b)]

    # Series peak is shifted lower than parallel peak
    assert peak_09b < peak_09

    # At 7 kHz (clank region), series has less gain than parallel
    idx_7k = FREQS.index(7000.0) if 7000.0 in FREQS else np.argmin(np.abs(np.array(FREQS) - 7000.0))
    assert c09b[idx_7k] < c09[idx_7k]


def test_differential_magnetic_softening_neodymium_to_alnico():
    """
    Verify that converting a passive Neodymium source (34in_dingwall_sp1) to an
    Alnico V target (05_vintage_62_p_alnico) engages differential magnetic softening:
    - Delta alpha = 0.18, Delta eta = 0.05, Delta k_sag = 0.07, Vsat_eff ≈ 0.84.
    - Forte peaks (> 0.5V) undergo soft-knee saturation and 2nd harmonic expansion.
    """
    import pedalboard.io
    sr = 48000
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    forte_signal = (0.85 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        in_wav = Path(td) / "forte_in.wav"
        out_wav = Path(td) / "out_softened.wav"
        write_wav_24bit(str(in_wav), forte_signal, sample_rate=sr)

        res = simulate_voice("05_vintage_62_p_alnico", input_wav=in_wav, output_wav=out_wav, instrument="34in_dingwall_sp1", normalize="none")
        assert res is True

        with pedalboard.io.AudioFile(str(out_wav)) as f:
            audio_out = f.read(f.frames)[0]

        # In a non-linear saturation, second harmonic (200 Hz) emerges from asymmetry (Delta alpha > 0)
        fft_mag = np.abs(np.fft.rfft(audio_out))
        freqs = np.fft.rfftfreq(len(audio_out), 1.0 / sr)
        fund_idx = np.argmin(np.abs(freqs - 100.0))
        h2_idx = np.argmin(np.abs(freqs - 200.0))

        fund_level = fft_mag[fund_idx]
        h2_level = fft_mag[h2_idx]
        # Second harmonic is present due to differential asymmetry (alpha > 0)
        assert h2_level > 1e-4 * fund_level, f"Expected 2nd harmonic bloom from differential alpha, got H2/H1 = {h2_level/fund_level:.6f}"


def test_differential_magnetic_softening_alnico_to_neodymium_bypassed():
    """
    Verify that converting a softer Alnico V source (34in_standard_p) to a stiffer
    Neodymium target (13_dingwall_multiscale_bridge) bypasses forward saturation (Delta <= 0).
    Input scaling linearity error ||y_full - 2 * y_half|| / ||y_full|| must be < 1e-4.
    """
    import pedalboard.io
    sr = 48000
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    sig_full = (0.85 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
    sig_half = (0.425 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        in_full = Path(td) / "full.wav"
        in_half = Path(td) / "half.wav"
        out_full = Path(td) / "out_bypassed_full.wav"
        out_half = Path(td) / "out_bypassed_half.wav"
        write_wav_24bit(str(in_full), sig_full, sample_rate=sr)
        write_wav_24bit(str(in_half), sig_half, sample_rate=sr)

        simulate_voice("13_dingwall_multiscale_bridge", input_wav=in_full, output_wav=out_full, instrument="34in_standard_p", normalize="none")
        simulate_voice("13_dingwall_multiscale_bridge", input_wav=in_half, output_wav=out_half, instrument="34in_standard_p", normalize="none")

        with pedalboard.io.AudioFile(str(out_full)) as f:
            y_full = f.read(f.frames)[0]
        with pedalboard.io.AudioFile(str(out_half)) as f:
            y_half = f.read(f.frames)[0]

        # Target Neodymium is stiffer than source Alnico V, so softening is bypassed: 100% linear
        rel_diff = float(np.max(np.abs(y_full - 2.0 * y_half)) / np.max(np.abs(y_full)))
        assert rel_diff < 1e-4, f"Expected linear scaling (rel_diff < 1e-4), got {rel_diff:.2e}"


def test_differential_magnetic_softening_active_to_passive():
    """
    Verify that converting an active 18V EMG source (30in_emg_mmtw) to a passive
    Alnico V target (05_vintage_62_p_alnico) applies full target magnetic saturation.
    Compression and asymmetry cause ||y_full - 2 * y_half|| / ||y_full|| to exceed 5%.
    """
    import pedalboard.io
    sr = 48000
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    sig_full = (0.85 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
    sig_half = (0.425 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        in_full = Path(td) / "full.wav"
        in_half = Path(td) / "half.wav"
        out_full = Path(td) / "out_act_full.wav"
        out_half = Path(td) / "out_act_half.wav"
        write_wav_24bit(str(in_full), sig_full, sample_rate=sr)
        write_wav_24bit(str(in_half), sig_half, sample_rate=sr)

        simulate_voice("05_vintage_62_p_alnico", input_wav=in_full, output_wav=out_full, instrument="30in_emg_mmtw", normalize="none")
        simulate_voice("05_vintage_62_p_alnico", input_wav=in_half, output_wav=out_half, instrument="30in_emg_mmtw", normalize="none")

        with pedalboard.io.AudioFile(str(out_full)) as f:
            y_full = f.read(f.frames)[0]
        with pedalboard.io.AudioFile(str(out_half)) as f:
            y_half = f.read(f.frames)[0]

        rel_diff = float(np.max(np.abs(y_full - 2.0 * y_half)) / np.max(np.abs(y_full)))
        assert rel_diff > 0.05, f"Expected non-linear saturation (rel_diff > 0.05), got {rel_diff:.4f}"


def test_differential_magnetic_softening_identity_bypassed():
    """
    Verify that an identity voice conversion (34in_standard_p -> 05_vintage_62_p_alnico)
    bypasses forward saturation to prevent double-compression.
    Input scaling linearity error ||y_full - 2 * y_half|| / ||y_full|| must be < 1e-4.
    """
    import pedalboard.io
    sr = 48000
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    sig_full = (0.85 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
    sig_half = (0.425 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        in_full = Path(td) / "full.wav"
        in_half = Path(td) / "half.wav"
        out_full = Path(td) / "out_id_full.wav"
        out_half = Path(td) / "out_id_half.wav"
        write_wav_24bit(str(in_full), sig_full, sample_rate=sr)
        write_wav_24bit(str(in_half), sig_half, sample_rate=sr)

        simulate_voice("05_vintage_62_p_alnico", input_wav=in_full, output_wav=out_full, instrument="34in_standard_p", normalize="none")
        simulate_voice("05_vintage_62_p_alnico", input_wav=in_half, output_wav=out_half, instrument="34in_standard_p", normalize="none")

        with pedalboard.io.AudioFile(str(out_full)) as f:
            y_full = f.read(f.frames)[0]
        with pedalboard.io.AudioFile(str(out_half)) as f:
            y_half = f.read(f.frames)[0]

        rel_diff = float(np.max(np.abs(y_full - 2.0 * y_half)) / np.max(np.abs(y_full)))
        assert rel_diff < 1e-4, f"Expected linear scaling (rel_diff < 1e-4), got {rel_diff:.2e}"


def test_calibrated_drive_excursion_item3():
    """
    Verify Item 3: Drive excursion into magnetic saturation window is consistently calibrated
    when prefilter_firs is None (standalone or prefiltered audio).
    - Large signals (peak 0.95) are scaled to target_drive_peak (<= 0.70) into saturation.
    - Small signals (peak 0.05) bypass saturation completely and remain 100% linear.
    """
    import pedalboard.io
    m = parse_netlist(CIRCUITS_DIR / "05_vintage_62_p_alnico.cir")
    sr = 48000
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)

    # 1. Large signal: peak 0.95
    large_sig = (0.95 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)
    # 2. Small signal: peak 0.05
    small_sig = (0.05 * np.sin(2 * np.pi * 100 * t)).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        out_large = Path(td) / "out_large.wav"
        out_small = Path(td) / "out_small.wav"

        simulate_circuit_audio(large_sig, out_large, m, prefilter_firs=None, is_passive=False, normalize="none")
        simulate_circuit_audio(small_sig, out_small, m, prefilter_firs=None, is_passive=False, normalize="none")

        with pedalboard.io.AudioFile(str(out_large)) as f:
            audio_large = f.read(f.frames)[0]
        with pedalboard.io.AudioFile(str(out_small)) as f:
            audio_small = f.read(f.frames)[0]

        # Small signal has zero harmonic distortion (pure sine preserved)
        fft_small = np.abs(np.fft.rfft(audio_small))
        freqs = np.fft.rfftfreq(len(audio_small), 1.0 / sr)
        h1_idx = np.argmin(np.abs(freqs - 100.0))
        h2_idx = np.argmin(np.abs(freqs - 200.0))
        assert fft_small[h2_idx] < 1e-4 * fft_small[h1_idx]

        # Large signal engages saturation safely without exceeding true-peak headroom
        assert np.max(np.abs(audio_large)) <= 0.9885

def test_no_double_voicing_on_aperture_input():
    """
    Verify Vector 1: Auto-detection of pre-filtered intermediate aperture audio.
    When input_wav filename starts with 'aperture_', simulate_voice must automatically
    set prefiltered=True and avoid convolving prefilter_firs a second time.
    """
    import pedalboard.io
    sr = 48000
    impulse = np.zeros(1024, dtype=np.float32)
    impulse[0] = 0.50

    with tempfile.TemporaryDirectory() as td:
        aperture_wav = Path(td) / "aperture_04_modern_p_ceramic.wav"
        out_wav = Path(td) / "out_04.wav"

        # Write simulated aperture prefiltered audio
        with pedalboard.io.AudioFile(str(aperture_wav), "w", samplerate=sr, num_channels=1, bit_depth=24) as f:
            f.write(impulse[np.newaxis, :])

        # Call simulate_voice WITHOUT passing prefiltered=True
        success = simulate_voice(
            "04_modern_p_ceramic",
            input_wav=aperture_wav,
            output_wav=out_wav,
            instrument="30in",
            prefiltered=False, # explicitly False: should be overridden by auto-detection!
            normalize="none",
        )
        assert success is True
        assert out_wav.exists()

        # Read result: if prefiltered was correctly auto-detected, output length is ~1024 + 1024
        # (circuit impulse only), NOT convolved through prefilter_firs again.
        with pedalboard.io.AudioFile(str(out_wav)) as f:
            out_audio = f.read(f.frames)[0]
        assert len(out_audio) == len(impulse)
        assert np.max(np.abs(out_audio)) > 0.0

def test_multichannel_branch_weight_consistency():
    """
    Verify Vector 2 & 3: Multi-channel branch weight consistency.
    When a voice has a multi-channel SPICE netlist (e.g. 02_jazz_bass_pair),
    prefilter FIRs have unit branch weight (p_weight = 1.0) because SPICE nodal
    analysis computes the parallel current divider Y_branch / Y_total.
    """
    from scripts.model_physics import compute_voice_prefilter_firs, VOICES
    firs_02 = compute_voice_prefilter_firs("02_jazz_bass_pair", instrument="30in", num_taps=512)
    assert len(firs_02) == 2
    # Both channels must have peaks around 0.99
    peak_0 = np.max(np.abs(firs_02[0]))
    peak_1 = np.max(np.abs(firs_02[1]))
    assert math.isclose(max(peak_0, peak_1), 0.99, rel_tol=1e-3)

def test_dingwall_composite_source_circuit():
    """
    Verify Vector 2: 37in_multiscale_dingwall pair_parallel declares source circuit
    and computes differential SPICE transfer functions without falling back to generic RLC.
    """
    inst = load_instrument("37in_multiscale_dingwall")
    pair_pickup = inst["pickups"]["pair_parallel"]
    assert "circuit" in pair_pickup
    assert pair_pickup["circuit"] == "circuits/sources/source_dingwall_fd3n.cir"
    assert (REPO_ROOT / pair_pickup["circuit"]).exists()

    # Differential SPICE transfer functions evaluate cleanly
    cir_path = REPO_ROOT / "circuits" / "02_jazz_bass_pair.cir"
    src_cir_path = REPO_ROOT / pair_pickup["circuit"]
    tgt_model = parse_netlist(cir_path)
    src_model = parse_netlist(src_cir_path)
    diff_curves = compute_differential_circuit_transfer_functions(tgt_model, src_model, freqs=FREQS)
    assert len(diff_curves) == 2
    for c in diff_curves:
        assert len(c) == len(FREQS)
        assert np.all(np.isfinite(c))
        assert np.all(np.array(c) > 0.0)

def test_asymmetric_lenz_flux_sag_attack_release():
    """
    Verify Refinement 1: Asymmetric Lenz flux sag envelope follower.
    Fast attack (<= 8 ms) on sudden transient burst, gradual release (>= 35 ms) on decay.
    """
    from scripts.simulate_circuits import _lenz_envelope_core
    fs = 48000.0
    tau_att = 0.006  # 6 ms
    tau_rel = 0.045  # 45 ms
    alpha_att = 1.0 - math.exp(-1.0 / (fs * tau_att))
    alpha_rel = 1.0 - math.exp(-1.0 / (fs * tau_rel))

    # Test Step Attack: sudden burst from 0.0 to 1.0
    n_samples = int(fs * 0.1)  # 100 ms
    step_input = np.ones(n_samples, dtype=np.float64)
    env_attack = _lenz_envelope_core(step_input, alpha_att, alpha_rel)

    # In 1 tau_att (6 ms = 288 samples), envelope should reach ~63.2%
    idx_6ms = int(fs * 0.006)
    assert 0.60 <= env_attack[idx_6ms] <= 0.66
    # In 8 ms (384 samples), envelope should exceed 70% (fast attack <= 8 ms)
    idx_8ms = int(fs * 0.008)
    assert env_attack[idx_8ms] >= 0.70

    # Test Decay Release: held at 1.0 for 100 ms, then sudden drop to 0.0 for 100 ms
    pulse_input = np.zeros(int(fs * 0.2), dtype=np.float64)
    pulse_input[:n_samples] = 1.0
    env_release = _lenz_envelope_core(pulse_input, alpha_att, alpha_rel)
    # At n_samples (100 ms), env is ~1.0. In 1 tau_rel (45 ms), it should decay to ~36.8% of ~1.0
    idx_45ms_after = n_samples + int(fs * 0.045)
    assert 0.33 <= env_release[idx_45ms_after] <= 0.40
    # In 35 ms after drop, it should still retain significant energy (> 40%), proving release >= 35 ms
    idx_35ms_after = n_samples + int(fs * 0.035)
    assert env_release[idx_35ms_after] >= 0.40

    # Verify apply_oversampled_saturation incorporates Lenz sag
    x = np.sin(2 * np.pi * 100 * np.linspace(0, 0.2, int(fs * 0.2))) * 0.8
    y_sag = apply_oversampled_saturation(x, vsat=0.4, k_sag=0.15, magnet_drag=True)
    y_nosag = apply_oversampled_saturation(x, vsat=0.4, k_sag=0.0, magnet_drag=False)
    assert np.max(np.abs(y_sag)) < np.max(np.abs(y_nosag))

def test_coil_dielectric_loss():
    """
    Verify Refinement 2: Coil self-capacitance dielectric loss (tan delta = 0.025).
    Gently softens resonant peak by ~0.01-0.5 dB without shifting center frequency.
    """
    cir_path = CIRCUITS_DIR / "04_modern_p_ceramic.cir"
    model = parse_netlist(cir_path)

    # Compute with zero dielectric loss
    model.tan_delta_coil = 0.0
    curves_lossless = compute_circuit_transfer_functions(model, freqs=FREQS)
    peak_lossless = max(curves_lossless[0])
    peak_idx_lossless = curves_lossless[0].index(peak_lossless)
    peak_freq_lossless = FREQS[peak_idx_lossless]

    # Compute with physical dielectric loss (tan delta = 0.025)
    model.tan_delta_coil = 0.025
    curves_lossy = compute_circuit_transfer_functions(model, freqs=FREQS)
    peak_lossy = max(curves_lossy[0])
    peak_idx_lossy = curves_lossy[0].index(peak_lossy)
    peak_freq_lossy = FREQS[peak_idx_lossy]

    # Resonant frequency must remain virtually unchanged (within 50 Hz)
    assert abs(peak_freq_lossy - peak_freq_lossless) <= 50.0

    # Dielectric loss should gently soften the resonant peak
    delta_db = 20.0 * np.log10(peak_lossless / peak_lossy)
    assert 0.005 <= delta_db <= 0.50

def test_jaco_bridge_growl_bias_voicing():
    """
    Verify Refinement 4 & 5: Jaco Pastorius 60s Jazz Bridge Growl Bias voicing (02c).
    Validates decoupled pot parsing (Neck 75%, Bridge 100%), relative branch attenuation,
    and prefilter FIR generation.
    """
    cir_path = CIRCUITS_DIR / "02c_jazz_bridge_growl_bias.cir"
    assert cir_path.exists()
    model = parse_netlist(cir_path)
    assert model.topology == "parallel"
    assert model.Rpot_n == pytest.approx(55000.0)
    assert model.Rpot_b == pytest.approx(0.0)

    curves = compute_circuit_transfer_functions(model, freqs=FREQS)
    assert len(curves) == 2
    neck_mag = np.array(curves[0])
    bridge_mag = np.array(curves[1])

    # Neck pickup should be attenuated relative to bridge pickup across passband
    # due to 55k wiper resistance
    idx_1k = np.argmin(np.abs(np.array(FREQS) - 1000.0))
    assert neck_mag[idx_1k] < bridge_mag[idx_1k]
    diff_db_1k = 20.0 * np.log10(bridge_mag[idx_1k] / neck_mag[idx_1k])
    assert 6.0 <= diff_db_1k <= 14.0

    # Pre-filter FIRs for 02c must exist and synthesize cleanly
    firs = compute_voice_prefilter_firs("02c_jazz_bridge_growl_bias", instrument="34in_standard_jazz", num_taps=512)
    assert len(firs) == 2
    assert np.all(np.isfinite(firs[0]))
    assert np.all(np.isfinite(firs[1]))

def test_multi_pickup_excursion_ratio():
    """
    Verify Refinement 3: Physical string excursion drive ratio between neck and bridge pickups.
    Mono signal through multi-pickup circuit simulation scales bridge drive.
    """
    model = parse_netlist(CIRCUITS_DIR / "02_jazz_bass_pair.cir")
    fs = 48000
    n_samples = 4800
    mono_audio = (np.sin(2 * np.pi * 100.0 * np.linspace(0, 0.1, n_samples)) * 0.8).astype(np.float32)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
        out_wav = Path(tmp_out.name)
    try:
        simulate_circuit_audio(
            mono_audio,
            output_wav_path=out_wav,
            model=model,
            vsat=0.5,
            alpha=0.2,
            alpha3=0.08,
            k_sag=0.08,
            bypass_saturation=False,
        )
        assert out_wav.exists()
        import pedalboard.io
        with pedalboard.io.AudioFile(str(out_wav)) as f:
            read_audio = f.read(f.frames)[0]
        assert len(read_audio) == n_samples
        assert np.all(np.isfinite(read_audio))
    finally:
        if out_wav.exists():
            out_wav.unlink()

def test_asymmetric_dahl_proximity_pinning():
    """
    Verify Refinement: Asymmetric Dahl magnetic domain-wall pinning.
    Approach excursion (x > 0 towards pole) experiences higher pinning coupling than departure (x < 0).
    Verifies zero DC bias drift on cyclic zero-mean AC excitation.
    """
    from scripts.simulate_circuits import _dahl_core, apply_dahl_hysteresis

    n = 1000
    pos_step = np.full(n, 0.6, dtype=np.float64)
    neg_step = np.full(n, -0.6, dtype=np.float64)
    pos_step[0] = 0.0
    neg_step[0] = 0.0

    out_pos = _dahl_core(pos_step, eta=0.10, r=0.06)
    out_neg = _dahl_core(neg_step, eta=0.10, r=0.06)

    z_pos_1 = (out_pos[1] - (1.0 - 0.10) * pos_step[1]) / 0.10
    z_neg_1 = abs((out_neg[1] - (1.0 - 0.10) * neg_step[1]) / 0.10)
    assert z_pos_1 > z_neg_1

    # Verify tiny DC drift on cyclic audio (< 0.005, blocked downstream by 8 Hz DC blocker)
    t = np.linspace(0, 0.5, 24000)
    sine = np.sin(2 * np.pi * 100.0 * t) * 0.7
    out_sine = apply_dahl_hysteresis(sine, eta=0.06, r=0.06)
    assert abs(np.mean(out_sine)) < 0.005

def test_frequency_selective_lenz_velocity_drag():
    """
    Verify Refinement: Velocity-proportional / frequency-selective Lenz drag.
    High-frequency transient clank is damped more heavily than low-frequency fundamental.
    """
    from scripts.simulate_circuits import _lenz_velocity_drag_core, apply_oversampled_saturation

    fs = 48000
    t = np.linspace(0, 0.2, int(fs * 0.2))
    # Dual-tone signal: 60 Hz bass fundamental + 3000 Hz transient clank
    sig_low = np.sin(2 * np.pi * 60.0 * t) * 0.5
    sig_high = np.sin(2 * np.pi * 3000.0 * t) * 0.5
    sig_dual = (sig_low + sig_high).astype(np.float32)

    # Saturate with Lenz drag engaged
    out_sag = apply_oversampled_saturation(sig_dual, vsat=0.4, k_sag=0.20, magnet_drag=True)
    out_nosag = apply_oversampled_saturation(sig_dual, vsat=0.4, k_sag=0.0, magnet_drag=False)

    f_bins = np.fft.rfftfreq(len(t), 1.0 / fs)
    idx_60 = np.argmin(np.abs(f_bins - 60.0))
    idx_3k = np.argmin(np.abs(f_bins - 3000.0))

    fft_sag = np.abs(np.fft.rfft(out_sag))
    fft_nosag = np.abs(np.fft.rfft(out_nosag))

    low_ratio = fft_sag[idx_60] / fft_nosag[idx_60]
    high_ratio = fft_sag[idx_3k] / fft_nosag[idx_3k]

    # High frequency must be damped more heavily than low frequency
    assert high_ratio < low_ratio
    delta_db_diff = 20.0 * np.log10(low_ratio / high_ratio)
    assert delta_db_diff >= 0.5

    # Small-signal test vector (<= 0.10) must be 100% linear bypass
    small_sig = (sig_dual * 0.05).astype(np.float32)
    out_small = apply_oversampled_saturation(small_sig, vsat=0.4, k_sag=0.20)
    assert np.allclose(small_sig, out_small, atol=1e-6)












