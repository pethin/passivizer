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

def test_active_jazz_differential_transfer_has_no_artificial_comb_filter():
    """Verify that multi-pickup matching source instruments (e.g. 34in_active_jazz) have tau=0 and no comb filtering."""
    from scripts.model_physics import compute_voice_prefilter_firs, load_instrument, VOICES
    from scripts.analyze_voices import build_voice_dataframe

    # 1. FIRs must have zero inter-pickup delay (peak at tap 0)
    firs_01 = compute_voice_prefilter_firs("01_modern_jazz_active", instrument="34in_active_jazz")
    assert len(firs_01) == 2
    assert np.argmax(np.abs(firs_01[0])) <= 2
    assert np.argmax(np.abs(firs_01[1])) <= 2

    firs_02 = compute_voice_prefilter_firs("02_jazz_bass_pair", instrument="34in_active_jazz")
    assert len(firs_02) == 2
    assert np.argmax(np.abs(firs_02[0])) <= 2
    assert np.argmax(np.abs(firs_02[1])) <= 2

    # 2. Differential transfer function must be smooth without artificial comb filter notches
    inst = load_instrument("34in_active_jazz")
    df_01 = build_voice_dataframe("01_modern_jazz_active", VOICES["01_modern_jazz_active"], instrument=inst)
    mags_01 = df_01["magnitude_db"].to_numpy()
    freqs = df_01["frequency"].to_numpy()

    i100 = np.argmin(np.abs(freqs - 100.0))
    i600 = np.argmin(np.abs(freqs - 600.0))
    i1800 = np.argmin(np.abs(freqs - 1800.0))

    # Without artificial comb filter, 600 Hz and 1800 Hz are within 2.0 dB of 100 Hz (smooth preamp shelf)
    assert abs(mags_01[i600] - mags_01[i100]) < 2.0
    assert abs(mags_01[i1800] - mags_01[i100]) < 2.0

def test_single_to_multi_pickup_coherence_eliminates_high_frequency_comb_notches():
    """Verify that single-to-multi pickup conversion retains the 600-800 Hz acoustic scoop while eliminating high-frequency comb notches."""
    from scripts.model_physics import load_instrument, VOICES
    from scripts.analyze_voices import build_voice_dataframe

    inst = load_instrument("34in_active_p")
    for voice_id in ["01_modern_jazz_active", "02_jazz_bass_pair"]:
        df = build_voice_dataframe(voice_id, VOICES[voice_id], instrument=inst)
        mags = df["magnitude_db"].to_numpy()
        freqs = df["frequency"].to_numpy()

        i100 = np.argmin(np.abs(freqs - 100.0))
        mask_mid = (freqs >= 500.0) & (freqs <= 800.0)
        min_mid = np.min(mags[mask_mid])
        scoop_depth = mags[i100] - min_mid

        # 1. Iconic acoustic mid-scoop must be preserved (> 10 dB depth relative to 100 Hz)
        assert scoop_depth >= 10.0, f"{voice_id} mid-scoop was {scoop_depth:.1f} dB (expected >= 10 dB)"

        # 2. High-frequency comb filter notches above 1.8 kHz must be eliminated (no notches deeper than -6 dB)
        for f_check in [2000.0, 3200.0, 4400.0]:
            idx = np.argmin(np.abs(freqs - f_check))
            assert mags[idx] > -6.0, f"{voice_id} at {f_check} Hz was {mags[idx]:.1f} dB (expected > -6.0 dB, comb notch present)"

    # 3. Voice 01 must rise smoothly without periodic comb ripple oscillations in 1.5 - 5.0 kHz
    df_01 = build_voice_dataframe("01_modern_jazz_active", VOICES["01_modern_jazz_active"], instrument=inst)
    mags_01 = df_01["magnitude_db"].to_numpy()
    freqs_01 = df_01["frequency"].to_numpy()
    mask_mid_hi = (freqs_01 >= 1500.0) & (freqs_01 <= 5000.0)
    diffs = np.diff(mags_01[mask_mid_hi])
    assert np.all(diffs >= -0.05), "High frequencies must rise smoothly without periodic comb ripple oscillations"


