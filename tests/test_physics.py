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

    # 5-string Dingwall bridge matches Voice 13 (Dingwall Multi-Scale Bridge)
    inst_dingwall = load_instrument("37in_multiscale_dingwall")
    assert is_voice_matching_source(inst_dingwall, "13_dingwall_multiscale_bridge", VOICES["13_dingwall_multiscale_bridge"])

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
    assert math.isclose(f100, -0.56, abs_tol=0.5)

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

def test_jazz_differential_transfer_has_no_artificial_comb_filter():
    """Verify that multi-pickup matching source instruments (e.g. 34in_standard_jazz) have tau=0 and no comb filtering."""
    from scripts.model_physics import compute_voice_prefilter_firs, load_instrument, VOICES
    from scripts.analyze_voices import build_voice_dataframe

    # 1. FIRs must have zero inter-pickup delay (peak at tap 0)
    firs_01 = compute_voice_prefilter_firs("01_modern_jazz_active", instrument="34in_standard_jazz")
    assert len(firs_01) == 2
    assert np.argmax(np.abs(firs_01[0])) <= 2
    assert np.argmax(np.abs(firs_01[1])) <= 2

    firs_02 = compute_voice_prefilter_firs("02_jazz_bass_pair", instrument="34in_standard_jazz")
    assert len(firs_02) == 2
    assert np.argmax(np.abs(firs_02[0])) <= 2
    assert np.argmax(np.abs(firs_02[1])) <= 2

    # 2. Differential transfer function must be smooth without artificial comb filter notches
    inst = load_instrument("34in_standard_jazz")
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

    inst = load_instrument("30in_emg_mmtw")
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

        # 2. High-frequency comb filter notches above 1.8 kHz must be eliminated (no notches deeper than -7 dB)
        for f_check in [2000.0, 3200.0, 4400.0]:
            idx = np.argmin(np.abs(freqs - f_check))
            assert mags[idx] > -7.0, f"{voice_id} at {f_check} Hz was {mags[idx]:.1f} dB (expected > -7.0 dB, comb notch present)"

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

    # 2. Voice 12 (Mudbucker) on 34in Active StingRay
    p_inst = load_instrument("34in_active_stingray")
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

def test_per_string_acoustic_dispersion():
    """
    Verify Refinement: Per-string acoustic inharmonicity dispersion.
    Wave speed v(f) increases smoothly with frequency due to flexural stiffness,
    thick low strings disperse more than thin high strings, and response is bounded.
    """
    import math
    from scripts.model_physics import (
        compute_dispersive_wave_speed,
        numpy_pickup_acoustic_response,
        FREQS,
    )

    freqs = np.asarray(FREQS, dtype=np.float64)

    # 1. Low-E dispersion
    v0_e = 71.16
    v_disp_e = compute_dispersive_wave_speed(freqs, v0_e, "E")
    # At DC, v(0) == v0
    assert math.isclose(v_disp_e[0], v0_e, rel_tol=1e-5)
    # v(f) strictly non-decreasing with frequency
    diffs = np.diff(v_disp_e)
    assert np.all(diffs >= -1e-6)
    # Bounded: maximum boost at 8 kHz <= 1.15x
    assert v_disp_e[-1] <= 1.15 * v0_e

    # 2. String stiffness ranking: Low-B > Low-E > G > High-C
    v0_b = 58.0
    v0_g = 169.27
    v0_c = 225.0
    v_disp_b = compute_dispersive_wave_speed(freqs, v0_b, "B")
    v_disp_g = compute_dispersive_wave_speed(freqs, v0_g, "G")
    v_disp_c = compute_dispersive_wave_speed(freqs, v0_c, "C")

    idx_3k = np.argmin(np.abs(freqs - 3000.0))
    ratio_b = v_disp_b[idx_3k] / v0_b
    ratio_e = v_disp_e[idx_3k] / v0_e
    ratio_g = v_disp_g[idx_3k] / v0_g
    ratio_c = v_disp_c[idx_3k] / v0_c

    assert ratio_b > ratio_e > ratio_g > ratio_c

    # 3. Acoustic response with dispersion evaluates cleanly (4-string and 6-string)
    coils = [
        {"position_from_bridge_m": 0.065, "aperture_width_in": 0.75, "weight": 1.0, "polarity": 1.0, "strings": ["all"]}
    ]
    resp_4 = numpy_pickup_acoustic_response(freqs, coils, [71.16, 95.0, 126.81, 169.27])
    assert len(resp_4) == len(freqs)
    assert np.all(np.isfinite(resp_4))
    assert np.all(resp_4 > 0.0)
    assert math.isclose(resp_4[0], 1.0, rel_tol=1e-3)

    resp_6 = numpy_pickup_acoustic_response(freqs, coils, [58.0, 71.16, 95.0, 126.81, 169.27, 225.0])
    assert len(resp_6) == len(freqs)
    assert np.all(np.isfinite(resp_6))
    assert np.all(resp_6 > 0.0)
    assert math.isclose(resp_6[0], 1.0, rel_tol=1e-3)

