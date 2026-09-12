"""
Allomorph Architectural Guardrails Automated Invariant Test Suite.

Programmatically verifies that all core physical modeling and numerical invariants
specified in AGENTS.md and docs/architectural_guardrails.md are strictly upheld:
1. Active preamp finite DC transmission (H(0) >= 1.0) and Gibbs truncation ripple prevention
2. Mathematical identity flatness (exact 0.00 dB on matching source/target)
3. Small-signal linearity (bit-exact linear bypass for peak <= 0.10)
4. Quadrature regularization floor at comb nulls
5. Accelerated Numba JIT execution for recursive audio buffer loops
6. First-class transducer taxonomy ('magnetic', 'bridge_force', 'direct') and zero-conditional deconvolution
"""

import ast
import math

import numpy as np

from allomorph.circuit import (
    REPO_ROOT,
    compute_active_preamp_eq,
    compute_differential_circuit_transfer_functions,
    load_circuit,
)
from allomorph.config import VOICES, load_instrument
from allomorph.dsp import FREQS, read_wav
from allomorph.visualizer import build_voice_dataframe


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
    active_sources = ["34in_active_stingray", "34in_preamp_soapbar", "34in_emg_soapbar"]
    test_voices = ["02_jazz_bass_pair", "05_vintage_62_p_alnico"]

    for inst_id in active_sources:
        inst = load_instrument(inst_id)
        for voice_id in test_voices:
            df = build_voice_dataframe(
                voice_id, VOICES[voice_id], instrument=inst, mode="difference"
            )
            sub_df = df.filter((df["frequency"] >= 20.0) & (df["frequency"] <= 300.0))
            mags = sub_df["magnitude_db"].to_numpy()

            # Numerical derivative (slope differences)
            diffs = np.diff(mags)
            # Count sign flips (extrema in 20-300 Hz)
            sign_flips = sum(
                1
                for i in range(len(diffs) - 1)
                if (diffs[i] > 1e-4 and diffs[i + 1] < -1e-4)
                or (diffs[i] < -1e-4 and diffs[i + 1] > 1e-4)
            )

            assert sign_flips <= 1, (
                f"{inst_id} -> {voice_id} had {sign_flips} slope sign flips between 20 Hz and 300 Hz. "
                "Periodic Gibbs truncation ripples are present."
            )


def test_guardrail_zero_high_frequency_gibbs_ripples():
    """Guardrail 5.1.2: Multi-pickup spatial arrival delays must use causal integer sample shifting
    rather than circular FFT phase rotations to prevent high-frequency (8-20 kHz) Gibbs truncation ripples."""
    active_sources = [
        "34in_active_stingray",
        "30in_emg_mmtw",
        "34in_preamp_soapbar",
        "34in_emg_soapbar",
    ]
    test_voices = ["01_modern_jazz_active", "07_modern_pj_active", "02_jazz_bass_pair"]

    for inst_id in active_sources:
        inst = load_instrument(inst_id)
        for voice_id in test_voices:
            df = build_voice_dataframe(
                voice_id, VOICES[voice_id], instrument=inst, mode="difference"
            )
            sub_df = df.filter((df["frequency"] >= 8000.0) & (df["frequency"] <= 20000.0))
            mags = sub_df["magnitude_db"].to_numpy()

            diffs = np.diff(mags)
            sign_flips = sum(
                1
                for i in range(len(diffs) - 1)
                if (diffs[i] > 1e-4 and diffs[i + 1] < -1e-4)
                or (diffs[i] < -1e-4 and diffs[i + 1] > 1e-4)
            )

            assert sign_flips <= 1, (
                f"{inst_id} -> {voice_id} had {sign_flips} slope sign flips between 8 kHz and 20 kHz. "
                "Periodic Gibbs truncation ripples are present in high frequencies."
            )


def test_guardrail_identity_model_flatness():
    """Guardrail 5.3.1: Pairing an instrument with its matching target voice must evaluate
    to exact 0.00 dB identity across all frequency bins."""
    inst_ray = load_instrument("34in_active_stingray")
    ray_circ = inst_ray.pickups["mm_parallel"].circuit
    assert ray_circ is not None
    m_src_ray = load_circuit(ray_circ)
    m_tgt_ray = load_circuit(VOICES["09_stingray_mm_parallel"].circuit)

    diff_ray = compute_differential_circuit_transfer_functions(m_tgt_ray, m_src_ray, freqs=FREQS)
    h_diff = np.asarray(diff_ray[0])

    assert np.all(h_diff == 1.0), (
        "Matching active StingRay models must produce bit-exact 1.000 (0.00 dB)"
    )


