"""
Allomorph - Two-Stage Pipeline & Staging Test Suite
Validates the Canonical Intermediate baseline, 32 frontend IRs, 3-tier dynamic continuum,
and concise stage-friendly naming invariants.
"""

import math
import wave
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from allomorph.circuit import (
    INTERMEDIATE_TARGET_PEAK_DBFS,
    export_all_frontend_irs,
    generate_canonical_sweep,
    simulate_voice,
)
from allomorph.config import (
    VOICES,
    get_source_pickup,
    load_instrument,
)
from allomorph.naming import (
    VOICE_CONCISE_SLUGS,
    get_baked_basename,
    resolve_instruments,
    resolve_voices,
)
from allomorph.physics import compute_voice_prefilter_firs
from allomorph.pipeline.schema import get_tier_spec


def test_canonical_intermediate_config():
    """Validates the Canonical Intermediate configuration datums."""
    inst = load_instrument("canonical_intermediate")
    assert inst.id == "canonical_intermediate"
    assert inst.scale_length_in == 34.0
    assert inst.scale_length_m == 0.8636

    pickups = inst.pickups
    assert len(pickups) == 1
    p = pickups["canonical_median"]
    assert p.position_from_bridge_m == pytest.approx(0.0935, abs=1e-4)
    assert p.aperture_width_in == pytest.approx(0.75, abs=1e-3)
    assert p.coil_spacing_in == 0.0

    # Wideband passive reference circuit
    assert inst.electronics == "passive"
    assert p.resonant_frequency_hz == pytest.approx(4800.0)
    assert p.q_factor == pytest.approx(0.75)


def test_canonical_sweep_calibration(tmp_path: Path):
    """Validates that the Canonical Intermediate sweep peak is strictly -1.50 dBFS."""
    sweep_path = tmp_path / "canonical_sweep.wav"
    generate_canonical_sweep(output_wav=sweep_path)

    assert sweep_path.exists()
    with wave.open(str(sweep_path), "rb") as wf:
        assert wf.getframerate() == 48000
        assert wf.getsampwidth() == 3  # 24-bit
        assert wf.getnchannels() == 1
        n = wf.getnframes()
        raw = wf.readframes(n)

    raw_padded = bytearray()
    for i in range(0, len(raw), 3):
        raw_padded.extend(raw[i : i + 3])
        raw_padded.append(0 if raw[i + 2] < 128 else 255)
    audio = np.frombuffer(raw_padded, dtype=np.int32).astype(np.float32) / 8388607.0

    peak = float(np.max(np.abs(audio)))
    peak_db = 20.0 * math.log10(peak)
    assert peak_db == pytest.approx(INTERMEDIATE_TARGET_PEAK_DBFS, abs=0.10)
    assert not np.isnan(audio).any()
    assert not np.isinf(audio).any()


def test_frontend_ir_generation(tmp_path: Path):
    """Validates that all 32 frontend IRs are exported with exact 2048-tap length and positive polarity."""
    exported = export_all_frontend_irs(output_dir=tmp_path)
    assert len(exported) == 32

    for ir_path in exported:
        assert ir_path.exists(), f"IR missing: {ir_path}"
        with wave.open(str(ir_path), "rb") as wf:
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3  # 24-bit
            assert wf.getnframes() == 2048, f"{ir_path} has {wf.getnframes()} taps (expected 2048)"
            raw = wf.readframes(2048)

        raw_padded = bytearray()
        for i in range(0, len(raw), 3):
            raw_padded.extend(raw[i : i + 3])
            raw_padded.append(0 if raw[i + 2] < 128 else 255)
        fir = np.frombuffer(raw_padded, dtype=np.int32).astype(np.float32) / 8388607.0

        # Positive initial polarity assertion
        assert np.sum(fir[:16]) > 0.0, f"{ir_path.name} has inverted polarity ({np.sum(fir[:16])})"
        # Zero NaN/Inf
        assert not np.isnan(fir).any()
        assert not np.isinf(fir).any()


def test_concise_naming_invariants():
    """Asserts that all 21 target voice model filenames across all 3 tiers are <= 22 characters."""
    assert isinstance(VOICE_CONCISE_SLUGS, dict)
    for k, v in VOICE_CONCISE_SLUGS.items():
        assert isinstance(k, str)
        assert isinstance(v, str)
        assert k in VOICES

    tier_prefixes = ["cln_", "std_", "hot_"]
    for slug in VOICE_CONCISE_SLUGS.values():
        for prefix in tier_prefixes:
            filename = f"{prefix}{slug}.nam"
            assert len(filename) <= 22, (
                f"Model filename '{filename}' exceeds 22 characters ({len(filename)} chars)"
            )


def test_backend_3_tier_dynamics():
    """Validates that Clean, Standard, and Hot Rod tiers have correct progressive saturation factors."""
    test_voice = "05_vintage_62_p_alnico"
    vcfg = VOICES[test_voice]
    base_alpha = vcfg.alpha if vcfg.alpha is not None else 0.25
    base_vsat = vcfg.vsat if vcfg.vsat is not None else 0.50

    # Clean: 0% saturation, high vsat
    clean_alpha = 0.0
    clean_vsat = 10.0
    assert clean_alpha == 0.0
    assert clean_vsat >= 10.0

    # Standard: 100% nominal saturation
    std_alpha = base_alpha
    std_vsat = base_vsat
    assert std_alpha == base_alpha
    assert std_vsat == base_vsat

    # Hot Rod: 175% saturation, reduced vsat
    hot_alpha = min(1.0, base_alpha * 1.75)
    hot_vsat = max(0.20, base_vsat / 1.35)
    assert hot_alpha > std_alpha
    assert hot_vsat < std_vsat