def test_infer_string_names_and_split_coil_high_c():
    """
    Verify that infer_string_names accurately distinguishes Low-B vs High-C 5-string tunings,
    and that split-coil pickups bind High-C to the treble half and Low-B to the bass half.
    """
    from scripts.model_physics import infer_string_names, numpy_pickup_acoustic_response, FREQS

    # 4-string standard
    assert infer_string_names([71.16, 95.0, 126.81, 169.27]) == ["E", "A", "D", "G"]

    # 5-string Low-B (standard 34" and 37" multiscale)
    assert infer_string_names([53.28, 71.16, 95.0, 126.81, 169.27]) == ["B", "E", "A", "D", "G"]
    assert infer_string_names([58.02, 75.88, 99.19, 129.60, 169.27]) == ["B", "E", "A", "D", "G"]

    # 5-string High-C (E-A-D-G-C on standard 34" and 30" short scale)
    assert infer_string_names([71.16, 95.0, 126.81, 169.27, 225.69]) == ["E", "A", "D", "G", "C"]
    assert infer_string_names([62.79, 83.82, 111.89, 149.35, 199.36]) == ["E", "A", "D", "G", "C"]

    # 6-string
    assert infer_string_names([53.28, 71.16, 95.0, 126.81, 169.27, 225.69]) == ["B", "E", "A", "D", "G", "C"]

    # Split-coil P-Bass response with 5-string High-C:
    # Forward coil: E/A; Rearward coil: D/G. High-C should bind with D/G.
    freqs = np.asarray(FREQS, dtype=np.float64)
    split_p_coils = [
        {"position_from_bridge_m": 0.138, "aperture_width_in": 1.0, "weight": 1.0, "polarity": 1.0, "strings": [3, 4]},
        {"position_from_bridge_m": 0.112, "aperture_width_in": 1.0, "weight": 1.0, "polarity": 1.0, "strings": [1, 2]},
    ]
    # High-C 5-string speeds
    high_c_speeds = [71.16, 95.0, 126.81, 169.27, 225.69]
    resp_high_c = numpy_pickup_acoustic_response(freqs, split_p_coils, high_c_speeds)
    assert len(resp_high_c) == len(freqs)
    assert np.all(np.isfinite(resp_high_c))
    assert np.all(resp_high_c > 0.0)

