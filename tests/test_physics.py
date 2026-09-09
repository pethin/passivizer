import math
import os
import tempfile
import wave
from pathlib import Path
import numpy as np
from scripts.model_physics import (
    VOICES,
    SCALES,
    compute_aperture_prefilter_fir,
    compute_voice_prefilter_firs,
    write_wav_24bit,
    NUM_TAPS
)
from scripts.prep_nam_audio import prefilter_audio

def test_compute_aperture_prefilter_fir_30in():
    voice_id = "04_modern_p_ceramic"
    fir = compute_aperture_prefilter_fir(voice_id, src_scale="30in", num_taps=NUM_TAPS)

    assert len(fir) == NUM_TAPS
    max_peak = max(abs(x) for x in fir)
    assert math.isclose(max_peak, 0.99, rel_tol=1e-3)

    # Causal minimum phase: early energy should dominate late energy
    early_energy = sum(x ** 2 for x in fir[:256])
    late_energy = sum(x ** 2 for x in fir[1024:])
    assert early_energy > late_energy * 5

    # Tail should taper to near zero
    assert abs(fir[-1]) < 0.01

def test_compute_aperture_prefilter_fir_32in():
    voice_id = "09_stingray_mm_parallel"
    fir = compute_aperture_prefilter_fir(voice_id, src_scale="32in", num_taps=NUM_TAPS)

    assert len(fir) == NUM_TAPS
    max_peak = max(abs(x) for x in fir)
    assert math.isclose(max_peak, 0.99, rel_tol=1e-3)

    early_energy = sum(x ** 2 for x in fir[:256])
    late_energy = sum(x ** 2 for x in fir[1024:])
    assert early_energy > late_energy * 5

def test_compute_aperture_prefilter_multiscale():
    voice_id = "13_dingwall_multiscale_bridge"
    fir = compute_aperture_prefilter_fir(voice_id, src_scale="30in", num_taps=NUM_TAPS)

    assert len(fir) == NUM_TAPS
    max_peak = max(abs(x) for x in fir)
    assert math.isclose(max_peak, 0.99, rel_tol=1e-3)

    early_energy = sum(x ** 2 for x in fir[:256])
    late_energy = sum(x ** 2 for x in fir[1024:])
    assert early_energy > late_energy * 5

