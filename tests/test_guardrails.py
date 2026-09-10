"""
Passivizer Architectural Guardrails Automated Invariant Test Suite.

Programmatically verifies that all core physical modeling and numerical invariants
specified in AGENTS.md and docs/architectural_guardrails.md are strictly upheld:
1. Active preamp finite DC transmission (H(0) >= 1.0) and Gibbs truncation ripple prevention
2. Mathematical identity flatness (exact 0.00 dB on matching source/target)
3. Small-signal linearity (bit-exact linear bypass for peak <= 0.10)
4. Quadrature regularization floor at comb nulls
5. Accelerated Numba JIT execution for recursive audio buffer loops
"""

import ast
import inspect
import math
import numpy as np
from pathlib import Path

from scripts.simulate_circuits import (
    compute_active_preamp_eq,
    compute_circuit_transfer_functions,
    compute_differential_circuit_transfer_functions,
    parse_netlist,
    simulate_circuit_audio,
    CIRCUITS_DIR,
    REPO_ROOT,
    FREQS,
)
from scripts.model_physics import load_instrument, VOICES
from scripts.analyze_voices import build_voice_dataframe


def test_guardrail_active_preamp_dc_transmission():
    """Guardrail 5.3.3: Active preamps must feature flat, finite DC transmission (H(0) >= 1.0)
    to prevent unphysical sub-audible inversion steps and Gibbs truncation ripples."""
    s_dc = 1j * 2.0 * math.pi * 1e-6  # Near DC

    for preamp_type in ["sadowsky_2band", "stingray_2band"]:
        H_eq = compute_active_preamp_eq(preamp_type, s_dc)
        mag_dc = abs(H_eq)
        assert mag_dc >= 1.0, (
            f"Preamp {preamp_type} DC magnitude was {mag_dc:.4f} (expected >= 1.0). "
            "Sub-audible highpass poles (s / (s + w_sub)) are strictly prohibited."
        )


def test_guardrail_zero_gibbs_ripples_in_differential_curves():
    """Guardrail 5.3.3: Differential frequency response curves between 20 Hz and 300 Hz
    must be smooth and monotonic without periodic Gibbs truncation ripple oscillations."""
    active_sources = ["34in_active_stingray", "34in_active_soapbar"]
    test_voices = ["02_jazz_bass_pair", "05_vintage_62_p_alnico"]

    for inst_id in active_sources:
        inst = load_instrument(inst_id)
        for voice_id in test_voices:
            df = build_voice_dataframe(voice_id, VOICES[voice_id], instrument=inst, mode="difference")
            sub_df = df.filter((df["frequency"] >= 20.0) & (df["frequency"] <= 300.0))
            mags = sub_df["magnitude_db"].to_numpy()

            # Numerical derivative (slope differences)
            diffs = np.diff(mags)
            # Count sign flips (extrema in 20-300 Hz)
            sign_flips = sum(
                1 for i in range(len(diffs) - 1)
                if (diffs[i] > 1e-4 and diffs[i + 1] < -1e-4) or (diffs[i] < -1e-4 and diffs[i + 1] > 1e-4)
            )

            assert sign_flips <= 1, (
                f"{inst_id} -> {voice_id} had {sign_flips} slope sign flips between 20 Hz and 300 Hz. "
                "Periodic Gibbs truncation ripples are present."
            )


def test_guardrail_identity_model_flatness():
    """Guardrail 5.3.1: Pairing an instrument with its matching target voice must evaluate
    to exact 0.00 dB identity across all frequency bins."""
    m_src_ray = parse_netlist(CIRCUITS_DIR / "sources" / "source_active_stingray.cir")
    m_tgt_ray = parse_netlist(CIRCUITS_DIR / "09_stingray_mm_parallel.cir")

    diff_ray = compute_differential_circuit_transfer_functions(m_tgt_ray, m_src_ray, freqs=FREQS)
    h_diff = np.asarray(diff_ray[0])

    assert np.all(h_diff == 1.0), "Matching active StingRay models must produce bit-exact 1.000 (0.00 dB)"


def test_guardrail_small_signal_linearity():
    """Guardrail 5.4.1: Audio signals with peak amplitude <= 0.10 must bypass saturation
    and non-linear drag bit-exact to preserve linear test fidelity."""
    from scripts.simulate_circuits import apply_oversampled_saturation

    sr = 48000
    n_samples = 2400
    # Small signal well within linear threshold (0.05 peak)
    small_sig = (0.05 * np.sin(2.0 * np.pi * 100.0 * np.arange(n_samples) / sr)).astype(np.float32)

    sat_out = apply_oversampled_saturation(
        small_sig,
        vsat=0.45,
        alpha=0.15,
        alpha3=0.08,
        eta_hyst=0.06,
        k_sag=0.25,
        k_eddy=0.15,
        k_pull=0.12,
        k_stein=0.03,
    )

    # On small signals, the saturation engine must return a bit-exact identical array
    assert np.array_equal(sat_out, small_sig), "Small signals (<= 0.10) must bypass saturation bit-exact"


def test_guardrail_quadrature_null_floor_bounded():
    """Guardrail 5.2.3: Multi-coil combining must incorporate the quadrature regularization floor
    so deep comb cancellation nulls never collapse to singular non-differentiable cusps."""
    from scripts.model_physics import numpy_pickup_macro_aperture

    inst = load_instrument("30in_emg_mmtw")
    src_pickup = inst["pickups"]["mmtw_dual"]
    speeds = inst["string_wave_speeds"]

    freqs = np.linspace(20.0, 15000.0, 1000)
    macro_env = numpy_pickup_macro_aperture(freqs, src_pickup["coils"], speeds)

    min_val = np.min(macro_env)
    # The quadrature floor (0.18^2) guarantees transmission never drops below ~0.03 (-30 dB)
    assert min_val > 0.02, f"Comb null dropped to {min_val:.5f} (< 0.02); quadrature floor is missing."


def test_guardrail_buffer_loop_acceleration():
    """Guardrail 6.1: Recursive ODE state solvers in scripts/simulate_circuits.py must be decorated
    with @njit to prevent interpreted Python loops over audio buffers."""
    sim_script = REPO_ROOT / "scripts" / "simulate_circuits.py"
    tree = ast.parse(sim_script.read_text())

    recursive_cores = ["_lenz_velocity_drag_core", "_dahl_core", "_slew_limit_core"]
    found_cores = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in recursive_cores:
            decorator_names = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorator_names.append(dec.id)
                elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                    decorator_names.append(dec.func.id)
            if node.name not in found_cores or "njit" in decorator_names:
                found_cores[node.name] = decorator_names

    for core_name in recursive_cores:
        assert core_name in found_cores, f"Expected {core_name} to exist in simulate_circuits.py"
        assert "njit" in found_cores[core_name], f"{core_name} is missing @njit fastmath acceleration"
