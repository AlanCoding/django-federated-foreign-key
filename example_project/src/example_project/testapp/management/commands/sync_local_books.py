from django.core.management.base import BaseCommand

from example_project.testapp.models import Book, Reference
from federated_foreign_key.models import GenericContentType


class Command(BaseCommand):
    """Create ``Reference`` entries for local books."""

    help = "Create Reference objects for existing local Book entries"

    def handle(self, **options):
        ct = GenericContentType.objects.get_for_model(Book)
        for book in Book.objects.all():
            Reference.objects.get_or_create(
                content_type=ct,
                object_id=book.pk,
            )