def test_prefilter_audio_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_wav = Path(tmpdir) / "test_in.wav"
        output_wav = Path(tmpdir) / "test_out.wav"

        # Generate a short 0.05s test audio impulse sequence (2400 samples at 48 kHz)
        test_samples = [0.5 if i % 100 == 0 else 0.0 for i in range(2400)]
        write_wav_24bit(str(input_wav), test_samples, sample_rate=48000)

        fir = compute_aperture_prefilter_fir("04_modern_p_ceramic", src_scale="30in", num_taps=512)
        prefilter_audio(input_wav, output_wav, fir)

        assert output_wav.exists()
        with wave.open(str(output_wav), "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3  # 24-bit PCM
            assert wf.getnchannels() == 1
            assert wf.getnframes() > 0

def test_electrical_resonance_and_deconvolution():
    import numpy as np
    from scripts.model_physics import (
        load_instrument,
        pickup_electrical_response,
        resolve_pickup_electrical_deconvolution,
    )

    freqs = np.array([0.0, 1000.0, 2500.0, 3500.0, 10000.0])

    # Test MMTW Dual: fr=2500, Q=1.35
    res_dual = pickup_electrical_response(freqs, fr=2500.0, q=1.35)
    assert math.isclose(res_dual[0], 1.0, abs_tol=1e-4)  # DC = 1.0
    assert math.isclose(res_dual[2], 1.35, abs_tol=1e-3)  # Resonance peak = Q
    assert res_dual[4] < 0.1  # High-frequency rolloff

    # Test Biquad Anti-Resonance filter
    inst_30 = load_instrument("30in_emg_mmtw")
    res_inv = resolve_pickup_electrical_deconvolution(freqs, inst_30["pickups"]["mmtw_dual"], inst_30)
    assert math.isclose(res_inv[0], 1.0, abs_tol=1e-4)  # DC = 1.0 (0 dB)
    assert res_inv[2] < 1.0  # Dips at resonance
    assert math.isclose(res_dual[2] * res_inv[2], 1.0, abs_tol=1e-3)  # Flattens peak to exactly 1.0
    assert math.isclose(res_inv[4], 1.0, rel_tol=0.05)  # Reverts to 1.0 at high frequencies (no noise explosion)
    assert all(x <= 1.0001 for x in res_inv)  # Gain never exceeds 0 dB (pure notch/attenuation)

def test_compute_voice_prefilter_firs_single_and_multi():
    # Single-pickup voice -> exactly 1 channel
    firs_single = compute_voice_prefilter_firs("04_modern_p_ceramic", src_scale="30in", num_taps=512)
    assert len(firs_single) == 1
    assert len(firs_single[0]) == 512
    max_peak_single = max(abs(x) for x in firs_single[0])
    assert math.isclose(max_peak_single, 0.99, rel_tol=1e-3)

    # Multi-pickup voice (Jazz pair) -> exactly 2 channels (Neck and Bridge)
    firs_multi = compute_voice_prefilter_firs("02_jazz_bass_pair", src_scale="30in", num_taps=512)
    assert len(firs_multi) == 2
    assert len(firs_multi[0]) == 512
    assert len(firs_multi[1]) == 512
    global_max = max(max(abs(x) for x in f) for f in firs_multi)
    assert math.isclose(global_max, 0.99, rel_tol=1e-3)

    # Multi-pickup voice (P/MM series) -> exactly 2 channels
    firs_pmm = compute_voice_prefilter_firs("11_pmm_hybrid_series", src_scale="32in", num_taps=512)
    assert len(firs_pmm) == 2

def test_multi_pickup_prefilter_audio_stereo_export():
    with tempfile.TemporaryDirectory() as tmpdir:
        input_wav = Path(tmpdir) / "test_in.wav"
        output_wav = Path(tmpdir) / "test_stereo_out.wav"

        # Generate a short 0.05s test audio impulse sequence (2400 samples at 48 kHz)
        test_samples = [0.5 if i % 100 == 0 else 0.0 for i in range(2400)]
        write_wav_24bit(str(input_wav), test_samples, sample_rate=48000)

        firs = compute_voice_prefilter_firs("02_jazz_bass_pair", src_scale="30in", num_taps=512)
        assert len(firs) == 2
        prefilter_audio(input_wav, output_wav, firs)

        assert output_wav.exists()
        with wave.open(str(output_wav), "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3  # 24-bit PCM
            assert wf.getnchannels() == 2  # Stereo (Channel 0 = Neck, Channel 1 = Bridge)
            assert wf.getnframes() > 0

def test_identity_acoustic_transfer_preserves_flat_bass():
    """Verify that modeling a source instrument against its matching voice bypasses acoustic deconvolution."""
    from scripts.model_physics import is_voice_matching_source, load_instrument, VOICES

    inst_p = load_instrument("34in_standard_p")
    assert is_voice_matching_source(inst_p, "05_vintage_62_p_alnico", VOICES["05_vintage_62_p_alnico"])

    inst_jazz = load_instrument("34in_standard_jazz")
    assert is_voice_matching_source(inst_jazz, "02_jazz_bass_pair", VOICES["02_jazz_bass_pair"])
    assert is_voice_matching_source(inst_jazz, "01_modern_jazz_active", VOICES["01_modern_jazz_active"])

    # Non-matching voice should return False
    assert not is_voice_matching_source(inst_p, "02_jazz_bass_pair", VOICES["02_jazz_bass_pair"])

def test_numpy_pickup_macro_aperture_properties():
    """Verify that macro aperture computes a smooth, comb-free sensing envelope."""
    from scripts.model_physics import numpy_pickup_macro_aperture, load_instrument

    inst = load_instrument("30in_emg_mmtw")
    src_pickup = inst["pickups"]["mmtw_dual"]
    speeds = inst["string_wave_speeds"]

    freqs = np.linspace(20.0, 10000.0, 500)
    macro_env = numpy_pickup_macro_aperture(freqs, src_pickup["coils"], speeds)

    # 1. DC / fundamental must be ~1.0 (within 0.1%)
    assert math.isclose(macro_env[0], 1.0, rel_tol=1e-3)

    # 2. Smooth aperture rolloff without comb nulls: > 0.70 at 2 kHz, > 0.05 at 10 kHz
    f2k_idx = np.argmin(np.abs(freqs - 2000.0))
    assert macro_env[f2k_idx] > 0.70
    assert all(x > 0.05 for x in macro_env)

def test_30in_mm_pj_subbass_retention():
    """Verify that 30in MM dual-coil playing P/J hybrid retains full sub-bass without collapse."""
    from scripts.analyze_voices import build_voice_dataframe
    from scripts.model_physics import VOICES

    df = build_voice_dataframe("07_modern_pj_active", VOICES["07_modern_pj_active"], instrument="30in_emg_mmtw")
    f20 = df.filter(df["frequency"] == 20.0)["magnitude_db"][0]
    f100 = df.filter((df["frequency"] >= 99.0) & (df["frequency"] <= 101.0))["magnitude_db"][0]
    f_max = df["magnitude_db"].max()

    # Sub-bass fundamental must be within 0.5 dB of expected response
    assert math.isclose(f20, 1.50, abs_tol=0.5)
    assert math.isclose(f100, 0.31, abs_tol=0.5)

    # Resonant peak must extend cleanly above passband (between +1.0 dB and +7.0 dB)
    assert 1.0 <= f_max <= 7.0

def test_30in_mm_jazz_pair_subbass_retention():
    """Verify that 30in MM dual-coil playing Jazz Bass pair retains full sub-bass without collapse."""
    from scripts.analyze_voices import build_voice_dataframe
    from scripts.model_physics import VOICES

    df = build_voice_dataframe("02_jazz_bass_pair", VOICES["02_jazz_bass_pair"], instrument="30in_emg_mmtw")
    f20 = df.filter(df["frequency"] == 20.0)["magnitude_db"][0]
    f100 = df.filter((df["frequency"] >= 99.0) & (df["frequency"] <= 101.0))["magnitude_db"][0]

    # Sub-bass fundamental must be within 0.5 dB of gain_db (-0.50 dB)
    assert math.isclose(f20, -0.50, abs_tol=0.5)
    assert math.isclose(f100, -0.63, abs_tol=0.5)

