import os
import sys
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TEST_ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "example_project" / "src"))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "example_project.settings",
)
