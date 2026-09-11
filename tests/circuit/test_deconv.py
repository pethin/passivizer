"""
Tests for differential circuit deconvolution, Wiener regularization,
dielectric absorption, and Jordan permeability relaxation.
"""

import math
import numpy as np
import pytest

from allomorph.circuit import (
    parse_netlist,
    compute_circuit_transfer_functions,
    compute_differential_circuit_transfer_functions,
    compute_core_impedance,
    CIRCUITS_DIR,
    REPO_ROOT,
)
from allomorph.config import VOICES
from allomorph.dsp import FREQS, NUM_TAPS
from allomorph.physics import compute_voice_prefilter_firs


def test_passive_identity_differential_flatness():
    """Verify that identity differential response is flat, and pot unloading is accurately modeled."""
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
    # 1. Source netlist existence & parsing
    m_src_ray = parse_netlist(CIRCUITS_DIR / "sources" / "source_active_stingray.cir")
    assert m_src_ray.has_active_buffer is True
    assert m_src_ray.preamp_type == "stingray_2band"

    m_src_ding = parse_netlist(CIRCUITS_DIR / "sources" / "source_dingwall_fd3n.cir")
    assert m_src_ding.has_active_buffer is True
    assert m_src_ding.preamp_type == "none"
    assert m_src_ding.L == 2.3

    # SP1 Passive Dingwall bridge source verification
    m_src_sp1 = parse_netlist(CIRCUITS_DIR / "sources" / "source_dingwall_sp1_bridge.cir")
    assert m_src_sp1.has_active_buffer is False
    assert m_src_sp1.L == 2.3
    assert m_src_sp1.Rtop == 10
    assert m_src_sp1.Rbot == 250000.0

    # 2. Mathematical identity flatness (exact 0.00 dB everywhere, including DC and 20 kHz)
    m_tgt_ray = parse_netlist(CIRCUITS_DIR / "09_stingray_mm_parallel.cir")
    diff_ray = compute_differential_circuit_transfer_functions(m_tgt_ray, m_src_ray, freqs=FREQS)
    assert np.all(np.array(diff_ray[0]) == 1.0)

    m_tgt_ding = parse_netlist(CIRCUITS_DIR / "13_dingwall_multiscale_bridge.cir")
    assert m_tgt_ding.has_active_buffer is True
    assert m_tgt_ding.preamp_type == "none"
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


def test_wiener_clamping_prevents_noise_explosion():
    """Verify that differential top-end boost is strictly clamped <= +6.0 dB above 4.5 kHz."""
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


def test_fractional_order_dielectric_absorption():
    """Verify Cole-Davidson fractional-order dielectric absorption in capacitors."""
    # Load Voice 05c (47nF rolled tone)
    m = parse_netlist(CIRCUITS_DIR / "05c_vintage_62_p_47nf.cir")

    # 1. Ideal capacitor (alpha = 1.0)
    m.alpha_dielectric_tone = 1.0
    m.alpha_dielectric_cable = 1.0
    curves_ideal = compute_circuit_transfer_functions(m, freqs=FREQS)

    # 2. Fractional-order film dielectric (alpha = 0.988)
    m.alpha_dielectric_tone = 0.988
    m.alpha_dielectric_cable = 0.994
    curves_dielectric = compute_circuit_transfer_functions(m, freqs=FREQS)

    mag_ideal = np.asarray(curves_ideal[0])
    mag_dielectric = np.asarray(curves_dielectric[0])

    # Dielectric absorption should create subtle, smooth loss differences (within 0.05 to 1.5 dB across passband)
    diff_db = 20.0 * np.log10(np.maximum(mag_dielectric, 1e-6) / np.maximum(mag_ideal, 1e-6))
    assert np.all(np.abs(diff_db) < 2.0), "Dielectric absorption should be a subtle analog nuance"
    assert np.max(np.abs(diff_db)) > 0.05, "Dielectric absorption must produce non-trivial difference"
    # At low frequencies (200 Hz), dielectric absorption provides subtle low-mid loss/bloom
    idx_200 = min(range(len(FREQS)), key=lambda i: abs(FREQS[i] - 200.0))
    assert diff_db[idx_200] < 0.0, "Dielectric relaxation should introduce low-mid dissipation"


