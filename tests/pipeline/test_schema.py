"""
Unit tests for pipeline schemas (CLI arguments, storefront listings, NAM model metadata).
"""

import pytest
from pydantic import ValidationError

from allomorph.pipeline.schema import (
    ArtworkPackConfig,
    NamExportMetadata,
    NamSourceInstrumentMeta,
    NamSourcePickupMeta,
    NamTargetVoiceMeta,
    NamTrainingConfig,
    NamTrainingMetadata,
    PipelineCliConfig,
    TierSpec,
    Tone3000PackListing,
    get_tier_spec,
)


def test_pipeline_cli_config_validation():
    """Verify PipelineCliConfig validation of command line options."""
    cfg = PipelineCliConfig(stage="targets", tier="standard", instrument="30in", cable_pf=750.0)
    assert cfg.stage == "targets"
    assert cfg.tier == "standard"
    assert cfg.instrument == "30in"

    with pytest.raises(ValidationError):
        PipelineCliConfig(stage="unsupported_stage")  # type: ignore[arg-type]


def test_tone3000_listing_validation():
    """Verify Tone3000PackListing minimum and maximum length bounds."""
    valid_desc = "A" * 7500
    valid_voicings = [f"voicing_{i:02d}" for i in range(22)]
    listing = Tone3000PackListing(
        edition="standard_precision_bass",
        description=valid_desc,
        pickup_tags=["split_coil", "alnico_v"],
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
        training=NamTrainingMetadata(esr=0.0004, epochs=100),
        license="PolyForm Noncommercial License 1.0.0",
        copyright="Copyright 2026 Peter Nguyen",
        author="Peter Nguyen",
        source_instrument=NamSourceInstrumentMeta(
            id="30in",
            name='30" Short Scale Bass',
            scale_length_in=30.0,
            scale_length_m=0.762,
            string_wave_speeds=[58.0, 75.0, 99.0, 130.0],
            pickup=NamSourcePickupMeta(name="EMG MMTW", position_from_bridge_m=0.0775),
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
    assert meta.training.esr == 0.0004
    assert meta.source_instrument.pickup.name == "EMG MMTW"

    # Rejection of missing required fields
    with pytest.raises(ValidationError):
        NamExportMetadata.model_validate({"training": {}})


def test_nam_training_config_validation():
    """Verify NamTrainingConfig defaults and hyperparameter bounds."""
    cfg = NamTrainingConfig()
    assert cfg.instrument == "all"
    assert cfg.voice == "all"
    assert cfg.epochs == 500
    assert cfg.batch_size == 32
    assert cfg.goal_esr == 0.0005
    assert cfg.a2_full is False

    # Valid custom configuration
    custom = NamTrainingConfig(
        instrument="30in",
        voice="05_vintage_62_p_alnico",
        tier="hotrod",
        epochs=50,
        batch_size=64,
        fast_dev_run=True,
        a2_full=True,
    )
    assert custom.tier == "hotrod"
    assert custom.epochs == 50
    assert custom.batch_size == 64
    assert custom.a2_full is True

    # Negative epochs rejection
    with pytest.raises(ValidationError):
        NamTrainingConfig.model_validate({"epochs": 0})

    # Invalid tier rejection
    with pytest.raises(ValidationError):
        NamTrainingConfig.model_validate({"tier": "unsupported_tier"})


def test_artwork_pack_config_validation():
    """Verify ArtworkPackConfig hex color pattern and required metadata."""

    def dummy_renderer(accent: str) -> str:
        return f"<svg color='{accent}'></svg>"

    pack = ArtworkPackConfig(
        accent="#38bdf8",
        title="TEST PACK",
        desc_line1="Line 1",
        desc_line2="Line 2",
        scale="34in",
        badge2="STD",
        badge3="PASSIVE",
        content=dummy_renderer,
    )
    assert pack.accent == "#38bdf8"
    assert pack.content(pack.accent) == "<svg color='#38bdf8'></svg>"

    # Invalid hex color code pattern rejection
    with pytest.raises(ValidationError):
        ArtworkPackConfig(
            accent="not-a-hex",
            title="TEST",
            desc_line1="1",
            desc_line2="2",
            scale="34in",
            badge2="STD",
            badge3="PASSIVE",
            content=dummy_renderer,
        )


def test_tier_spec_validation_and_resolution():
    """Verify TierSpec fields, get_tier_spec resolution, alias normalization, and error handling."""
    tier = TierSpec(
        name="custom",
        folder_name="99_custom",
        prefix="cst_",
        description="Custom tier",
    )
    assert tier.name == "custom"
    assert tier.folder_name == "99_custom"
    assert tier.prefix == "cst_"

    # Resolves canonical tiers
    dyn = get_tier_spec("dynamic")
    assert dyn.folder_name == "00_dynamic"
    assert dyn.prefix == "dyn_"

    cln = get_tier_spec("clean")
    assert cln.folder_name == "01_studio_clean"
    assert cln.prefix == "cln_"

    std = get_tier_spec("standard")
    assert std.folder_name == "02_standard_dynamic"
    assert std.prefix == "std_"

    hot = get_tier_spec("hotrod")
    assert hot.folder_name == "03_hot_rod"
    assert hot.prefix == "hot_"

    # Resolves aliases
    assert get_tier_spec("dyn").prefix == "dyn_"
    assert get_tier_spec("std").prefix == "std_"

    # Default None resolves to dynamic
    assert get_tier_spec(None).name == "dynamic"

    # Reject unknown tier
    with pytest.raises(KeyError) as exc_info:
        get_tier_spec("unknown_tier")
    assert "Unknown tier 'unknown_tier'" in str(exc_info.value)
