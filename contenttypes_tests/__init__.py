from importlib import import_module
import sys
from pathlib import Path

try:
    module = import_module("tests.contenttypes_tests")
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))
    module = import_module("tests.contenttypes_tests")

# Copy attributes so that "from contenttypes_tests import X" works.
for attr in dir(module):
    if not attr.startswith("__"):
        globals()[attr] = getattr(module, attr)

# Ensure submodules are available under contenttypes_tests.
sys.modules[__name__] = module
default_app_config = "tests.contenttypes_tests.apps.ContentTypesTestsConfig"
