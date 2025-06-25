import os

SECRET_KEY = "test"
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "federated_foreign_key",
    "remote_project.remoteapp",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_NAME", ":memory:"),
    }
}
FEDERATION_PROJECT_NAME = "project_b"
ROOT_URLCONF = "remote_project.urls"
ALLOWED_HOSTS = ["*"]
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
