import sys
from pathlib import Path

# Ensure scripts directory is importable
SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_pipeline import main

if __name__ == "__main__":
    main()

