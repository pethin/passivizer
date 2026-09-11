"""
Unit tests for Pydantic configuration schemas and validation behavior.
Ensures fail-fast declarative integrity (Guardrail 5.3.5) with extra="forbid",
type checking, dict subscripting, and bounds validation.
"""

import pytest
from pydantic import ValidationError

from allomorph.base import AllomorphBaseModel
from allomorph.circuit.schema import CircuitConfig
from allomorph.config.schema import (
    CoilConfig,
    InstrumentConfig,
    InstrumentStringsConfig,
    PickupConfig,
    PreampBandConfig,
    PreampConfig,
    ScaleConfig,
    StringPresetConfig,
    VoiceCoilConfig,
    VoiceConfig,
    VoicePickupConfig,
)


class SampleModel(AllomorphBaseModel):
    name: str
    value: float = 1.0


def test_allomorph_base_model_subscripting():
    """Verify dict-like behavior on AllomorphBaseModel for seamless interoperability."""
    m = SampleModel(name="test", value=42.0)

    # Subscript reading
    assert m["name"] == "test"
    assert m["value"] == 42.0
    assert m.get("name") == "test"
    assert m.get("missing", "default") == "default"
    assert "name" in m
    assert "missing" not in m

    # Keys, values, items, iter
    assert set(m.keys()) == {"name", "value"}
    assert "test" in list(m.values())
    assert ("name", "test") in list(m.items())
    assert dict(iter(m)) == {"name": "test", "value": 42.0}

    # Subscript mutation
    m["value"] = 100.0
    assert m.value == 100.0
    assert m["value"] == 100.0

    # Copy
    m_copy = m.model_copy()
    assert m_copy["value"] == 100.0

    # Key error on invalid key
    with pytest.raises(KeyError):
        _ = m["non_existent_field"]


def test_allomorph_base_model_extra_forbid():
    """Verify that unknown/unexpected keys are strictly rejected across all models."""
    with pytest.raises(ValidationError) as exc_info:
        SampleModel.model_validate({"name": "test", "unexpected_field": "illegal"})
    assert "extra_forbidden" in str(exc_info.value)


def test_scale_config_validation():
    """Verify ScaleConfig validation and bounds."""
    scale = ScaleConfig(
        name='34" Standard',
        scale_length_in=34.0,
        string_wave_speeds=[77.4, 103.4, 137.9, 184.2],
    )
    assert scale.scale_length_in == 34.0
    assert scale.scale_length_m == pytest.approx(34.0 * 0.0254)
    assert len(scale.speeds) == 4

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        ScaleConfig.model_validate(
            {
                "name": "Bad",
                "scale_length_in": 34.0,
                "string_wave_speeds": [77.4, 103.4, 137.9, 184.2],
                "bogus_key": 123,
            }
        )


def test_string_preset_config_validation():
    """Verify StringPresetConfig validation."""
    preset = StringPresetConfig(
        name="Standard Nickel Roundwound",
        type="roundwound",
        wrap="nickel",
        core="steel",
        tension_lbs=42.8,
        damping_cutoff_hz=1200.0,
        damping_order=1.5,
    )
    assert preset.wrap == "nickel"
    assert preset.core == "steel"
    assert preset.tension_lbs == 42.8

    # Disallow unexpected field
    with pytest.raises(ValidationError):
        StringPresetConfig.model_validate(
            {
                "name": "Bad",
                "type": "roundwound",
                "wrap": "nickel",
                "core": "steel",
                "tension_lbs": 42.8,
                "damping_cutoff_hz": 1200.0,
                "damping_order": 1.5,
                "extra_field": True,
            }
        )


def test_preamp_band_and_catalog_validation():
    """Verify PreampBandConfig and PreampConfig validation."""
    band = PreampBandConfig(
        type="low_shelf",
        freq_hz=40.0,
        gain_db=4.0,
        q=0.707,
    )
    assert band.type == "low_shelf"
    assert band.freq_hz == 40.0

    preamp = PreampConfig(
        name="Test Preamp",
        input_impedance_meg=1.0,
        output_impedance_ohm=100.0,
        bands=[band],
    )
    assert preamp.name == "Test Preamp"
    assert len(preamp.bands) == 1

    # Disallow invalid extra key in band
    with pytest.raises(ValidationError):
        PreampBandConfig.model_validate(
            {
                "type": "bell",
                "freq_hz": 800.0,
                "gain_db": 2.0,
                "unknown": "not_allowed",
            }
        )


def test_pickup_and_instrument_config_validation():
    """Verify CoilConfig, PickupConfig, and InstrumentConfig validation."""
    coil = CoilConfig(
        position_from_bridge_m=0.0775,
        aperture_width_in=0.75,
    )
    assert coil.position_from_bridge_m == 0.0775

    pickup = PickupConfig(
        name="Test Bridge Pickup",
        position_from_bridge_m=0.0775,
        aperture_width_in=0.90,
        coils=[coil],
    )
    assert pickup.name == "Test Bridge Pickup"
    assert len(pickup.coils) == 1

    inst = InstrumentConfig(
        id="test_bass",
        name="Test Bass",
        scale_length_in=34.0,
        scale_length_m=0.8636,
        string_wave_speeds=[77.4, 103.4, 137.9, 184.2],
        pickups={"bridge": pickup},
        default_pickup="bridge",
        strings=InstrumentStringsConfig(preset="roundwound_nickel_standard"),
    )
    assert inst.id == "test_bass"
    assert inst.default_pickup == "bridge"
    assert "bridge" in inst.pickups

    # Extra field forbidden on InstrumentConfig
    with pytest.raises(ValidationError):
        InstrumentConfig.model_validate(
            {
                "id": "test_bass",
                "name": "Test Bass",
                "scale_length_in": 34.0,
                "scale_length_m": 0.8636,
                "string_wave_speeds": [77.4, 103.4, 137.9, 184.2],
                "pickups": {"bridge": pickup},
                "default_pickup": "bridge",
                "unregistered_custom_attr": "forbidden",
            }
        )


def test_voice_config_validation():
    """Verify VoiceConfig, VoicePickupConfig, and VoiceCoilConfig validation."""
    coil = VoiceCoilConfig(
        position_from_bridge_m=0.0635,
        aperture_width_in=0.75,
    )
    voice_pickup = VoicePickupConfig(
        name="Bridge Single",
        fr=3200.0,
        Q=1.6,
        coils=[coil],
    )
    voice = VoiceConfig(
        id="03_test_voice",
        name="Test Voice",
        topology="single",
        description="A test target voice",
        fr=3200.0,
        Q=1.6,
        circuit=CircuitConfig(topology="single", L=3.2, Rdc=8000.0, Reddy=150000.0),
        pickups=[voice_pickup],
    )
    assert voice.id == "03_test_voice"
    assert voice.circuit.L == 3.2
    assert voice.pickups is not None and len(voice.pickups) == 1

    # Extra field forbidden on VoiceConfig
    with pytest.raises(ValidationError):
        VoiceConfig.model_validate(
            {
                "id": "03_test_voice",
                "name": "Test Voice",
                "topology": "single",
                "description": "A test target voice",
                "fr": 3200.0,
                "Q": 1.6,
                "circuit": {"topology": "single", "L": 3.2, "Rdc": 8000.0, "Reddy": 150000.0},
                "pickups": [{"name": "Bridge Single", "fr": 3200.0, "Q": 1.6}],
                "extra_bad_arg": "bad",
            }
        )