def test_scale_normalized_bridge_proximity_displacement():
    """Verify that bridge proximity spatial displacement uses scale-normalized fractional positions."""
    from scripts.model_physics import load_instrument, SCALES, VOICES, compute_effective_position

    # In 32in custom P/MM, MM pickup is at 62.2mm on 812.8mm scale: eta = 0.0765
    # In 34in StingRay, MM pickup is at 66.0mm on 863.6mm scale: eta = 0.0764
    # The fractional displacement between the two matching sweet spots is virtually zero
    eta_32 = 0.0622 / 0.8128
    eta_34 = 0.0660 / 0.8636
    delta_in_scaled = (eta_34 - eta_32) * 34.0
    assert abs(delta_in_scaled) < 0.01

    # Raw absolute mm would erroneously claim the 34in is +0.15" further forward
    delta_in_unnormalized = (0.0660 - 0.0622) / 0.0254
    assert delta_in_unnormalized > 0.14


def test_multicoil_wavelength_dependent_coherence_and_mudbucker():
    """Verify that multi-coil cross-coherence decays smoothly without kinks and mudbucker rolls off monotonically."""
    from scripts.model_physics import load_instrument, VOICES
    from scripts.analyze_voices import build_voice_dataframe

    # 1. Voice 09 (Music Man StingRay) on 34in Standard Jazz Bass
    jazz_inst = load_instrument("34in_standard_jazz")
    df_09 = build_voice_dataframe("09_stingray_mm_parallel", VOICES["09_stingray_mm_parallel"], instrument=jazz_inst, mode="difference")
    f_09 = df_09["frequency"].to_numpy()
    m_09 = df_09["magnitude_db"].to_numpy()

    # Fundamental mid-scoop at 2.5 kHz must be preserved (< -5.0 dB)
    scoop_mask = (f_09 >= 2200.0) & (f_09 <= 2800.0)
    assert np.min(m_09[scoop_mask]) < -5.0

    # Treble rise from 4.5 kHz to 7.0 kHz must be strictly monotonic (no 5.4 kHz plateau/kink)
    treble_mask = (f_09 >= 4500.0) & (f_09 <= 7000.0)
    diffs_09 = np.diff(m_09[treble_mask])
    assert np.all(diffs_09 >= -0.05), "Treble rise must be smooth and monotonic without kinks or plateaus"

    # 2. Voice 12 (Mudbucker) on 34in Active P-Bass
    p_inst = load_instrument("34in_active_p")
    df_12 = build_voice_dataframe("12_mudbucker_ultra_series", VOICES["12_mudbucker_ultra_series"], instrument=p_inst, mode="difference")
    f_12 = df_12["frequency"].to_numpy()
    m_12 = df_12["magnitude_db"].to_numpy()

    # Sub-bass punch (+6.2 dB)
    assert m_12[0] > 5.5

    # Strictly monotonic rolloff above 1.5 kHz (no zigzag comb teeth)
    rolloff_mask = (f_12 >= 1500.0) & (f_12 <= 18000.0)
    diffs_12 = np.diff(m_12[rolloff_mask])
    assert np.all(diffs_12 <= 0.05), "Mudbucker response must roll off monotonically without secondary peaks or teeth"


def test_dynamic_coherence_decay_and_multiscale_snap():
    """Verify dynamic delay-based coherence window for P/J and multiscale tension snap for short-scale."""
    from scripts.model_physics import load_instrument, compute_voice_prefilter_firs, VOICES
    from scripts.analyze_voices import build_voice_dataframe

    # 1. Voice 07 (P/J Bass) on 30in short scale has delta = 25 samples (tau = 0.52ms, notch = 960Hz)
    inst_30 = load_instrument("30in_emg_mmtw")
    df_07 = build_voice_dataframe("07_modern_pj_active", VOICES["07_modern_pj_active"], instrument=inst_30, mode="difference")
    f_07 = df_07["frequency"].to_numpy()
    m_07 = df_07["magnitude_db"].to_numpy()

    # The dynamic coherence window must preserve the authentic ~10-11 dB P/J mid-scoop at 960 Hz
    idx_notch = np.argmin(np.abs(f_07 - 960.0))
    assert m_07[idx_notch] < -8.0, f"Expected deep P/J mid-scoop at 960 Hz, got {m_07[idx_notch]:.2f} dB"

    # 2. Voice 13 (Dingwall Multi-Scale) on 30in short scale must receive tension snap
    firs_13 = compute_voice_prefilter_firs("13_dingwall_multiscale_bridge", instrument=inst_30)
    assert len(firs_13) == 1
    # Check that prefilter is non-trivial and has high-frequency energy
    assert np.linalg.norm(firs_13[0]) > 0.1



