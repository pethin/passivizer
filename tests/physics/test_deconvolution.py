"""
Tests for pickup electrical resonance and biquad deconvolution.
"""

import math
import numpy as np

from allomorph.config import load_instrument
from allomorph.physics import pickup_electrical_response, resolve_pickup_electrical_deconvolution


def test_electrical_resonance_and_deconvolution():
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
