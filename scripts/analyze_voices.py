#!/usr/bin/env python3
"""
Allomorph - Interactive Visualizer & Frequency Analyzer CLI
Uses Polars and Altair to model, analyze, and render interactive frequency
response curves for all Master Voices across source bass instruments.

Delegates core logic to the library package allomorph.visualizer.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from allomorph.config import load_instrument, load_all_instruments
from allomorph.visualizer import (
    NUM_POINTS,
    F_MIN,
    F_MAX,
    log_freqs,
    build_voice_dataframe,
    compute_canonical_intermediate_response,
    build_universal_targets_dataframe,
    build_frontend_deconvolutions_dataframe,
    build_instrument_frontend_dataframe,
    build_composite_instrument_dataframe,
    DOCS_DIR,
    RESPONSES_DIR,
    append_spec_panel,
    format_instrument_meta,
    build_portal_html,
    generate_portal_pages,
    render_chart_to_file,
    generate_universal_targets_chart,
    generate_instrument_frontend_chart,
    generate_frontend_deconvolutions_chart,
    generate_composite_instrument_chart,
    generate_interactive_chart,
    generate_all_charts,
    main,
)

__all__ = [
    "NUM_POINTS",
    "F_MIN",
    "F_MAX",
    "log_freqs",
    "build_voice_dataframe",
    "compute_canonical_intermediate_response",
    "build_universal_targets_dataframe",
    "build_frontend_deconvolutions_dataframe",
    "build_instrument_frontend_dataframe",
    "build_composite_instrument_dataframe",
    "DOCS_DIR",
    "RESPONSES_DIR",
    "append_spec_panel",
    "format_instrument_meta",
    "build_portal_html",
    "generate_portal_pages",
    "render_chart_to_file",
    "generate_universal_targets_chart",
    "generate_instrument_frontend_chart",
    "generate_frontend_deconvolutions_chart",
    "generate_composite_instrument_chart",
    "generate_interactive_chart",
    "generate_all_charts",
    "load_instrument",
    "load_all_instruments",
    "main",
]

if __name__ == "__main__":
    main()
