from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent
EXAMPLE_SRC = REPO_ROOT / "example_project" / "src"
if str(EXAMPLE_SRC) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_SRC))
