import math
import os
import tempfile
import wave
from pathlib import Path
from scripts.model_physics import (
    VOICES,
    SCALES,
    compute_aperture_prefilter_fir,
    write_wav_24bit,
    NUM_TAPS
)
from scripts.prep_nam_audio import prefilter_audio

def test_compute_aperture_prefilter_fir_30in():
    voice_id = "03_modern_p_ceramic"
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
    voice_id = "07_stingray_mm_parallel"
    fir = compute_aperture_prefilter_fir(voice_id, src_scale="32in", num_taps=NUM_TAPS)

    assert len(fir) == NUM_TAPS
    max_peak = max(abs(x) for x in fir)
    assert math.isclose(max_peak, 0.99, rel_tol=1e-3)

    early_energy = sum(x ** 2 for x in fir[:256])
    late_energy = sum(x ** 2 for x in fir[1024:])
    assert early_energy > late_energy * 5

def test_compute_aperture_prefilter_multiscale():
    voice_id = "11_dingwall_multiscale_bridge"
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

        fir = compute_aperture_prefilter_fir("03_modern_p_ceramic", src_scale="30in", num_taps=512)
        prefilter_audio(input_wav, output_wav, fir)

        assert output_wav.exists()
        with wave.open(str(output_wav), "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3  # 24-bit PCM
            assert wf.getnchannels() == 1
            assert wf.getnframes() > 0
