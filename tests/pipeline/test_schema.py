"""
Unit tests for pipeline schemas (CLI arguments, storefront listings, NAM model metadata).
"""

import pytest
from pydantic import ValidationError

from allomorph.pipeline.schema import (
    NamExportMetadata,
    NamSourceInstrumentMeta,
    NamTargetVoiceMeta,
    PipelineCliConfig,
    Tone3000PackListing,
)


def test_pipeline_cli_config_validation():
    """Verify PipelineCliConfig validation of command line options."""
    cfg = PipelineCliConfig(stage="targets", tier="standard", instrument="30in", cable_pf=750.0)
    assert cfg.stage == "targets"
    assert cfg.tier == "standard"
    assert cfg.instrument == "30in"

    with pytest.raises(ValidationError):
        PipelineCliConfig(stage="unsupported_stage")  # type: ignore[arg-type]


def test_tone3000_pack_listing_validation():
    """Verify Tone3000PackListing constraints on character counts and voicings."""
    valid_desc = "x" * 7500
    valid_voicings = [f"Voice {i}" for i in range(1, 23)]

    listing = Tone3000PackListing(
        edition="standard_precision_bass",
        description=valid_desc,
        pickup_tags=["[Split-P]"],
        voicings=valid_voicings,
    )
    assert listing.edition == "standard_precision_bass"

    # Too short description (< 7000 chars)
    with pytest.raises(ValidationError):
        Tone3000PackListing(
            edition="test",
            description="Too short description",
            voicings=valid_voicings,
        )

    # Incorrect number of voicings (!= 22)
    with pytest.raises(ValidationError):
        Tone3000PackListing(
            edition="test",
            description=valid_desc,
            voicings=valid_voicings[:20],
        )


def test_nam_export_metadata_validation():
    """Verify NamExportMetadata and nested instrument/voice metadata validation."""
    meta = NamExportMetadata(
        training={"esr": 0.0004, "epochs": 100},
        license="PolyForm Noncommercial License 1.0.0",
        copyright="Copyright 2026 Peter Nguyen",
        author="Peter Nguyen",
        source_instrument=NamSourceInstrumentMeta(
            id="30in",
            name='30" Short Scale Bass',
            scale_length_in=30.0,
            scale_length_m=0.762,
            string_wave_speeds=[58.0, 75.0, 99.0, 130.0],
            pickup={"name": "EMG MMTW", "position_from_bridge_m": 0.0775},
        ),
        target_voice=NamTargetVoiceMeta(
            id="05_vintage_62_p_alnico",
            name="'62 Precision Bass (Alnico V)",
            topology="single",
            resonant_frequency_hz=3200.0,
            q_factor=1.8,
        ),
    )
    assert meta.source_instrument.id == "30in"
    assert meta.target_voice.id == "05_vintage_62_p_alnico"

    # Rejection of missing required fields
    with pytest.raises(ValidationError):
        NamExportMetadata.model_validate({"training": {}})
