"""
Tests for Altair chart generation and portal HTML synthesis in allomorph.visualizer.
"""

import re
import tempfile
from pathlib import Path

import polars as pl

from allomorph.config import load_all_instruments
from allomorph.visualizer import (
    DOCS_DIR,
    RESPONSES_DIR,
    build_frontend_deconvolutions_dataframe,
    generate_all_charts,
    generate_frontend_deconvolutions_chart,
    generate_interactive_chart,
)


def test_generate_interactive_chart():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_html = Path(tmpdir) / "chart.html"
        generate_interactive_chart(instrument="30in", out_html=str(out_html))

        assert out_html.exists()
        content = out_html.read_text(encoding="utf-8")
        assert "vega" in content.lower()
        assert "Allomorph Master Voices" in content


def test_generate_all_charts():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        generated = generate_all_charts(output_dir=out_dir)

        all_insts = load_all_instruments()
        for inst_id in all_insts:
            if inst_id == "canonical_intermediate":
                continue
            assert inst_id in generated
            # Check unified signal flow chart
            chart_path = out_dir / f"{inst_id}.html"
            assert chart_path.exists()
            content = chart_path.read_text(encoding="utf-8")
            assert "vega" in content.lower()
            assert "Signal Flow" in content
            assert "1. Source Bass Input" in content
            assert "5. Target Voice Output" in content

        # Check Universal Targets and Frontend Deconvolutions master pages
        assert (out_dir / "universal_targets.html").exists()
        assert (out_dir / "frontend_deconvolutions.html").exists()
        for inst_id in all_insts:
            if inst_id == "canonical_intermediate":
                continue
            assert (out_dir / f"{inst_id}_frontend.html").exists()

        # Check index portal in output directory
        index_path = out_dir / "index.html"
        assert index_path.exists()
        portal_content = index_path.read_text(encoding="utf-8")
        assert "Allomorph Frequency Response Suite" in portal_content
        assert "tab-btn" in portal_content
        assert "iframe" in portal_content
        assert "pnav-targets" in portal_content
        assert "pnav-frontends" in portal_content
        assert "pnav-inspector" in portal_content
        for inst_id, inst_cfg in all_insts.items():
            if inst_id == "canonical_intermediate":
                continue
            assert inst_id in portal_content
            assert inst_cfg.name in portal_content


def test_generate_interactive_chart_modes():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Output mode
        p_out = Path(tmpdir) / "out.html"
        generate_interactive_chart(instrument="30in", out_html=str(p_out), mode="output")
        assert p_out.exists()
        assert "Output Voice Frequency Responses" in p_out.read_text(encoding="utf-8")

        # 2. Difference mode
        p_diff = Path(tmpdir) / "diff.html"
        generate_interactive_chart(instrument="30in", out_html=str(p_diff), mode="difference")
        assert p_diff.exists()
        assert "Input/Output Differential Transfer Functions" in p_diff.read_text(encoding="utf-8")

        # 3. Unified mode with radio selector
        p_unified = Path(tmpdir) / "unified.html"
        generate_interactive_chart(instrument="30in", out_html=str(p_unified), mode="unified")
        assert p_unified.exists()
        content = p_unified.read_text(encoding="utf-8")
        assert "Display Mode: " in content


def test_generate_frontend_deconvolutions_chart():
    df = build_frontend_deconvolutions_dataframe()
    assert isinstance(df, pl.DataFrame)
    assert "instrument_name" in df.columns
    assert "pickup_name" in df.columns
    assert "frequency" in df.columns
    assert "magnitude_db" in df.columns
    assert df.height > 0

    with tempfile.TemporaryDirectory() as tmpdir:
        out_html = Path(tmpdir) / "frontend_deconv.html"
        generate_frontend_deconvolutions_chart(target_path=out_html)
        assert out_html.exists()
        content = out_html.read_text(encoding="utf-8")
        assert "Frontend Deconvolutions" in content
        assert "inst-select" in content
        assert "pickup-sublevel" in content
        assert "vegaEmbed" in content


def test_portal_html_scripts_valid():
    """Verify that all script tags in generated portals have balanced braces and valid syntax."""
    portal_files = [
        DOCS_DIR / "frequency_responses.html",
        RESPONSES_DIR / "index.html",
        RESPONSES_DIR / "frontend_deconvolutions.html",
    ]
    for p in portal_files:
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        scripts = re.findall(
            r"<script(?:\s+type=\"text/javascript\")?>(.*?)</script>", content, re.DOTALL
        )
        for s in scripts:
            # Strip comments and string literals
            clean_s = re.sub(r"//.*", "", s)
            clean_s = re.sub(r"/\*.*?\*/", "", clean_s, flags=re.DOTALL)
            clean_s = re.sub(r"'(?:\\.|[^'])*'", "''", clean_s)
            clean_s = re.sub(r'"(?:\\.|[^"])*"', '""', clean_s)
            clean_s = re.sub(r"`(?:\\.|[^`])*`", "``", clean_s)

            stack = []
            matching = {")": "(", "}": "{", "]": "["}
            for char in clean_s:
                if char in "({[":
                    stack.append(char)
                elif char in ")}]":
                    assert stack, f"Unmatched closing '{char}' in {p.name}"
                    top = stack.pop()
                    assert top == matching[char], (
                        f"Mismatched '{char}' in {p.name}: expected {matching[char]}, got {top}"
                    )
            assert not stack, f"Unclosed brackets {stack} in {p.name}"
