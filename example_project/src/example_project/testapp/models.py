from django.db import models
from federated_foreign_key.fields import FederatedForeignKey, FederatedRelation
from federated_foreign_key.models import GenericContentType


class Book(models.Model):
    """Sample model used for tests."""

    title = models.CharField(max_length=50)
    references = FederatedRelation("Reference", related_query_name="book")


class Reference(models.Model):
    """Model holding a federated relation to any object."""

    content_type = models.ForeignKey(
        GenericContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveIntegerField()
    content_object = FederatedForeignKey("content_type", "object_id")
