from pkgutil import extend_path
from pathlib import Path

__path__ = extend_path(__path__, __name__)
# Include the source folder so that `example_project.settings` can be imported
_src_pkg = Path(__file__).resolve().parent / 'src' / 'example_project'
if str(_src_pkg) not in __path__:
    __path__.append(str(_src_pkg))