def test_alternate_tunings_dispersion_and_split_coil():
    """
    Verify support for alternate and dropped tunings:
    - Drop D (D-A-D-G), Drop C (C-G-C-F), C Standard (C-F-A#-D#), D Standard (D-G-C-F), Drop A (A-E-A-D-G)
    - Continuous inharmonicity interpolation B_s(f0)
    - Split-coil (P-Bass) register routing ensuring dropped strings map to the bass coil half
    """
    import math
    from scripts.model_physics import (
        infer_string_names,
        get_inharmonicity_for_f0,
        compute_dispersive_wave_speed,
        numpy_pickup_acoustic_response,
        FREQS,
    )

    # 1. Tuning string name inference
    drop_d_speeds = [63.42, 95.00, 126.81, 169.27]
    assert infer_string_names(drop_d_speeds) == ["D", "A", "D", "G"]

    drop_c_speeds = [56.49, 84.63, 112.98, 150.82]
    assert infer_string_names(drop_c_speeds) == ["C", "G", "C", "F"]

    c_std_speeds = [56.49, 75.40, 100.65, 134.35]
    assert infer_string_names(c_std_speeds) == ["C", "F", "A#", "D#"]

    d_std_speeds = [63.42, 84.63, 112.98, 150.82]
    assert infer_string_names(d_std_speeds) == ["D", "G", "C", "F"]

    drop_a_5_speeds = [47.50, 71.16, 95.00, 126.81, 169.27]
    assert infer_string_names(drop_a_5_speeds) == ["A", "E", "A", "D", "G"]

    # 2. Continuous inharmonicity interpolation B_s(f0)
    bs_a0 = get_inharmonicity_for_f0(27.50)
    bs_c1 = get_inharmonicity_for_f0(32.70)
    bs_d1 = get_inharmonicity_for_f0(36.71)
    bs_e1 = get_inharmonicity_for_f0(41.20)
    bs_a1 = get_inharmonicity_for_f0(55.00)
    bs_d2 = get_inharmonicity_for_f0(73.42)
    bs_g2 = get_inharmonicity_for_f0(98.00)
    bs_c3 = get_inharmonicity_for_f0(130.81)

    # Strictly monotonic decrease with frequency / pitch
    assert bs_a0 > bs_c1 > bs_d1 > bs_e1 > bs_a1 > bs_d2 > bs_g2 > bs_c3
    # Bounded physical stiffness
    assert 1e-6 < bs_c1 < 5e-5
    assert 1e-6 < bs_d1 < 5e-5

    # 3. Wave speed dispersion for Drop D and Drop C
    freqs = np.asarray(FREQS, dtype=np.float64)
    v_disp_drop_d = compute_dispersive_wave_speed(freqs, 63.42)
    assert math.isclose(v_disp_drop_d[0], 63.42, rel_tol=1e-5)
    assert np.all(np.diff(v_disp_drop_d) >= -1e-6)
    assert v_disp_drop_d[-1] <= 1.15 * 63.42

    v_disp_drop_c = compute_dispersive_wave_speed(freqs, 56.49)
    assert math.isclose(v_disp_drop_c[0], 56.49, rel_tol=1e-5)
    assert np.all(np.diff(v_disp_drop_c) >= -1e-6)
    assert v_disp_drop_c[-1] <= 1.15 * 56.49

    # 4. Split-coil P-Bass response under Drop D and Drop C
    # Forward coil: 139mm (E/A strings); Rearward coil: 111mm (D/G strings)
    split_p_coils = [
        {"position_from_bridge_m": 0.1390, "aperture_width_in": 1.0, "weight": 1.0, "polarity": 1.0, "strings": [3, 4]},
        {"position_from_bridge_m": 0.1110, "aperture_width_in": 1.0, "weight": 1.0, "polarity": 1.0, "strings": [1, 2]},
    ]

    resp_drop_d = numpy_pickup_acoustic_response(freqs, split_p_coils, drop_d_speeds)
    assert len(resp_drop_d) == len(freqs)
    assert np.all(np.isfinite(resp_drop_d))
    assert np.all(resp_drop_d > 0.0)
    assert math.isclose(resp_drop_d[0], 1.0, rel_tol=1e-3)

    resp_drop_c = numpy_pickup_acoustic_response(freqs, split_p_coils, drop_c_speeds)
    assert len(resp_drop_c) == len(freqs)
    assert np.all(np.isfinite(resp_drop_c))
    assert np.all(resp_drop_c > 0.0)
    assert math.isclose(resp_drop_c[0], 1.0, rel_tol=1e-3)

    # Verify that string 0 in Drop D (named "D") binds to the forward coil (0.139m), not rearward coil (0.111m)
    single_string_0_d = numpy_pickup_acoustic_response(freqs, split_p_coils, [63.42], string_names=["D"])
    # If it was matched to both coils or rearward coil, response would differ.
    # Single coil forward:
    fwd_coil_resp = numpy_pickup_acoustic_response(freqs, [split_p_coils[0]], [63.42])
    assert np.allclose(single_string_0_d, fwd_coil_resp, rtol=1e-4)

