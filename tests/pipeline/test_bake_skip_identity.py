"""
Unit tests for Allomorph --stage bake identity model skipping.
Verifies that bit-for-bit identity voices (H_diff == 1.0) are omitted from
baked exports when skip_identity=True, while transformative voices are produced.
"""

from pathlib import Path

from allomorph.circuit.schema import SimulationConfig
from allomorph.circuit.simulation import simulate_voice


def test_simulation_config_skip_identity_field():
    """Verify SimulationConfig has skip_identity field defaulting to False."""
    cfg = SimulationConfig()
    assert cfg.skip_identity is False

    cfg_skip = SimulationConfig(skip_identity=True)
    assert cfg_skip.skip_identity is True


def test_simulate_voice_skips_identity_when_flag_set(tmp_path: Path):
    """Verify simulate_voice returns False and removes output file when skip_identity=True on identity pair."""
    out_wav = tmp_path / "stingray_parallel.wav"
    out_wav.write_bytes(b"placeholder")

    cfg = SimulationConfig(
        instrument="34in_active_stingray",
        output_wav=out_wav,
        skip_identity=True,
        max_samples=2400,
    )

    success = simulate_voice("09_stingray_mm_parallel", config=cfg)
    assert success is False
    assert not out_wav.exists()


def test_simulate_voice_produces_file_for_transformative_voice(tmp_path: Path):
    """Verify simulate_voice produces a file and returns True for transformative voices even with skip_identity=True."""
    out_wav = tmp_path / "vintage_p.wav"

    cfg = SimulationConfig(
        instrument="34in_active_stingray",
        output_wav=out_wav,
        skip_identity=True,
        max_samples=2400,
    )

    success = simulate_voice("05_vintage_62_p_alnico", config=cfg)
    assert success is True
    assert out_wav.exists()
    assert out_wav.stat().st_size > 0


def test_pipeline_cli_bake_skips_identity():
    """Verify that running CLI with --stage bake on an identity voice does not output a WAV file."""
    from allomorph.naming import get_baked_basename
    from allomorph.pipeline.cli import REPO_ROOT, main

    baked_wav = (
        REPO_ROOT
        / "audio"
        / "baked"
        / "34in_active_stingray"
        / f"{get_baked_basename('09_stingray_mm_parallel', 'dynamic')}.wav"
    )
    if baked_wav.exists():
        baked_wav.unlink()

    test_argv = [
        "--stage",
        "bake",
        "--instrument",
        "34in_active_stingray",
        "--voice",
        "09_stingray_mm_parallel",
        "--max-samples",
        "2400",
    ]
    main(test_argv)

    assert not baked_wav.exists(), f"Identity voice should not be output: {baked_wav}"


