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
        generate_interactive_chart(source_scale="30in", out_html=str(out_html))
        
        assert out_html.exists()
        content = out_html.read_text(encoding="utf-8")
        assert "vega" in content.lower()
        assert "Passivizer Master Voices" in content
