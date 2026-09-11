"""
Unit tests for Pydantic configuration schemas and validation behavior.
Ensures fail-fast declarative integrity (Guardrail 5.3.5) with extra="forbid",
type checking, dict subscripting, and bounds validation.
"""

import pytest
from pydantic import ValidationError

from allomorph.config.schema import (
    AllomorphBaseModel,
    CircuitBranchConfig,
    CircuitConfig,
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
    m_copy = m.copy()
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
        ScaleConfig.model_validate({
            "name": "Bad",
            "scale_length_in": 34.0,
            "string_wave_speeds": [77.4, 103.4, 137.9, 184.2],
            "bogus_key": 123,
        })


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
        StringPresetConfig.model_validate({
            "name": "Bad",
            "type": "roundwound",
            "wrap": "nickel",
            "core": "steel",
            "tension_lbs": 42.8,
            "damping_cutoff_hz": 1200.0,
            "damping_order": 1.5,
            "extra_field": True,
        })


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
        PreampBandConfig.model_validate({
            "type": "bell",
            "freq_hz": 800.0,
            "gain_db": 2.0,
            "unknown": "not_allowed",
        })


def test_circuit_config_validation():
    """Verify CircuitConfig parameter types, defaults, and extra-key rejection."""
    circuit = CircuitConfig(
        topology="single",
        L=3.4,
        Rdc=10500.0,
        Reddy=180000.0,
        Ccoil=60e-12,
        Rvol=250000.0,
        Ctone=47e-9,
    )
    assert circuit.topology == "single"
    assert circuit.L == 3.4
    assert circuit.Rvol == 250000.0

    # Parallel circuit branch validation
    branch_neck = CircuitBranchConfig(L=3.0, Rdc=8000.0, Reddy=150000.0, Ccoil=50e-12)
    branch_bridge = CircuitBranchConfig(L=3.2, Rdc=8500.0, Reddy=160000.0, Ccoil=55e-12)
    par_circuit = CircuitConfig(
        topology="parallel",
        neck=branch_neck,
        bridge=branch_bridge,
    )
    assert par_circuit.neck is not None and par_circuit.neck.L == 3.0

    # Rejection of extra fields
    with pytest.raises(ValidationError):
        CircuitConfig.model_validate({
            "topology": "single",
            "L": 3.4,
            "Rdc": 10500.0,
            "bogus_circuit_parameter": 999,
        })


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
        InstrumentConfig.model_validate({
            "id": "test_bass",
            "name": "Test Bass",
            "scale_length_in": 34.0,
            "scale_length_m": 0.8636,
            "string_wave_speeds": [77.4, 103.4, 137.9, 184.2],
            "pickups": {"bridge": pickup},
            "default_pickup": "bridge",
            "unregistered_custom_attr": "forbidden",
        })


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
        VoiceConfig.model_validate({
            "id": "03_test_voice",
            "name": "Test Voice",
            "topology": "single",
            "description": "A test target voice",
            "fr": 3200.0,
            "Q": 1.6,
            "circuit": {"topology": "single", "L": 3.2, "Rdc": 8000.0, "Reddy": 150000.0},
            "pickups": [{"name": "Bridge Single", "fr": 3200.0, "Q": 1.6}],
            "extra_bad_arg": "bad",
        })


def test_spice_float_validation():
    """Verify SpiceFloat engineering notation parsing on CircuitConfig."""
    from allomorph.config.schema import parse_spice_unit

    assert parse_spice_unit("500k") == 500000.0
    assert parse_spice_unit("47nF") == pytest.approx(4.7e-8)
    assert parse_spice_unit("1.0Meg") == 1e6
    assert parse_spice_unit("750pF") == pytest.approx(7.5e-10)
    assert parse_spice_unit(100.0) == 100.0
    assert parse_spice_unit(None) is None

    # CircuitConfig accepts string engineering notation
    cfg = CircuitConfig.model_validate({
        "topology": "single",
        "L": "3.6H",
        "Rdc": "8.2k",
        "Reddy": "120k",
        "Ccoil": "80pF",
        "Rvol": "500k",
        "Ctone": "47nF",
        "Ccable": "750pF",
    })
    assert cfg.L == 3.6
    assert cfg.Rdc == 8200.0
    assert cfg.Reddy == 120000.0
    assert cfg.Ccoil == pytest.approx(8e-11)
    assert cfg.Rvol == 500000.0
    assert cfg.Ctone == pytest.approx(4.7e-8)
    assert cfg.Ccable == pytest.approx(7.5e-10)


def test_magnet_properties_config_and_diff():
    """Verify MagnetPropertiesConfig and differential calculation."""
    from allomorph.config.schema import MagnetPropertiesConfig

    alnico = MagnetPropertiesConfig(alpha=0.26, alpha3=0.10, k_sag=0.08, vsat=0.50)
    ceramic = MagnetPropertiesConfig(alpha=0.12, alpha3=0.04, k_sag=0.03, vsat=0.70)

    # Differential softening (alnico target vs ceramic source)
    diff = alnico.diff(ceramic)
    assert diff.alpha == pytest.approx(0.14)
    assert diff.alpha3 == pytest.approx(0.06)
    assert diff.k_sag == pytest.approx(0.05)
    assert diff.vsat == alnico.vsat

    # Reverse differential clamped to 0.0
    reverse_diff = ceramic.diff(alnico)
    assert reverse_diff.alpha == 0.0
    assert reverse_diff.alpha3 == 0.0
    assert reverse_diff.k_sag == 0.0


def test_harness_controls_validation():
    """Verify HarnessControls potentiometer wiper bounds and tapers."""
    from allomorph.config.schema import HarnessControls

    ctrl = HarnessControls(vol_pos=0.8, tone_pos=0.5, blend_pos=0.5, pot_taper="audio")
    assert ctrl.vol_pos == 0.8
    assert ctrl.tone_pos == 0.5
    assert ctrl.blend_pos == 0.5

    # Out of bounds wiper values raise ValidationError
    with pytest.raises(ValidationError):
        HarnessControls(vol_pos=1.5)

    with pytest.raises(ValidationError):
        HarnessControls(tone_pos=-0.1)

    with pytest.raises(ValidationError):
        HarnessControls(pot_taper="invalid_taper")  # type: ignore[arg-type]


def test_saturation_config_validation():
    """Verify SaturationConfig validation and parameters."""
    from allomorph.config.schema import SaturationConfig

    sat = SaturationConfig(vsat=0.60, alpha=0.25, oversample=4)
    assert sat.vsat == 0.60
    assert sat.alpha == 0.25
    assert sat.oversample == 4

    # Invalid oversample option
    with pytest.raises(ValidationError):
        SaturationConfig(oversample=3)  # type: ignore[arg-type]

    # Non-positive vsat
    with pytest.raises(ValidationError):
        SaturationConfig(vsat=0.0)


def test_parametric_sweep_result_validation():
    """Verify ParametricSweepResult dimensional array invariants."""
    import numpy as np

    from allomorph.circuit.sweeps import ParametricSweepResult

    freqs = np.array([100.0, 1000.0, 10000.0])
    values = [0.0, 0.5, 1.0]
    curves = [np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0]), np.array([2.0, 2.0, 2.0])]
    labels = ["0%", "50%", "100%"]

    res = ParametricSweepResult(
        param="vol_pos",
        values=values,
        freqs=freqs,
        curves=curves,
        labels=labels,
    )
    assert res.param == "vol_pos"
    assert len(res.curves_linear) == 3

    # Mismatched curve count
    with pytest.raises(ValidationError):
        ParametricSweepResult(
            param="vol_pos",
            values=values,
            freqs=freqs,
            curves=curves[:2],  # Only 2 curves for 3 values
            labels=labels,
        )

    # Mismatched frequency length on a curve
    with pytest.raises(ValidationError):
        ParametricSweepResult(
            param="vol_pos",
            values=values,
            freqs=freqs,
            curves=[np.array([0.0, 0.0]), np.array([1.0, 1.0, 1.0]), np.array([2.0, 2.0, 2.0])],
            labels=labels,
        )


def test_pipeline_cli_config_validation():
    """Verify PipelineCliConfig validation of command line options."""
    from allomorph.config.schema import PipelineCliConfig

    cfg = PipelineCliConfig(stage="targets", tier="standard", instrument="30in", cable_pf=750.0)
    assert cfg.stage == "targets"
    assert cfg.tier == "standard"
    assert cfg.instrument == "30in"

    with pytest.raises(ValidationError):
        PipelineCliConfig(stage="unsupported_stage")  # type: ignore[arg-type]


def test_tone3000_pack_listing_validation():
    """Verify Tone3000PackListing constraints on character counts and voicings."""
    from allomorph.config.schema import Tone3000PackListing

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