def test_guardrail_small_signal_linearity():
    """Guardrail 5.4.1: Audio signals with peak amplitude <= 0.10 must bypass saturation
    and non-linear drag bit-exact to preserve linear test fidelity."""
    from allomorph.circuit import apply_oversampled_saturation

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
    assert np.array_equal(sat_out, small_sig), (
        "Small signals (<= 0.10) must bypass saturation bit-exact"
    )


def test_guardrail_quadrature_null_floor_bounded():
    """Guardrail 5.2.3: Multi-coil combining must incorporate the quadrature regularization floor
    so deep comb cancellation nulls never collapse to singular non-differentiable cusps."""
    from allomorph.physics import numpy_pickup_macro_aperture

    inst = load_instrument("30in_emg_mmtw")
    src_pickup = inst.pickups["mmtw_dual"]
    speeds = inst.string_wave_speeds

    freqs = np.linspace(20.0, 15000.0, 1000)
    macro_env = numpy_pickup_macro_aperture(freqs, src_pickup.coils, speeds)

    min_val = np.min(macro_env)
    # The quadrature floor (0.18^2) guarantees transmission never drops below ~0.03 (-30 dB)
    assert min_val > 0.02, (
        f"Comb null dropped to {min_val:.5f} (< 0.02); quadrature floor is missing."
    )


def test_guardrail_buffer_loop_acceleration():
    """Guardrail 6.1: Recursive ODE state solvers in saturation.py must be decorated
    with @njit to prevent interpreted Python loops over audio buffers."""
    sim_script = REPO_ROOT / "src" / "allomorph" / "circuit" / "saturation.py"
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
        assert core_name in found_cores, f"Expected {core_name} to exist in {sim_script.name}"
        assert "njit" in found_cores[core_name], (
            f"{core_name} is missing @njit fastmath acceleration"
        )


