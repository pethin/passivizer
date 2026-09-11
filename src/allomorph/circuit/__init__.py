"""
Allomorph Circuit Simulation Engine
Analytical closed-form nodal RLC solver and state-space non-linear saturation.
"""

from allomorph.circuit.parser import (
    parse_spice_val,
    MAGNET_PROPERTIES,
    CircuitModel,
    eval_pot_taper,
    load_circuit,
    parse_netlist,
)
from allomorph.circuit.solver import (
    compute_core_impedance,
    apply_magnet_properties_to_model,
    compute_active_preamp_eq,
    compute_circuit_transfer_functions,
    compute_differential_circuit_transfer_functions,
)
from allomorph.circuit.saturation import (
    _HAS_NUMBA,
    _dahl_core,
    _lenz_envelope_core,
    _lenz_velocity_drag_core,
    _slew_limit_core,
    apply_dahl_hysteresis,
    apply_elliptical_orbit_projection,
    apply_oversampled_saturation,
)
from allomorph.dsp import FREQS
from allomorph.physics import (
    compute_voice_prefilter_firs,
    compute_aperture_prefilter_fir,
)
from allomorph.circuit.audio import (
    apply_prefilter_to_audio,
    prefilter_audio,
    find_default_input_audio,
)
from allomorph.circuit.simulation import (
    REPO_ROOT,
    AUDIO_DIR,
    MODELS_DIR,
    CANONICAL_SWEEP_PATH,
    FRONTENDS_DIR,
    TARGETS_DIR,
    INTERMEDIATE_TARGET_PEAK_DBFS,
    INTERMEDIATE_TARGET_RMS_DBFS,
    simulate_circuit_audio,
    simulate_voice,
    _simulate_voice_task,
)
from allomorph.circuit.staging import (
    generate_canonical_sweep,
    export_frontend_ir,
    export_all_frontend_irs,
    simulate_backend_targets,
    main,
)
from allomorph.circuit.sweeps import (
    ParametricSweepResult,
    compute_parametric_sweep,
)

__all__ = [
    "ParametricSweepResult",
    "compute_parametric_sweep",
    "parse_spice_val",
    "MAGNET_PROPERTIES",
    "CircuitModel",
    "eval_pot_taper",
    "load_circuit",
    "parse_netlist",
    "compute_core_impedance",
    "apply_magnet_properties_to_model",
    "compute_active_preamp_eq",
    "compute_circuit_transfer_functions",
    "compute_differential_circuit_transfer_functions",
    "_HAS_NUMBA",
    "_dahl_core",
    "_lenz_envelope_core",
    "_lenz_velocity_drag_core",
    "_slew_limit_core",
    "apply_dahl_hysteresis",
    "apply_elliptical_orbit_projection",
    "apply_oversampled_saturation",
    "REPO_ROOT",
    "AUDIO_DIR",
    "MODELS_DIR",
    "CANONICAL_SWEEP_PATH",
    "FRONTENDS_DIR",
    "TARGETS_DIR",
    "INTERMEDIATE_TARGET_PEAK_DBFS",
    "INTERMEDIATE_TARGET_RMS_DBFS",
    "apply_prefilter_to_audio",
    "prefilter_audio",
    "simulate_circuit_audio",
    "find_default_input_audio",
    "simulate_voice",
    "_simulate_voice_task",
    "generate_canonical_sweep",
    "export_frontend_ir",
    "export_all_frontend_irs",
    "simulate_backend_targets",
    "main",
]
