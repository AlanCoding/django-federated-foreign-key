"""
Tests for the order_with_respect_to Meta attribute.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Question(models.Model):
    text = models.CharField(
        max_length=200,
        help_text=_("The actual question being asked."),
    )


class Answer(models.Model):
    text = models.CharField(
        max_length=200,
        help_text=_("Answer text shown for the question."),
    )
    question = models.ForeignKey(
        Question,
        models.CASCADE,
        help_text=_("Question this answer belongs to."),
    )

    class Meta:
        order_with_respect_to = "question"

    def __str__(self):
        return self.text


class Post(models.Model):
    title = models.CharField(
        max_length=200,
        help_text=_("Displayed title for the post."),
    )
    parent = models.ForeignKey(
        "self",
        models.SET_NULL,
        related_name="children",
        null=True,
        help_text=_("Parent post in the hierarchy."),
    )

    class Meta:
        order_with_respect_to = "parent"

    def __str__(self):
        return self.title


# order_with_respect_to points to a model with a OneToOneField primary key.
class Entity(models.Model):
    pass


class Dimension(models.Model):
    entity = models.OneToOneField(
        "Entity",
        primary_key=True,
        on_delete=models.CASCADE,
        help_text=_("Entity that this dimension extends."),
    )


class Component(models.Model):
    dimension = models.ForeignKey(
        "Dimension",
        on_delete=models.CASCADE,
        help_text=_("Dimension that this component refers to."),
    )

    class Meta:
        order_with_respect_to = "dimension"
