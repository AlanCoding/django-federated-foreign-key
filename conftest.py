import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "example_project" / "src"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_project.settings")
