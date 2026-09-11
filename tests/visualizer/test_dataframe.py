"""
Tests for Polars-based frequency response dataframe generation in allomorph.visualizer.
"""

import polars as pl

from allomorph.config import VOICES, load_all_instruments, load_instrument
from allomorph.visualizer import (
    build_composite_instrument_dataframe,
    build_frontend_deconvolutions_dataframe,
    build_instrument_frontend_dataframe,
    build_universal_targets_dataframe,
    build_voice_dataframe,
)


def test_build_voice_dataframe():
    voice_id = "01_modern_jazz_active"
    cfg = VOICES[voice_id]
    df = build_voice_dataframe(voice_id, cfg, src_scale="30in")

    assert isinstance(df, pl.DataFrame)
    assert set(df.columns) == {
        "frequency",
        "magnitude_db",
        "voice_id",
        "voice_name",
        "topology",
        "description",
    }
    assert df.height == 600

    # Check frequency range
    freqs = df["frequency"].to_list()
    assert freqs[0] >= 20.0
    assert freqs[-1] <= 20000.0

    # Magnitude should be in reasonable dB range (e.g. -35 dB to +15 dB)
    mags = df["magnitude_db"].to_list()
    assert all(-50.0 <= m <= 20.0 for m in mags)


def test_circuit_simulation_integration():
    """Verify that build_voice_dataframe accurately incorporates the exact circuit transfer functions."""
    # 1. 47nF tone capacitor rolloff on P-Bass
    df_tone = build_voice_dataframe(
        "05c_vintage_62_p_47nf", VOICES["05c_vintage_62_p_47nf"], src_scale="30in"
    )
    df_p = build_voice_dataframe(
        "04_modern_p_ceramic", VOICES["04_modern_p_ceramic"], src_scale="30in"
    )

    mag_tone_5k = df_tone.filter(pl.col("frequency") > 4500.0)["magnitude_db"].to_list()[0]
    mag_p_5k = df_p.filter(pl.col("frequency") > 4500.0)["magnitude_db"].to_list()[0]

    # Tone rolled off circuit should have substantially more high frequency attenuation (>20 dB deeper cut)
    assert mag_tone_5k < mag_p_5k - 20.0

    # 2. Rickenbacker 4.7nF series HPF low-end cut
    df_rick = build_voice_dataframe(
        "10_rickenbacker_bridge_hpf", VOICES["10_rickenbacker_bridge_hpf"], src_scale="30in"
    )
    mag_rick_low = df_rick.filter(pl.col("frequency") < 50.0)["magnitude_db"].to_list()[0]
    mag_rick_mid = df_rick.filter((pl.col("frequency") > 800.0) & (pl.col("frequency") < 1200.0))[
        "magnitude_db"
    ].to_list()[0]
    # Series cap introduces strong low-end shelf
    assert mag_rick_low < mag_rick_mid - 10.0

    # 3. Verify all voices produce finite, non-null values across all frequencies
    for vid, cfg in VOICES.items():
        vdf = build_voice_dataframe(vid, cfg, src_scale="30in")
        assert not vdf["magnitude_db"].is_nan().any()
        assert not vdf["magnitude_db"].is_null().any()


def test_build_composite_instrument_dataframe():
    inst = load_instrument("30in")
    df = build_composite_instrument_dataframe(inst)
    assert isinstance(df, pl.DataFrame)
    assert "frequency" in df.columns
    assert "magnitude_db" in df.columns
    assert "stage" in df.columns
    assert "voice_name" in df.columns
    assert "pickup_name" in df.columns
    stages = set(df["stage"].unique().to_list())
    expected_stages = {
        "1. Source Bass Input",
        "2. Block 1 Deconvolution",
        "3. Canonical Intermediate (0 dB)",
        "4. Block 2 Target Voicing",
        "5. Target Voice Output",
    }
    assert stages == expected_stages
    assert not df["magnitude_db"].is_nan().any()


