"""
Tests for Core Digital Signal Processing utilities in allomorph.dsp.
"""

import math
import tempfile
import wave
from pathlib import Path

import numpy as np

from allomorph.dsp import (
    fft_convolve,
    read_wav,
    read_wav_24bit,
    synthesize_minimum_phase_fir,
    write_wav_24bit,
)


def test_synthesize_minimum_phase_fir():
    # Simple lowpass magnitude curve
    mag_curve = [1.0 if i < 100 else 0.1 for i in range(4096)]
    num_taps = 4096
    fir = synthesize_minimum_phase_fir(mag_curve, num_taps=num_taps)

    assert len(fir) == num_taps

    # Peak normalization check (-0.1 dBFS, i.e., max peak is 0.99)
    max_peak = max(abs(x) for x in fir)
    assert math.isclose(max_peak, 0.99, rel_tol=1e-4)

    # Minimum phase causality: Energy should be concentrated at early taps
    early_energy = sum(x**2 for x in fir[:512])
    late_energy = sum(x**2 for x in fir[2048:])
    assert early_energy > late_energy * 10

    # Tail should taper smoothly towards zero
    assert abs(fir[-1]) < 0.01


def test_write_wav_24bit():
    samples = [0.0, 0.5, -0.5, 0.99, -0.99]
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "test_out.wav"
        write_wav_24bit(str(wav_path), samples, sample_rate=48000)

        assert wav_path.exists()
        with wave.open(str(wav_path), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 3  # 24-bit PCM
            assert wf.getframerate() == 48000
            assert wf.getnframes() == len(samples)


def test_read_wav_24bit_roundtrip():
    samples = np.array([0.0, 0.5, -0.5, 0.85, -0.85], dtype=np.float32)
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "test_roundtrip.wav"
        write_wav_24bit(str(wav_path), samples, sample_rate=48000)

        audio, sr = read_wav(wav_path)
        assert sr == 48000
        assert len(audio) == len(samples)
        assert np.allclose(audio, samples, atol=1e-4)

        # read_wav_24bit alias
        audio24, sr24 = read_wav_24bit(wav_path)
        assert sr24 == 48000
        assert np.array_equal(audio, audio24)

        # max_samples truncation
        audio_sub, _ = read_wav(wav_path, max_samples=3)
        assert len(audio_sub) == 3
        assert np.allclose(audio_sub, samples[:3], atol=1e-4)


def test_fft_convolve_modes_and_accuracy():
    # Test short and medium lengths
    for n, m in [(12, 5), (5, 12), (100, 32), (1000, 128)]:
        x = np.random.randn(n).astype(np.float64)
        y = np.random.randn(m).astype(np.float64)

        expected_full = np.convolve(x, y, mode="full")
        actual_full = fft_convolve(x, y, mode="full")
        assert np.allclose(actual_full, expected_full, atol=1e-9)

        expected_same = np.convolve(x, y, mode="same")
        actual_same = fft_convolve(x, y, mode="same")
        assert np.allclose(actual_same, expected_same, atol=1e-9)

    # Test overlap-add path (> 131072 samples)
    n_long = 150000
    m_ir = 256
    x_long = np.random.randn(n_long).astype(np.float32)
    y_ir = np.random.randn(m_ir).astype(np.float32)

    actual_overlap = fft_convolve(x_long, y_ir, mode="same")
    assert len(actual_overlap) == n_long

    # Check slice against direct convolve
    slice_len = 1000
    direct_slice = np.convolve(x_long[:slice_len], y_ir, mode="same")
    assert np.allclose(
        actual_overlap[m_ir : slice_len - m_ir], direct_slice[m_ir : slice_len - m_ir], atol=1e-4
    )
