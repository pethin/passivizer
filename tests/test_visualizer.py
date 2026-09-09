import tempfile
from pathlib import Path
import polars as pl
from scripts.model_physics import VOICES
from scripts.analyze_voices import build_voice_dataframe, generate_interactive_chart

def test_build_voice_dataframe():
    voice_id = "01_jazz_bass_pair"
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

def test_generate_interactive_chart():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_html = Path(tmpdir) / "chart.html"
        generate_interactive_chart(instrument="30in", out_html=str(out_html))
        
        assert out_html.exists()
        content = out_html.read_text(encoding="utf-8")
        assert "vega" in content.lower()
        assert "Passivizer Master Voices" in content

def test_circuit_simulation_integration():
    """Verify that build_voice_dataframe accurately incorporates the exact .cir netlist transfer functions."""
    # 1. 47nF tone capacitor rolloff on P-Bass
    df_tone = build_voice_dataframe("05_p_bass_47nf_rolloff", VOICES["05_p_bass_47nf_rolloff"], src_scale="30in")
    df_p = build_voice_dataframe("03_modern_p_ceramic", VOICES["03_modern_p_ceramic"], src_scale="30in")

    mag_tone_5k = df_tone.filter(pl.col("frequency") > 4500.0)["magnitude_db"].to_list()[0]
    mag_p_5k = df_p.filter(pl.col("frequency") > 4500.0)["magnitude_db"].to_list()[0]

    # Tone rolled off circuit should have substantially more high frequency attenuation (>20 dB deeper cut)
    assert mag_tone_5k < mag_p_5k - 20.0

    # 2. Rickenbacker 4.7nF series HPF low-end cut
    df_rick = build_voice_dataframe("08_rickenbacker_bridge_hpf", VOICES["08_rickenbacker_bridge_hpf"], src_scale="30in")
    mag_rick_low = df_rick.filter(pl.col("frequency") < 50.0)["magnitude_db"].to_list()[0]
    mag_rick_mid = df_rick.filter((pl.col("frequency") > 800.0) & (pl.col("frequency") < 1200.0))["magnitude_db"].to_list()[0]
    # Series cap introduces strong low-end shelf
    assert mag_rick_low < mag_rick_mid - 10.0

    # 3. Verify all voices produce finite, non-null values across all frequencies
    for vid, cfg in VOICES.items():
        vdf = build_voice_dataframe(vid, cfg, src_scale="30in")
        assert not vdf["magnitude_db"].is_nan().any()
        assert not vdf["magnitude_db"].is_null().any()

def test_generate_all_charts():
    from scripts.analyze_voices import generate_all_charts, load_all_instruments
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        generated = generate_all_charts(output_dir=out_dir)

        all_insts = load_all_instruments()
        for inst_id in all_insts.keys():
            assert inst_id in generated
            chart_path = out_dir / f"{inst_id}.html"
            assert chart_path.exists()
            content = chart_path.read_text(encoding="utf-8")
            assert "vega" in content.lower()

        # Check index portal in output directory
        index_path = out_dir / "index.html"
        assert index_path.exists()
        portal_content = index_path.read_text(encoding="utf-8")
        assert "Passivizer Frequency Response Suite" in portal_content
        assert "tab-btn" in portal_content
        assert "iframe" in portal_content
        for inst_id, inst_cfg in all_insts.items():
            assert inst_id in portal_content
            assert inst_cfg.get("name", inst_id) in portal_content


