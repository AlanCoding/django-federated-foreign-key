SECRET_KEY = "test"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "federated_foreign_key",
    "example_project.testapp",
    "django.contrib.sites.models.Site",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
FEDERATION_PROJECT_NAME = "project_a"
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
