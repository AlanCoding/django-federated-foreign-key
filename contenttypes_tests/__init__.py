from importlib import import_module
import sys

module = import_module('tests.contenttypes_tests')
# copy attributes
for attr in dir(module):
    if not attr.startswith('__'):
        globals()[attr] = getattr(module, attr)

# ensure submodules are available under contenttypes_tests
sys.modules[__name__] = module
default_app_config = 'tests.contenttypes_tests.apps.ContentTypesTestsConfig'
