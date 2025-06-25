import os

SECRET_KEY = "test"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "federated_foreign_key",
    "example_project.testapp",
    "django.contrib.sites",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_NAME", ":memory:"),
    }
}
FEDERATION_PROJECT_NAME = "project_a"
FEDERATED_REMOTE_OBJECT_CLASS = "example_project.remote.RemoteBook"
ROOT_URLCONF = "example_project.urls"
ALLOWED_HOSTS = ["*"]
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
