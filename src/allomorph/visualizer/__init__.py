"""
Allomorph Visualizer Subpackage
Interactive Altair visualizations and Polars frequency response modeling.
"""

import argparse
from pathlib import Path

from allomorph.config import load_instrument
from allomorph.visualizer.dataframe import (
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
)
from allomorph.visualizer.portal import (
    DOCS_DIR,
    RESPONSES_DIR,
    append_spec_panel,
    format_instrument_meta,
    build_portal_html,
    generate_portal_pages,
)
from allomorph.visualizer.charts import (
    render_chart_to_file,
    generate_universal_targets_chart,
    generate_instrument_frontend_chart,
    generate_frontend_deconvolutions_chart,
    generate_composite_instrument_chart,
    generate_interactive_chart,
    generate_all_charts,
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
    "main",
]


def main(argv=None):
    """CLI entrypoint for interactive frequency response visualizer."""
    parser = argparse.ArgumentParser(description="Generate interactive Altair visualization of Allomorph voices.")
    parser.add_argument(
        "--instrument", "-i",
        default="all",
        help="Source instrument configuration (ID, alias like 30in, 32in, path to .toml, or 'all' to generate all)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["composite", "unified", "output", "difference", "targets", "frontends"],
        default="composite",
        help="Chart mode: 'composite' (3-curve overlay), 'unified', 'output', 'difference', 'targets', or 'frontends'"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build interactive charts for all configured instruments"
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output HTML file or directory path (default: docs/frequency_responses/<instrument_id>.html)"
    )
    args = parser.parse_args(argv)

    if args.all or (isinstance(args.instrument, str) and args.instrument.lower() == "all"):
        generate_all_charts(output_dir=args.out)
    else:
        inst = load_instrument(args.instrument)
        target_file = generate_interactive_chart(instrument=inst, out_html=args.out, mode=args.mode)
        if args.out is None or (Path(args.out).resolve() == RESPONSES_DIR.resolve()):
            generate_portal_pages(output_dir=RESPONSES_DIR, default_id=inst.get("id"))