def test_build_composite_instrument_dataframe_matching_identity():
    inst = load_instrument("34in_standard_jazz")
    df = build_composite_instrument_dataframe(inst)

    # 1. Source Bass Input + Block 1 Deconvolution must neutralize into Canonical Intermediate (bit-exact 0.00 dB)
    s1 = df.filter(
        (df["stage"] == "1. Source Bass Input")
        & (df["pickup_name"] == "Jazz Neck + Bridge Parallel")
    )
    s2 = df.filter(
        (df["stage"] == "2. Block 1 Deconvolution")
        & (df["pickup_name"] == "Jazz Neck + Bridge Parallel")
    )
    assert len(s1) > 0
    assert len(s1) == len(s2)
    sum_curves = [
        round(a + b, 2)
        for a, b in zip(s1["magnitude_db"].to_list(), s2["magnitude_db"].to_list(), strict=False)
    ]
    assert all(val == 0.0 for val in sum_curves)

    # 2. Stage 3 (Canonical Intermediate) must be flat 0.00 dB baseline datum
    s3 = df.filter(
        (df["stage"] == "3. Canonical Intermediate (0 dB)")
        & (df["pickup_name"] == "Jazz Neck + Bridge Parallel")
    )
    assert (s3["magnitude_db"] == 0.0).all()

    # 3. Verify P-Bass deconvolution: Block 1 is regularized and strictly bounded (no unbounded HF boost)
    inst_p = load_instrument("34in_standard_p")
    df_p = build_composite_instrument_dataframe(inst_p)
    p_s1 = df_p.filter(df_p["stage"] == "1. Source Bass Input")
    p_s2 = df_p.filter(df_p["stage"] == "2. Block 1 Deconvolution")
    p_s2_mags = p_s2["magnitude_db"].to_list()
    assert max(p_s2_mags) <= 8.0
    assert min(p_s2_mags) > -5.0

    # Source Bass Input + Block 1 Deconvolution must sum to exact 0.00 dB
    p_sum = [
        round(a + b, 2) for a, b in zip(p_s1["magnitude_db"].to_list(), p_s2_mags, strict=False)
    ]
    assert all(val == 0.0 for val in p_sum)


def test_build_voice_dataframe_output_mode():
    voice_id = "01_modern_jazz_active"
    cfg = VOICES[voice_id]
    df = build_voice_dataframe(voice_id, cfg, src_scale="30in", mode="output")
    assert isinstance(df, pl.DataFrame)
    assert set(df.columns) == {
        "frequency",
        "magnitude_db",
        "voice_id",
        "voice_name",
        "topology",
        "description",
    }
    assert df.height == 600

    mags = df["magnitude_db"].to_list()
    assert all(-50.0 <= m <= 20.0 for m in mags)

    # Test with include_mode_col=True
    df_mode = build_voice_dataframe(
        voice_id, cfg, src_scale="30in", mode="output", include_mode_col=True
    )
    assert "mode" in df_mode.columns
    assert (df_mode["mode"] == "Output Voice").all()


def test_build_universal_targets_dataframe():
    df = build_universal_targets_dataframe()
    assert isinstance(df, pl.DataFrame)
    expected_cols = {
        "frequency",
        "magnitude_db",
        "voice_id",
        "voice_name",
        "topology",
        "fr",
        "Q",
        "description",
    }
    assert set(df.columns) == expected_cols
    # 22 target voices * 600 points = 13200 rows
    assert df.height == 22 * 600
    assert not df["magnitude_db"].is_nan().any()
    assert not df["magnitude_db"].is_null().any()


def test_build_instrument_frontend_dataframe():
    inst = load_instrument("34in_standard_p")
    df = build_instrument_frontend_dataframe(inst)
    assert isinstance(df, pl.DataFrame)
    expected_cols = {
        "frequency",
        "magnitude_db",
        "instrument_id",
        "instrument_name",
        "pickup_key",
        "pickup_name",
        "scale_in",
        "position_mm",
    }
    assert set(df.columns) == expected_cols
    assert df.height == len(inst.pickups) * 600
    assert not df["magnitude_db"].is_nan().any()


def test_build_frontend_deconvolutions_dataframe():
    df = build_frontend_deconvolutions_dataframe()
    assert isinstance(df, pl.DataFrame)
    assert "label" in df.columns
    assert "instrument_id" in df.columns
    all_insts = load_all_instruments()
    expected_inst_ids = {k for k in all_insts if k != "canonical_intermediate"}
    assert set(df["instrument_id"].unique().to_list()) == expected_inst_ids
    assert not df["magnitude_db"].is_nan().any()