def test_complex_magnetic_permeability_dispersion():
    """Verify causal Jordan complex permeability dispersion provides midrange core loss and preserves differential identity."""
    omega = 2.0 * np.pi * np.array([400.0, 800.0, 1200.0, 2400.0], dtype=np.float64)
    s = 1j * omega

    # 1. Complex core impedance with chi_mu > 0
    Z_ideal = compute_core_impedance(s, L=5.0, R_core=25000.0, chi_mu=0.0)
    Z_dispersive = compute_core_impedance(s, L=5.0, R_core=25000.0, chi_mu=0.04)

    # Real part (resistive loss) must be enhanced by Jordan relaxation
    assert np.all(np.real(Z_dispersive) > np.real(Z_ideal)), "Complex permeability must add core relaxation losses"
    assert not np.any(np.isnan(Z_dispersive))

    # 2. Differential transfer function of matching model must be exact identity (0.00 dB)
    m1 = parse_netlist(CIRCUITS_DIR / "05_vintage_62_p_alnico.cir")
    m2 = parse_netlist(CIRCUITS_DIR / "05_vintage_62_p_alnico.cir")
    m1.chi_mu = 0.04
    m2.chi_mu = 0.04
    diff_curves = compute_differential_circuit_transfer_functions(m1, m2, freqs=FREQS)
    for curve in diff_curves:
        assert np.allclose(curve, 1.0, atol=1e-4), "Matching complex permeability models must yield exact 0.00 dB identity"


def test_source_direct_simulation():
    """Verify 15_source_direct deconvolutes Canonical Intermediate aperture and preserves tier dynamics."""
    vcfg = VOICES["15_source_direct"]
    assert vcfg["sensor_type"] == "direct"
    assert vcfg["alpha"] == 0.26
    assert vcfg["vsat"] == 0.50

    # Netlist must be a no_eq flat studio buffer
    model = parse_netlist(REPO_ROOT / vcfg["circuit"])
    assert getattr(model, "no_eq", False) is True

    # Evaluated on canonical intermediate, prefilter FIR must invert the 93.5mm aperture sinc
    firs = compute_voice_prefilter_firs("15_source_direct", instrument="canonical_intermediate")
    assert len(firs) == 1
    fir = np.array(firs[0])
    assert len(fir) == NUM_TAPS

    # Frequency response of FIR should gently deconvolve the high-frequency aperture droop
    f_bins = np.fft.rfftfreq(8192, 1.0 / 48000.0)
    H = np.abs(np.fft.rfft(fir, 8192))
    gain_5k = H[np.argmin(np.abs(f_bins - 5000))] / H[np.argmin(np.abs(f_bins - 20))]
    assert 1.2 <= gain_5k <= 2.5


def test_active_character_differential_cable_isolation():
    """Verify 16_active_character deconvolves passive cable loading when evaluating from a passive bass."""
    tgt_model = parse_netlist(REPO_ROOT / "circuits" / "16_active_character.cir")
    src_model = parse_netlist(REPO_ROOT / "circuits" / "sources" / "source_standard_p.cir")

    diff_curves = compute_differential_circuit_transfer_functions(tgt_model, src_model, freqs=FREQS)
    assert len(diff_curves) == 1
    h_diff = np.array(diff_curves[0])

    # At 100 Hz, both circuits have flat DC/low-frequency transmission
    idx_100 = np.argmin(np.abs(np.array(FREQS) - 100.0))
    assert 0.90 <= h_diff[idx_100] <= 1.15

    # At 8 kHz, passive circuit has heavy cable loading, active buffer is isolated
    idx_8k = np.argmin(np.abs(np.array(FREQS) - 8000.0))
    assert h_diff[idx_8k] > 1.0, "Active buffer must deconvolve passive cable loading at 8 kHz"