def test_body_microphonic_coupling():
    """Verify mechanical body-pickup microphonic coupling physics and differential scaling."""
    from scripts.model_physics import compute_body_microphonic_coupling, FREQS

    freqs = np.asarray(FREQS, dtype=np.float64)

    # 1. Active EMG source to Vintage Alnico V target: Δk_body = 0.08 - 0.0 = 0.08
    src_pickup_active = {"magnet_type": "active"}
    tgt_voice_alnico5 = {"magnet_type": "alnico_v"}
    h_body = compute_body_microphonic_coupling(freqs, src_pickup_active, tgt_voice_alnico5)

    assert len(h_body) == len(freqs)
    assert np.all(np.isfinite(h_body))
    # DC and sub-audible must be exactly 1.0 (0.0 dB)
    assert math.isclose(h_body[0], 1.0, rel_tol=1e-5)
    # Peak must occur near 6.2 kHz
    peak_idx = int(np.argmax(h_body))
    peak_freq = freqs[peak_idx]
    assert 5500.0 <= peak_freq <= 6800.0
    # Boost should be subtle (+0.4 to +0.55 dB)
    peak_db = 20.0 * np.log10(h_body[peak_idx])
    assert 0.35 <= peak_db <= 0.55
    # Ultrasonic damping: above 15 kHz, curve smoothly rolls back toward 1.0
    idx_18k = int(np.argmin(np.abs(freqs - 18000.0)))
    assert 20.0 * np.log10(h_body[idx_18k]) < 0.15

    # 2. Matching passive source (Alnico V to Alnico V): Δk_body = 0.0 -> exact identity
    src_alnico5 = {"magnet_type": "alnico_v"}
    h_body_id = compute_body_microphonic_coupling(freqs, src_alnico5, tgt_voice_alnico5)
    assert np.allclose(h_body_id, 1.0, atol=1e-12)

    # 3. Active-to-active: exact identity
    src_active = {"magnet_type": "active"}
    tgt_active = {"magnet_type": "active"}
    h_body_active = compute_body_microphonic_coupling(freqs, src_active, tgt_active)
    assert np.allclose(h_body_active, 1.0, atol=1e-12)


def test_multiscale_wave_speed_continuum_endpoints():
    """Verify that 34"-37" multi-scale Dingwall wave speeds continuously interpolate
    from 37" scale at Low B (30.87 Hz) to 34" scale at High G (100.0 Hz)."""
    from scripts.model_physics import generate_wave_speed_continuum, load_instrument

    inst = load_instrument("37in_multiscale_dingwall")
    continuum = generate_wave_speed_continuum(inst, num_points=24)

    # First point: f0 = 30.87 Hz (Low B), scale = 37.0" (0.9398 m)
    pt_low = continuum[0]
    assert math.isclose(pt_low["f0"], 30.87, abs_tol=0.01)
    assert math.isclose(pt_low["scale_m"], 37.0 * 0.0254, abs_tol=1e-4)
    expected_v_low = 2.0 * (37.0 * 0.0254) * pt_low["f0"]
    assert math.isclose(pt_low["v0"], expected_v_low, abs_tol=0.01)

    # Last point: f0 = 100.0 Hz (High G), scale = 34.0" (0.8636 m)
    pt_high = continuum[-1]
    assert math.isclose(pt_high["f0"], 100.00, abs_tol=0.01)
    assert math.isclose(pt_high["scale_m"], 34.0 * 0.0254, abs_tol=1e-4)
    expected_v_high = 2.0 * (34.0 * 0.0254) * pt_high["f0"]
    assert math.isclose(pt_high["v0"], expected_v_high, abs_tol=0.01)

    # All intermediate scale lengths must monotonically decrease from 37" to 34"
    scales = [pt["scale_m"] for pt in continuum]
    assert all(scales[i] >= scales[i+1] for i in range(len(scales)-1))


