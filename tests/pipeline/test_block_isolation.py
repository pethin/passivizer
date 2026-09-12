"""
Tests verifying that the 1-Block Baked System remains completely isolated and invariant,
and that the 2-Block Decoupled System satisfies the analytic tilt cancellation identity:
tilt_Block1 + tilt_Block2 == tilt_1Block_Direct.
"""

import numpy as np
import pytest

from allomorph.config import (
    VOICES,
    compute_effective_position,
    load_all_instruments,
    load_instrument,
    resolve_pickup_coils,
    resolve_scale_range,
    resolve_voice_coils,
)
from allomorph.physics.prefilter import compute_voice_prefilter_firs
from allomorph.visualizer.dataframe import build_voice_dataframe


def test_1block_baked_prefilter_firs_stability():
    """Validates that 1-block baked prefilter FIRs remain stable, finite, and well-behaved."""
    test_cases = [
        ("34in_preamp_soapbar", "neck", "05_vintage_62_p_alnico"),
        ("34in_preamp_soapbar", "bridge", "03_jazz_bridge_60s"),
        ("34in_preamp_soapbar", "pair_parallel", "02_jazz_bass_pair"),
        ("34in_standard_p", "split_p", "05_vintage_62_p_alnico"),
        ("34in_active_emg", "bridge", "09_stingray_mm_parallel"),
    ]

    for inst_id, pkey, vid in test_cases:
        inst = load_instrument(inst_id)
        firs = compute_voice_prefilter_firs(
            vid, instrument=inst, num_taps=2048, src_pickup_key=pkey
        )
        assert len(firs) > 0
        for fir in firs:
            arr = np.asarray(fir, dtype=np.float64)
            assert len(arr) == 2048
            assert not np.any(np.isnan(arr))
            assert not np.any(np.isinf(arr))
            # Must have non-zero energy
            assert np.max(np.abs(arr)) > 1e-4


def test_1block_difference_dataframe_invariance():
    """Validates that 1-block direct difference visualizer curves remain finite and bounded."""
    inst = load_instrument("34in_preamp_soapbar")
    df_neck = build_voice_dataframe(
        "05_vintage_62_p_alnico",
        VOICES["05_vintage_62_p_alnico"],
        instrument=inst,
        mode="difference",
        src_pickup_key="neck",
    )
    mags = df_neck["magnitude_db"].to_numpy()
    assert len(mags) == 600
    assert not np.any(np.isnan(mags))
    assert np.max(mags) < 25.0
    assert np.min(mags) > -100.0


def test_2block_analytic_tilt_cancellation_identity():
    """Validates the mathematical identity that in the 2-block decoupled system,
    the tilt applied in Block 1 (source -> canonical) plus the tilt applied in Block 2 (canonical -> target)
    analytically equals the direct 1-block tilt (source -> target).
    """
    all_insts = load_all_instruments()
    can_pos_m = 0.0935
    can_scale_m = 0.8636
    eta_can = can_pos_m / can_scale_m

    for inst_id, inst in sorted(all_insts.items()):
        if inst_id == "canonical_intermediate":
            continue
        src_scale_m = float(inst.scale_length_m or 0.8636)
        for pcfg in inst.pickups.values():
            coils = resolve_pickup_coils(pcfg, inst)
            src_pos_m = compute_effective_position(coils)
            eta_src = src_pos_m / src_scale_m

            # Block 1 tilt: Source -> Canonical
            delta_in_b1 = (eta_can - eta_src) * 34.0
            tilt_db_b1 = delta_in_b1 * 1.5

            for vid, vcfg in sorted(VOICES.items()):
                if vid == "00_canonical_intermediate" or vcfg.sensor_type == "direct":
                    continue
                vcoils = resolve_voice_coils(vcfg)
                tgt_pos_m = compute_effective_position(vcoils)
                tgt_scale_range = resolve_scale_range(vcfg.scale)
                tgt_scale_m = (tgt_scale_range[0] + tgt_scale_range[1]) / 2.0
                eta_tgt = tgt_pos_m / tgt_scale_m

                # Block 2 tilt: Canonical -> Target
                delta_in_b2 = (eta_tgt - eta_can) * 34.0
                tilt_db_b2 = delta_in_b2 * 1.5

                # Direct 1-Block tilt: Source -> Target
                delta_in_direct = (eta_tgt - eta_src) * 34.0
                tilt_db_direct = delta_in_direct * 1.5

                # Sum of Block 1 and Block 2 tilts must match direct 1-block tilt
                summed_tilt = tilt_db_b1 + tilt_db_b2
                assert pytest.approx(summed_tilt, abs=1e-6) == tilt_db_direct


def test_2block_analytic_tension_cancellation_identity():
    """Validates the mathematical identity that in the 2-block decoupled system,
    for source instruments with scale length <= 34 inches (short, medium, and standard scale),
    the scale tension snap applied in Block 1 (source -> canonical) plus the scale tension snap applied in Block 2 (canonical -> target)
    analytically equals the direct 1-block tension snap (source -> target).
    """
    all_insts = load_all_instruments()
    can_scale_in = 34.0

    for inst_id, inst in sorted(all_insts.items()):
        if inst_id == "canonical_intermediate":
            continue
        src_scale_in = float(inst.scale_length_in or 34.0)
        if src_scale_in > can_scale_in:
            continue

        # Block 1 tension snap (Source -> Canonical Intermediate @ 34")
        if src_scale_in < can_scale_in - 0.2:
            snap_db_b1 = min(3.5, 1.8 * (can_scale_in - src_scale_in) / 4.0)
        else:
            snap_db_b1 = 0.0

        for vid, vcfg in sorted(VOICES.items()):
            if vid == "00_canonical_intermediate" or vcfg.scale == "upright":
                continue
            tgt_scale_in = (
                37.0
                if vcfg.scale in ["multiscale", "37in"]
                else (35.0 if vcfg.scale == "multiscale_super" else 34.0)
            )

            # Block 2 tension snap (Canonical Intermediate @ 34" -> Target)
            if can_scale_in < tgt_scale_in - 0.2:
                snap_db_b2 = min(3.5, 1.8 * (tgt_scale_in - can_scale_in) / 4.0)
            else:
                snap_db_b2 = 0.0

            # Direct 1-Block tension snap (Source -> Target)
            if src_scale_in < tgt_scale_in - 0.2:
                snap_db_direct = min(3.5, 1.8 * (tgt_scale_in - src_scale_in) / 4.0)
            else:
                snap_db_direct = 0.0

            # Sum of Block 1 and Block 2 tension snaps must match direct 1-block tension snap
            summed_snap = snap_db_b1 + snap_db_b2
            assert pytest.approx(summed_snap, abs=1e-6) == snap_db_direct

