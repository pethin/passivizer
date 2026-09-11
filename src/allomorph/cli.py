"""
Allomorph - Command-Line Interface (CLI) Entrypoint
"""

from allomorph.pipeline import main as pipeline_main

def main(argv=None):
    """Main CLI entrypoint for the 'allomorph' command."""
    return pipeline_main(argv)

if __name__ == "__main__":
    main()