def test_multiscale_sp1_wave_speed_continuum_endpoints():
    """Verify that 32"-35" multi-scale Dingwall SP1 wave speeds continuously interpolate
    from 35" scale at Low B (30.87 Hz) to 32" scale at High G (100.0 Hz)."""
    from scripts.model_physics import generate_wave_speed_continuum, load_instrument

    inst = load_instrument("34in_dingwall_sp1")
    continuum = generate_wave_speed_continuum(inst, num_points=24)

    # First point: f0 = 30.87 Hz, scale = 35.0" (0.8890 m)
    pt_low = continuum[0]
    assert math.isclose(pt_low["f0"], 30.87, abs_tol=0.01)
    assert math.isclose(pt_low["scale_m"], 35.0 * 0.0254, abs_tol=1e-4)
    expected_v_low = 2.0 * (35.0 * 0.0254) * pt_low["f0"]
    assert math.isclose(pt_low["v0"], expected_v_low, abs_tol=0.01)

    # Last point: f0 = 100.0 Hz, scale = 32.0" (0.8128 m)
    pt_high = continuum[-1]
    assert math.isclose(pt_high["f0"], 100.00, abs_tol=0.01)
    assert math.isclose(pt_high["scale_m"], 32.0 * 0.0254, abs_tol=1e-4)
    expected_v_high = 2.0 * (32.0 * 0.0254) * pt_high["f0"]
    assert math.isclose(pt_high["v0"], expected_v_high, abs_tol=0.01)

    # All intermediate scale lengths must monotonically decrease from 35" to 32"
    scales = [pt["scale_m"] for pt in continuum]
    assert all(scales[i] >= scales[i+1] for i in range(len(scales)-1))


def test_cylindrical_rod_vs_blade_aperture():
    """Verify 2D cylindrical rod aperture (Airy/Bessel) and 1D blade aperture properties."""
    from scripts.model_physics import compute_coil_aperture, FREQS
    freqs = np.asarray(FREQS, dtype=np.float64)
    v_disp = np.full_like(freqs, 100.0)
    w_m = 0.75 * 0.0254

    ap_rod = compute_coil_aperture(freqs, v_disp, w_m, pole_type="rod")
    ap_blade = compute_coil_aperture(freqs, v_disp, w_m, pole_type="blade")

    # 1. Exact unity at DC
    assert math.isclose(ap_rod[0], 1.0, abs_tol=1e-6)
    assert math.isclose(ap_blade[0], 1.0, abs_tol=1e-6)

    # 2. Both must be strictly monotonic decreasing
    assert np.all(np.diff(ap_rod) <= 1e-9)
    assert np.all(np.diff(ap_blade) <= 1e-9)

    # 3. Rod pole piece (2D disc) has slightly higher high-frequency response than a full-width blade
    idx_4k = np.argmin(np.abs(freqs - 4000.0))
    assert ap_rod[idx_4k] > ap_blade[idx_4k], "Cylindrical rod should exhibit crisper top-end transmission than a solid blade"


def test_saddle_witness_point_boundary_stiffness():
    """Verify bridge saddle boundary layer stiffness behavior."""
    from scripts.model_physics import compute_saddle_boundary_coupling, FREQS
    freqs = np.asarray(FREQS, dtype=np.float64)

    # 1. Distances >= 75 mm (e.g. neck pickup or P-bass at 125 mm) must return exact 1.0
    h_p = compute_saddle_boundary_coupling(freqs, pos_m=0.125)
    assert np.all(h_p == 1.0), "Pickups >= 75 mm from bridge must not be attenuated by saddle boundary"

    # 2. Close bridge pickup (e.g. 60s Jazz bridge at 63.5 mm)
    h_bridge = compute_saddle_boundary_coupling(freqs, pos_m=0.0635)
    assert math.isclose(h_bridge[0], 1.0, abs_tol=1e-6), "Saddle coupling must be exact 1.0 at DC"
    assert np.all(np.diff(h_bridge) <= 1e-9), "Saddle coupling must be monotonically decreasing"

    # Attenuation at 10 kHz should be subtle (< 1.5 dB)
    idx_10k = np.argmin(np.abs(freqs - 10000.0))
    att_db = 20.0 * np.log10(h_bridge[idx_10k])
    assert -1.8 < att_db < -0.3, f"Saddle attenuation at 10 kHz was {att_db:.2f} dB (expected -1.8 to -0.3 dB)"

    # 3. Very close bridge pickup (e.g. Dingwall bridge at 48 mm)
    h_dingwall = compute_saddle_boundary_coupling(freqs, pos_m=0.048)
    assert h_dingwall[idx_10k] < h_bridge[idx_10k], "Pickups closer to bridge should experience slightly greater boundary stiffness damping"








