import json
from urllib.request import urlopen

from django.core.management.base import BaseCommand

from federated_foreign_key.models import GenericContentType
from example_project.testapp.models import Reference


class Command(BaseCommand):
    """Create ``Reference`` entries for remote books."""

    help = "Fetch remote books and create Reference objects if they do not exist"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default="http://localhost:8001/books/",
            help="URL of the remote book list",
        )
        parser.add_argument(
            "--project",
            default="project_b",
            help="Federation project name of the remote server",
        )
        parser.add_argument(
            "--app-label",
            default="remoteapp",
            help="App label of the remote model",
        )
        parser.add_argument(
            "--model",
            default="book",
            help="Model name of the remote model",
        )

    def handle(self, url, project, app_label, model, **options):
        with urlopen(url) as response:
            data = json.load(response)

        ct, _ = GenericContentType.objects.get_or_create(
            project=project,
            app_label=app_label,
            model=model,
        )

        for item in data:
            Reference.objects.get_or_create(
                content_type=ct,
                object_id=item["id"],
            )
