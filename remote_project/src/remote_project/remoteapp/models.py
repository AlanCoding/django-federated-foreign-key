from django.db import models
from django.utils.translation import gettext_lazy as _


class Book(models.Model):
    """Book model for remote project."""

    title = models.CharField(
        max_length=50,
        help_text=_("Title stored in the remote project's database."),
    )