def test_guardrail_transducer_taxonomy_and_zero_conditional_deconvolution():
    """Guardrail 5.3.4: Transducers must be modeled via first-class physical taxonomy
    ('magnetic', 'bridge_force', 'direct') with zero ad-hoc voice ID conditionals."""
    # 1. Verify all registered voices declare a recognized physical sensor_type
    valid_sensors = {"magnetic", "bridge_force", "direct"}
    for vid, cfg in VOICES.items():
        sensor = cfg.sensor_type
        assert sensor in valid_sensors, f"Voice {vid} has invalid sensor_type: '{sensor}'"

    # 2. AST check: physics module must contain zero hardcoded voice ID conditionals in FIR synthesis
    phys_file = REPO_ROOT / "src" / "allomorph" / "physics" / "prefilter.py"
    tree = ast.parse(phys_file.read_text())

    prohibited_constants = {
        "15_source_direct",
        "15_neutral_character",
        "15b_active_character",
        "15c_passive_character",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "compute_voice_prefilter_firs":
            for sub_node in ast.walk(node):
                if (
                    isinstance(sub_node, ast.Constant)
                    and isinstance(sub_node.value, str)
                    and sub_node.value in prohibited_constants
                ):
                    raise AssertionError(
                        f"Found prohibited hardcoded voice ID '{sub_node.value}' inside compute_voice_prefilter_firs. "
                        "All acoustic filtering must be governed by first-class physical parameters (e.g. sensor_type)."
                    )

    # 3. Direct sensor target output mode must evaluate to bit-exact 0.00 dB
    vcfg = VOICES["15_neutral_character"]
    df_out = build_voice_dataframe(
        "15_neutral_character", vcfg, instrument="canonical_intermediate", mode="output"
    )
    mags_out = df_out["magnitude_db"].to_numpy()
    assert np.all(mags_out == 0.0), (
        f"15_neutral_character output mode was not bit-exact 0.00 dB (max error: {np.max(np.abs(mags_out))})"
    )

    # 4. Character Voicings preserve aperture (unit impulse)
    from allomorph.physics import compute_voice_prefilter_firs

    firs = compute_voice_prefilter_firs("15_neutral_character", instrument="canonical_intermediate")
    assert len(firs) == 1
    fir = np.array(firs[0])
    assert fir[0] == 1.0
    assert np.all(fir[1:] == 0.0)

    # 5. Direct sensor deconvolution without preserve_aperture must smoothly invert aperture sinc
    test_direct_cfg = vcfg.model_copy(update={"preserve_aperture": False})
    VOICES["_test_direct_deconv"] = test_direct_cfg
    try:
        firs_dir = compute_voice_prefilter_firs(
            "_test_direct_deconv", instrument="canonical_intermediate"
        )
        assert len(firs_dir) == 1
        fir_dir = np.array(firs_dir[0])

        f_bins = np.fft.rfftfreq(8192, 1.0 / 48000.0)
        H = np.abs(np.fft.rfft(fir_dir, 8192))
        gain_5k = H[np.argmin(np.abs(f_bins - 5000))] / H[np.argmin(np.abs(f_bins - 20))]
        assert 1.2 <= gain_5k <= 2.5, f"Expected 1.2 <= gain_5k <= 2.5, got {gain_5k:.3f}"

        # Verify monotonic smooth inversion in 20 Hz to 5000 Hz passband (zero sign flips)
        mask = (f_bins >= 20.0) & (f_bins <= 5000.0)
        H_band = H[mask]
        diffs = np.diff(H_band)
        sign_flips = sum(
            1
            for i in range(len(diffs) - 1)
            if (diffs[i] > 1e-5 and diffs[i + 1] < -1e-5)
            or (diffs[i] < -1e-5 and diffs[i + 1] > 1e-5)
        )
        assert sign_flips == 0, (
            f"Deconvolution curve had {sign_flips} sign flips in 20-5000 Hz band (must be smoothly monotonic)"
        )
    finally:
        del VOICES["_test_direct_deconv"]


def test_guardrail_fail_fast_zero_silent_fallbacks():
    """Guardrail 5.3.5: Missing configuration models, invalid scale names, unknown pickups,
    unknown string presets, or unrecognized magnet types must immediately raise explicit
    ValueError or KeyError exceptions instead of silently applying default fallbacks."""
    import pytest

    from allomorph.circuit import simulate_voice
    from allomorph.circuit.parser import CircuitModel
    from allomorph.circuit.solver import apply_magnet_properties_to_model
    from allomorph.config.scales import resolve_scale_range
    from allomorph.config.schema import InstrumentConfig, InstrumentStringsConfig, PickupConfig
    from allomorph.config.strings import get_instrument_string

    # 1. Passive instrument with missing pickup circuit must raise ValueError
    dummy_passive = InstrumentConfig(
        id="mock_passive_bass",
        name="Mock Passive Bass",
        electronics="passive",
        default_pickup="p",
        pickups={
            "p": PickupConfig(
                name="Passive P",
                position_from_bridge_m=0.125,
                aperture_width_in=0.75,
                coil_spacing_in=0.0,
                magnet_type="alnico_v",
            )
        },
        string_wave_speeds=[73.4, 98.0, 130.8, 174.6],
        scale_length_in=34.0,
    )
    with pytest.raises(ValueError, match="does not define a '\\[circuit\\]' block"):
        simulate_voice("04_modern_p_ceramic", instrument=dummy_passive, max_samples=100)

    # 2. Unknown target voice ID must raise KeyError
    with pytest.raises(KeyError, match="Target voice 'nonexistent_voice' not found"):
        simulate_voice("nonexistent_voice")

    # 3. Unknown scale string must raise ValueError
    with pytest.raises(ValueError, match="Unknown scale or instrument identifier"):
        resolve_scale_range("99in_fictional_scale")

    # 4. Unknown string preset must raise KeyError
    with pytest.raises(KeyError, match="String preset 'imaginary_flats' not found"):
        get_instrument_string(
            InstrumentConfig(strings=InstrumentStringsConfig(preset="imaginary_flats"))
        )

    # 5. Unknown magnet type must raise KeyError
    with pytest.raises(KeyError, match="Unknown magnet type 'kryptonite'"):
        apply_magnet_properties_to_model(
            CircuitModel(), PickupConfig(name="mock", magnet_type="kryptonite")
        )


def test_guardrail_visualizer_vectorization_and_performance():
    """Guardrail 6.4 (Commit 7c6e634): build_composite_instrument_dataframe must be vectorized
    and execute in < 150 ms per instrument with step=3 downsampling, without redundant multi-rate FFTs."""
    import time

    from allomorph.config import load_instrument
    from allomorph.visualizer import build_composite_instrument_dataframe

    # 1. Bounded execution latency: building composite dataframe must take < 100 ms warm
    # (after global get_cached_target_dfs is primed)
    inst = load_instrument("34in_standard_p")
    build_composite_instrument_dataframe(inst, step=3)

    t0 = time.perf_counter()
    df = build_composite_instrument_dataframe(inst, step=3)
    duration_ms = (time.perf_counter() - t0) * 1000.0

    assert duration_ms < 100.0, (
        f"build_composite_instrument_dataframe took {duration_ms:.2f} ms (budget: < 100 ms). "
        "Iterative build_voice_dataframe(mode='difference') calls inside per-pickup loops are prohibited."
    )

    # 2. Downsampling invariant: Exactly 200 points per curve (600 // 3)
    freqs = df["frequency"].unique().to_list()
    assert len(freqs) == 200, f"Expected 200 downsampled frequency points, found {len(freqs)}"

    # 3. Payload rounding invariant: Decibel magnitudes must be rounded to at most 2 decimal places
    mags = df["magnitude_db"].to_list()
    for m in mags:
        assert round(m, 2) == m, f"Unrounded float {m} violates payload compression guardrail"


def test_guardrail_visualizer_signal_flow_inspector_fidelity():
    """Guardrail 3.7.1 & 5.3.6: The visualizer's Signal Flow Inspector must strictly replicate
    the authentic two-stage IR + NAM DSP pipeline:
      Stage 1: Source Baseline (0 dB)
      Stage 2: Block 1 Frontend IR (matches actual exported FIR from export_frontend_ir)
      Stage 3: Block 2 Target Voicing (universal target transfer function)
      Stage 4: Resulting Output (exact 0.00 dB for matching identity, Stage 2 + Stage 3 = Stage 4)"""
    import tempfile
    from pathlib import Path

    import numpy as np

    from allomorph.circuit.staging import export_frontend_ir
    from allomorph.config import load_instrument
    from allomorph.visualizer import build_composite_instrument_dataframe

    # 1. Physical IR Equivalence: Visualizer Block 1 must match export_frontend_ir FIR
    with tempfile.TemporaryDirectory() as tmpdir:
        ir_path = export_frontend_ir("34in_standard_p", "split_p", output_dir=Path(tmpdir))
        fir, _ = read_wav(ir_path, dtype=np.float64)

    n_fft = 8192
    h_ir = np.fft.rfft(fir, n_fft)
    f_bins = np.fft.rfftfreq(n_fft, 1.0 / 48000.0)
    mag_ir_db = 20.0 * np.log10(np.maximum(np.abs(h_ir), 1e-6))
    mag_ir_norm = mag_ir_db - mag_ir_db[0]

    inst = load_instrument("34in_standard_p")
    df = build_composite_instrument_dataframe(inst, step=1)
    s2 = df.filter(df["stage"] == "2. Block 1 Deconvolution")
    f_vis = s2["frequency"].to_numpy()
    mag_vis_db = s2["magnitude_db"].to_numpy()
    mag_vis_norm = mag_vis_db - mag_vis_db[0]

    mag_ir_interp = np.interp(f_vis, f_bins, mag_ir_norm)
    err = np.abs(mag_vis_norm - mag_ir_interp)
    assert np.max(err) < 0.5, (
        f"Visualizer Block 1 Deconvolution deviated by {np.max(err):.2f} dB from actual export_frontend_ir FIR. "
        "Visualizer must strictly match the real pipeline deconvolution."
    )

    # 2. Wiener Noise Regularization: Clamping must be strictly bounded (no +24 dB ultrasonic rise)
    assert np.max(mag_vis_db) <= 8.0, (
        f"Block 1 Deconvolution peak boost was {np.max(mag_vis_db):.2f} dB (must be <= +8.0 dB)"
    )
    assert mag_vis_db[-1] < 2.0, (
        f"Block 1 Deconvolution at 20 kHz was {mag_vis_db[-1]:.2f} dB (unbounded HF rise prohibited)"
    )

    # 3. Canonical Intermediate Neutralization: Stage 1 + Stage 2 = Stage 3 (0.00 dB)
    s1 = df.filter(df["stage"] == "1. Source Bass Input")
    s3 = df.filter(df["stage"] == "3. Canonical Intermediate (0 dB)")

    assert len(s3) > 0
    assert (s3["magnitude_db"] == 0.0).all(), "Canonical Intermediate baseline was not flat 0.00 dB"
    assert np.allclose(s1["magnitude_db"].to_numpy() + s2["magnitude_db"].to_numpy(), 0.0), (
        "Source Bass Input and Block 1 Deconvolution did not neutralize to flat Canonical Intermediate"
    )

    # 4. Canonical Intermediate Voicing: Stage 3 (0 dB) + Stage 4 = Stage 5 bit-exact
    s4_all = df.filter(df["stage"] == "4. Block 2 Target Voicing")
    s5_all = df.filter(df["stage"] == "5. Target Voice Output")
    assert len(s4_all) > 0
    assert len(s5_all) > 0
    for vname in df["voice_name"].unique().to_list():
        if not vname:
            continue
        m4 = s4_all.filter(s4_all["voice_name"] == vname)["magnitude_db"].to_numpy()
        m5 = s5_all.filter(s5_all["voice_name"] == vname)["magnitude_db"].to_numpy()
        assert np.allclose(m4, m5, atol=0.01), (
            f"Stage 3 (0 dB) + Stage 4 did not equal Stage 5 for voice '{vname}'"
        )

    # 5. Strict Stage Sequence Invariant
    stages = df["stage"].unique().to_list()
    expected_sequence = {
        "1. Source Bass Input",
        "2. Block 1 Deconvolution",
        "3. Canonical Intermediate (0 dB)",
        "4. Block 2 Target Voicing",
        "5. Target Voice Output",
    }
    assert set(stages) == expected_sequence, (
        f"Visualizer stages {stages} deviated from expected five-stage pipeline {expected_sequence}"
    )


def test_guardrail_visualizer_frontend_deconvolutions_fidelity():
    """Guardrail 3.7.2 & 5.3.6: Frontend Deconvolution visualizer curves
    (build_instrument_frontend_dataframe and build_frontend_deconvolutions_dataframe) must
    strictly match the actual 2048-tap minimum-phase FIR from export_frontend_ir within < 0.5 dB
    across 20 Hz to 20 kHz with bounded Wiener regularization and finite DC transmission."""
    import tempfile
    from pathlib import Path

    import numpy as np

    from allomorph.circuit.staging import export_frontend_ir
    from allomorph.config import load_all_instruments, load_instrument
    from allomorph.visualizer.dataframe import (
        build_frontend_deconvolutions_dataframe,
        build_instrument_frontend_dataframe,
    )

    # 1. Multi-Instrument FIR Equivalence: passive split-P, passive Jazz bridge, active EMG MMTW
    test_cases = [
        ("34in_standard_p", "split_p"),
        ("34in_standard_jazz", "bridge"),
        ("30in_emg_mmtw", "mmtw_dual"),
    ]

    for inst_id, pkey in test_cases:
        with tempfile.TemporaryDirectory() as tmpdir:
            ir_path = export_frontend_ir(inst_id, pkey, output_dir=Path(tmpdir))
            fir, _ = read_wav(ir_path, dtype=np.float64)

        n_fft = 8192
        h_ir = np.fft.rfft(fir, n_fft)
        f_bins = np.fft.rfftfreq(n_fft, 1.0 / 48000.0)
        mag_ir_db = 20.0 * np.log10(np.maximum(np.abs(h_ir), 1e-6))
        mag_ir_norm = mag_ir_db - mag_ir_db[0]

        inst = load_instrument(inst_id)
        df_inst = build_instrument_frontend_dataframe(inst)
        pdf = df_inst.filter(df_inst["pickup_key"] == pkey)
        f_vis = pdf["frequency"].to_numpy()
        mag_vis_db = pdf["magnitude_db"].to_numpy()
        mag_vis_norm = mag_vis_db - mag_vis_db[0]

        mag_ir_interp = np.interp(f_vis, f_bins, mag_ir_norm)
        err = np.abs(mag_vis_norm - mag_ir_interp)

        # Deviation must be strictly < 0.5 dB
        assert np.max(err) < 0.5, (
            f"build_instrument_frontend_dataframe for {inst_id} ({pkey}) deviated by "
            f"{np.max(err):.2f} dB from actual export_frontend_ir FIR (limit: < 0.5 dB)."
        )

        # Wiener noise regularization must be bounded (<= +8.0 dB boost, < +2.0 dB at 20 kHz)
        assert np.max(mag_vis_db) <= 8.0, (
            f"{inst_id} ({pkey}) peak frontend boost was {np.max(mag_vis_db):.2f} dB (limit: <= +8.0 dB)"
        )
        assert mag_vis_db[-1] < 2.0, (
            f"{inst_id} ({pkey}) at 20 kHz was {mag_vis_db[-1]:.2f} dB (unbounded HF rise prohibited)"
        )

        # Sub-audible DC transmission must be finite and bounded within [-12 dB, +12 dB]
        assert -12.0 <= mag_vis_db[0] <= 12.0, (
            f"{inst_id} ({pkey}) 20 Hz DC magnitude was {mag_vis_db[0]:.2f} dB (violates Guardrail 3.3)"
        )

    # 2. Master Catalog Consistency: build_frontend_deconvolutions_dataframe must match
    # build_instrument_frontend_dataframe bit-exact across all playable instruments
    all_df = build_frontend_deconvolutions_dataframe()
    all_insts = load_all_instruments()

    for inst_id, inst in all_insts.items():
        if inst_id == "canonical_intermediate":
            continue
        inst_df = build_instrument_frontend_dataframe(inst)
        sub_all = all_df.filter(all_df["instrument_id"] == inst_id)
        assert len(inst_df) == len(sub_all), (
            f"{inst_id} row count mismatch between master and single-instrument dataframes"
        )
        m1 = inst_df["magnitude_db"].to_numpy()
        m2 = sub_all["magnitude_db"].to_numpy()
        assert np.allclose(m1, m2, atol=1e-5), (
            f"{inst_id} frontend deconvolution curves differed between master and single dataframes"
        )


def test_guardrail_visualizer_universal_target_voicings_fidelity():
    """Guardrail 3.7.3 & 5.3.6: Universal Target Voicings (build_universal_targets_dataframe)
    must encompass all 22 target voices relative to Canonical Intermediate baseline,
    maintain physical electroacoustic bounds (< +25 dB boost, > -100 dB attenuation),
    and strictly match Stage 4 target curves in the Signal Flow Inspector."""
    import numpy as np

    from allomorph.config import VOICES, load_instrument
    from allomorph.visualizer.dataframe import (
        build_composite_instrument_dataframe,
        build_universal_targets_dataframe,
    )

    df_targets = build_universal_targets_dataframe()

    # 1. Catalog Completeness: Exactly 22 target voices (all voices except 00_canonical_intermediate)
    expected_vids = set(VOICES.keys()) - {"00_canonical_intermediate"}
    found_vids = set(df_targets["voice_id"].unique().to_list())
    assert found_vids == expected_vids, (
        f"Missing target voices in universal_targets: {expected_vids - found_vids}"
    )

    # 2. Non-null and Finite Invariant
    assert not df_targets["magnitude_db"].is_nan().any(), "NaN found in universal target magnitudes"
    assert not df_targets["magnitude_db"].is_null().any(), (
        "Null found in universal target magnitudes"
    )

    # 3. Physical Electroacoustic Boundedness
    for vid in expected_vids:
        vdf = df_targets.filter(df_targets["voice_id"] == vid)
        assert len(vdf) == 600, f"Target voice {vid} had {len(vdf)} points (expected 600)"
        m = vdf["magnitude_db"].to_numpy()
        max_boost = float(np.max(m))
        min_atten = float(np.min(m))
        assert max_boost < 25.0, (
            f"Target voice {vid} had unphysical peak boost {max_boost:.2f} dB (limit: < +25.0 dB)"
        )
        assert min_atten > -100.0, (
            f"Target voice {vid} had excessive attenuation {min_atten:.2f} dB (limit: > -100.0 dB)"
        )

    # 4. Consistency with Signal Flow Inspector Stage 3 for non-matching voices
    inst = load_instrument("34in_standard_p")
    df_comp = build_composite_instrument_dataframe(inst, step=1)

    vid = "09_stingray_mm_parallel"
    vname = VOICES[vid].name
    s4 = df_comp.filter(
        (df_comp["stage"] == "4. Block 2 Target Voicing") & (df_comp["voice_name"] == vname)
    )
    vtgt = df_targets.filter(df_targets["voice_id"] == vid)

    m_s4 = s4["magnitude_db"].to_numpy()
    m_tgt = vtgt["magnitude_db"].to_numpy()
    max_diff = float(np.max(np.abs(m_s4 - m_tgt)))
    assert max_diff < 0.01, (
        f"Stage 4 Target Voicing for {vid} differed from universal target dataframe by {max_diff:.4f} dB"
    )
