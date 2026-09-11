"""
Unit tests for circuit schemas (RLC parameters, potentiometer controls, dynamic metallurgy, simulation).
"""

import numpy as np
import pytest
from pydantic import ValidationError

from allomorph.base import parse_spice_unit
from allomorph.circuit.parser import CircuitModel
from allomorph.circuit.schema import (
    CircuitBranchConfig,
    CircuitConfig,
    CircuitMetricsRecord,
    HarnessControls,
    MagnetPropertiesConfig,
    SaturationConfig,
    SimulationConfig,
)
from allomorph.circuit.sweeps import ParametricSweepResult
from allomorph.config.schema import PreampBandConfig


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


def test_spice_float_validation():
    """Verify SpiceFloat engineering notation parsing on CircuitConfig."""
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
            curves=curves[:2],
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


def test_simulation_config_validation_and_kwargs():
    """Verify SimulationConfig validation, harness controls embedding, and to_sim_kwargs conversion."""
    harness = HarnessControls(vol_pos=0.8, tone_pos=0.5, blend_pos=0.5, pot_taper="audio")
    sat = SaturationConfig(vsat=0.45, alpha=0.12, oversample=4)

    sim_cfg = SimulationConfig(
        normalize="rms",
        target_dbfs=-14.0,
        oversample=4,
        harness_controls=harness,
        saturation_config=sat,
    )
    assert sim_cfg.normalize == "rms"
    assert sim_cfg.target_dbfs == -14.0

    kwargs = sim_cfg.to_sim_kwargs()
    assert isinstance(kwargs, dict)
    assert kwargs["normalize"] == "rms"
    assert kwargs["vol_pos"] == 0.8
    assert kwargs["vsat"] == 0.45
    assert kwargs["oversample"] == 4

    # Rejection of invalid normalize mode
    with pytest.raises(ValidationError):
        SimulationConfig(normalize="invalid_mode")  # type: ignore[arg-type]


def test_circuit_model_validation():
    """Verify CircuitModel Pydantic v2 validation, defaults, SPICE parsing, and copy behaviors."""
    model = CircuitModel()
    assert model.topology == "single"
    assert model.L == 4.8
    assert model.Rdc == 9500.0
    assert model.vol_pos == 1.0
    assert model.tone_pos == 1.0

    # Test engineering notation string parsing via from_dict
    custom = CircuitModel.from_dict({
        "topology": "single",
        "L": "3.4H",
        "Rdc": "10.5k",
        "Reddy": "180k",
        "Ccoil": "60pF",
        "Rvol": "250k",
        "Ctone": "47nF",
        "vol_pos": 0.7,
        "preamp_bands": [
            {"type": "low_shelf", "freq_hz": 40.0, "gain_db": 12.0, "q": 0.707},
            {"type": "high_shelf", "freq_hz": 4000.0, "gain_db": -6.0, "q": 0.707},
        ],
    })
    assert custom.L == 3.4
    assert custom.Rdc == 10500.0
    assert custom.Reddy == 180000.0
    assert custom.Ccoil == pytest.approx(60e-12)
    assert custom.Rbot_default == 250000.0
    assert custom.Ctone == pytest.approx(47e-9)
    assert custom.vol_pos == 0.7
    assert custom.preamp_bands is not None
    assert len(custom.preamp_bands) == 2
    assert isinstance(custom.preamp_bands[0], PreampBandConfig)
    assert custom.preamp_bands[0].gain_db == 12.0

    # Pot position bounds validation
    with pytest.raises(ValidationError):
        CircuitModel(vol_pos=1.5)

    with pytest.raises(ValidationError):
        CircuitModel(tone_pos=-0.2)

    # Topology validation
    with pytest.raises(ValidationError):
        CircuitModel(topology="invalid_topology")  # type: ignore[arg-type]

    # Non-positive inductance validation
    with pytest.raises(ValidationError):
        CircuitModel(L=0.0)

    # apply_pot_positions method
    adjusted = custom.model_copy()
    adjusted.apply_pot_positions(vol_pos=0.5, tone_pos=0.2)
    assert adjusted.vol_pos == 0.5
    assert adjusted.tone_pos == 0.2
    assert custom.vol_pos == 0.7  # Original unchanged


def test_circuit_metrics_record_validation():
    """Verify CircuitMetricsRecord schema validation, fields, and dict export."""
    rec = CircuitMetricsRecord(
        param="vol_pos",
        param_value=0.5,
        label="Volume 50%",
        f_res_hz=3250.5,
        peak_db=4.2,
        insertion_loss_db=-0.8,
        peak_boost_db=5.0,
        q_loaded=1.85,
        bandwidth_hz=1757.0,
        cutoff_3db_hz=4500.0,
        hf_slope_db_oct=-12.0,
    )
    assert rec.param == "vol_pos"
    assert rec.param_value == 0.5
    assert rec.f_res_hz == 3250.5

    data = rec.model_dump()
    assert data["label"] == "Volume 50%"
    assert data["q_loaded"] == 1.85

    # Rejection of missing required fields
    with pytest.raises(ValidationError):
        CircuitMetricsRecord.model_validate({
            "param": "vol_pos",
        })

