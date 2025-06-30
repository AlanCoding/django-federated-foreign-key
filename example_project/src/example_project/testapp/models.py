from django.db import models
from django.utils.translation import gettext_lazy as _
from federated_foreign_key.fields import FederatedForeignKey, FederatedRelation
from federated_foreign_key.models import GenericContentType


class Book(models.Model):
    """Sample model used for tests."""

    title = models.CharField(
        max_length=50,
        help_text=_("Title of the book used in demo data."),
    )
    references = FederatedRelation(
        "Reference",
        related_query_name="book",
        help_text=_("References to objects in any project."),
    )


class Reference(models.Model):
    """Model holding a federated relation to any object."""

    content_type = models.ForeignKey(
        GenericContentType,
        on_delete=models.CASCADE,
        help_text=_("Type of the referenced object."),
    )
    object_id = models.PositiveIntegerField(
        help_text=_("Identifier of the referenced object."),
    )
    content_object = FederatedForeignKey("content_type", "object_id")