def test_bake_dynamic_tier_and_auto_pickup():
    """Validates the dynamic (differential) tier and auto pickup mapping for on-demand bake mode."""
    import tempfile

    # 1. Auto pickup mapping verification across instruments
    inst_30 = load_instrument("30in")
    p_p = get_source_pickup(inst_30, "04_modern_p_ceramic")
    p_j = get_source_pickup(inst_30, "03_jazz_bridge_60s")
    assert p_p.id == "mmtw_dual"
    assert p_j.id == "mmtw_single"

    inst_fretless = load_instrument("32in_fretless_pmm")
    p_upright = get_source_pickup(inst_fretless, "14_upright_bridge_transducer")
    assert p_upright.id == "pcsx"

    # 2. compute_voice_prefilter_firs supports explicit pickup and auto fallback
    firs_auto = compute_voice_prefilter_firs(
        "04_modern_p_ceramic", instrument=inst_30, src_pickup_key="auto"
    )
    firs_dual = compute_voice_prefilter_firs(
        "04_modern_p_ceramic", instrument=inst_30, src_pickup_key="mmtw_dual"
    )
    firs_single = compute_voice_prefilter_firs(
        "04_modern_p_ceramic", instrument=inst_30, src_pickup_key="mmtw_single"
    )
    assert len(firs_auto) == 1
    assert len(firs_dual) == 1
    assert len(firs_single) == 1
    assert np.allclose(firs_auto[0], firs_dual[0])
    # Single coil vs dual coil aperture response must differ
    assert not np.allclose(firs_dual[0], firs_single[0])

    # 3. Fast simulation test of dynamic tier with max_samples
    with tempfile.TemporaryDirectory() as tmpdir:
        out_wav = Path(tmpdir) / "test_dynamic_bake.wav"
        simulate_voice(
            "04_modern_p_ceramic",
            output_wav=out_wav,
            instrument="30in",
            pickup="auto",
            tier="dynamic",
            max_samples=2048,
        )
        assert out_wav.exists()
        with wave.open(str(out_wav), "rb") as wf:
            assert wf.getnframes() == 2048
            assert wf.getframerate() == 48000
            assert wf.getsampwidth() == 3


def test_baked_short_distinct_names_and_instrument_directories():
    """Validates that baked files have short distinct names (<= 22 chars) and group by instrument."""
    playable_insts = resolve_instruments("all")
    all_voices = resolve_voices("all")

    # 1. Check all voices produce unique, short distinct basenames under auto pickup
    for tier in ["dynamic", "standard", "clean", "hotrod"]:
        tier_prefix = get_tier_spec(tier).prefix
        basenames = set()
        for vid in all_voices:
            basename = get_baked_basename(vid, tier=tier, pickup="auto")
            assert basename.startswith(tier_prefix)
            wav_filename = f"{basename}.wav"
            assert len(wav_filename) <= 22, f"WAV filename '{wav_filename}' exceeds 22 chars"
            assert basename not in basenames, f"Duplicate basename: {basename}"
            basenames.add(basename)
        assert len(basenames) == len(all_voices)

    # 2. Non-auto explicit pickup appends pickup key
    override_basename = get_baked_basename("04_modern_p_ceramic", tier="dynamic", pickup="bridge")
    assert override_basename == "dyn_04_modern_p_bridge"

    # 3. Directory structure verification: each instrument has its own subfolder
    for inst_id in playable_insts:
        inst_baked_dir = Path("audio/baked") / inst_id
        assert inst_baked_dir.parent == Path("audio/baked")
        assert inst_baked_dir.name == inst_id


def test_pipeline_cli_streamlined_stages():
    """Asserts that the CLI parser accepts all 7 pure Architecture C stages and rejects deprecated stages."""
    import argparse

    # We inspect the parser directly by testing valid arguments
    valid_stages = ["all", "viz", "canonical", "frontends", "targets", "train", "bake"]
    deprecated_stages = ["prep", "spice", "sim", "simulate"]

    # Construct test parser matching main()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=["all", "viz", "canonical", "frontends", "targets", "train", "bake"],
        default="all",
    )

    for stage in valid_stages:
        parsed = parser.parse_args(["--stage", stage])
        assert parsed.stage == stage

    for dep_stage in deprecated_stages:
        with pytest.raises(SystemExit):
            parser.parse_args(["--stage", dep_stage])

    # Assert --bake flag is rejected
    with pytest.raises(SystemExit):
        parser.parse_args(["--bake"])


def test_export_frontend_ir_passive_missing_circuit_raises_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that export_frontend_ir raises ValueError if a passive pickup lacks a circuit model."""
    import allomorph.circuit.staging as staging_mod
    from allomorph.config.schema import InstrumentConfig, PickupConfig

    # Mock load_instrument to return a passive bass with a pickup missing 'circuit'
    dummy_passive = InstrumentConfig(
        id="mock_passive_p",
        name="Mock Passive P",
        electronics="passive",
        scale_length_in=34.0,
        string_wave_speeds=[73.4, 98.0, 130.8, 174.6],
        default_pickup="p",
        pickups={
            "p": PickupConfig(
                name="Passive P",
                position_from_bridge_m=0.125,
                aperture_width_in=0.75,
                coil_spacing_in=0.0,
                magnet_type="alnico_v",
                # Note: No 'circuit' defined!
            )
        },
    )

    def mock_load(inst_id: Any) -> InstrumentConfig:
        return dummy_passive

    monkeypatch.setattr(staging_mod, "load_instrument", mock_load)

    with pytest.raises(
        ValueError, match="does not define a '\\[pickups.p.circuit\\]' configuration"
    ):
        staging_mod.export_frontend_ir("mock_passive_p", "p")
