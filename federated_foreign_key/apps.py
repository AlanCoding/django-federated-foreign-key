from django.apps import AppConfig
from django.db.models.signals import post_migrate

from .management import create_generic_contenttypes


class FederatedForeignKeyConfig(AppConfig):
    """Register signals to create ``GenericContentType`` objects."""

    name = "federated_foreign_key"
    verbose_name = "Federated Foreign Key"

    def ready(self):
        post_migrate.connect(create_generic_contenttypes)
