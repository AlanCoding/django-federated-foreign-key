from django.db import models
from federated_foreign_key.fields import FederatedForeignKey
from federated_foreign_key.models import GenericContentType


class Book(models.Model):
    title = models.CharField(max_length=50)


class Reference(models.Model):
    content_type = models.ForeignKey(
        GenericContentType,
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveIntegerField()
    content_object = FederatedForeignKey("content_type", "object_id")
