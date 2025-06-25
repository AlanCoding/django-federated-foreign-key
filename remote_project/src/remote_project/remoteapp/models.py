from django.db import models


class Book(models.Model):
    """Book model for remote project."""

    title = models.CharField(max_length=50)
