SECRET_KEY = 'test'
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'federated_foreign_key',
    'example_project.testapp',
    'contenttypes_tests',
    'empty_models',
    'no_models',
    'django.contrib.sites',
]
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
    'other': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}
FEDERATION_PROJECT_NAME = 'project_a'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
