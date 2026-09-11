"""
Tests for Polars-based frequency response dataframe generation in allomorph.visualizer.
"""

import polars as pl

from allomorph.config import VOICES, load_instrument
from allomorph.visualizer import (
    build_voice_dataframe,
    build_composite_instrument_dataframe,
)


def test_build_voice_dataframe():
    voice_id = "01_modern_jazz_active"
    cfg = VOICES[voice_id]
    df = build_voice_dataframe(voice_id, cfg, src_scale="30in")

    assert isinstance(df, pl.DataFrame)
    assert set(df.columns) == {"frequency", "magnitude_db", "voice_id", "voice_name", "topology", "description"}
    assert df.height == 600

    # Check frequency range
    freqs = df["frequency"].to_list()
    assert freqs[0] >= 20.0
    assert freqs[-1] <= 20000.0

    # Magnitude should be in reasonable dB range (e.g. -35 dB to +15 dB)
    mags = df["magnitude_db"].to_list()
    assert all(-50.0 <= m <= 20.0 for m in mags)


def test_circuit_simulation_integration():
    """Verify that build_voice_dataframe accurately incorporates the exact .cir netlist transfer functions."""
    # 1. 47nF tone capacitor rolloff on P-Bass
    df_tone = build_voice_dataframe("05c_vintage_62_p_47nf", VOICES["05c_vintage_62_p_47nf"], src_scale="30in")
    df_p = build_voice_dataframe("04_modern_p_ceramic", VOICES["04_modern_p_ceramic"], src_scale="30in")

    mag_tone_5k = df_tone.filter(pl.col("frequency") > 4500.0)["magnitude_db"].to_list()[0]
    mag_p_5k = df_p.filter(pl.col("frequency") > 4500.0)["magnitude_db"].to_list()[0]

    # Tone rolled off circuit should have substantially more high frequency attenuation (>20 dB deeper cut)
    assert mag_tone_5k < mag_p_5k - 20.0

    # 2. Rickenbacker 4.7nF series HPF low-end cut
    df_rick = build_voice_dataframe("10_rickenbacker_bridge_hpf", VOICES["10_rickenbacker_bridge_hpf"], src_scale="30in")
    mag_rick_low = df_rick.filter(pl.col("frequency") < 50.0)["magnitude_db"].to_list()[0]
    mag_rick_mid = df_rick.filter((pl.col("frequency") > 800.0) & (pl.col("frequency") < 1200.0))["magnitude_db"].to_list()[0]
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


def test_build_voice_dataframe_output_mode():
    voice_id = "01_modern_jazz_active"
    cfg = VOICES[voice_id]
    df = build_voice_dataframe(voice_id, cfg, src_scale="30in", mode="output")
    assert isinstance(df, pl.DataFrame)
    assert set(df.columns) == {"frequency", "magnitude_db", "voice_id", "voice_name", "topology", "description"}
    assert df.height == 600

    mags = df["magnitude_db"].to_list()
    assert all(-50.0 <= m <= 20.0 for m in mags)

    # Test with include_mode_col=True
    df_mode = build_voice_dataframe(voice_id, cfg, src_scale="30in", mode="output", include_mode_col=True)
    assert "mode" in df_mode.columns
    assert (df_mode["mode"] == "Output Voice").all()
