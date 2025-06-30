import uuid
from urllib.parse import quote

from federated_foreign_key.fields import FederatedRelation as GenericRelation
from federated_foreign_key.fields import FederatedForeignKey
from federated_foreign_key.models import GenericContentType
from django.contrib.sites.models import SiteManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class Site(models.Model):
    domain = models.CharField(
        max_length=100,
        help_text=_("Fully qualified domain name for the site."),
    )
    objects = SiteManager()


class Author(models.Model):
    name = models.CharField(
        max_length=100,
        help_text=_("Human readable name of the author."),
    )

    def get_absolute_url(self):
        return "/authors/%s/" % self.id


class Article(models.Model):
    title = models.CharField(
        max_length=100,
        help_text=_("Title displayed on the article page."),
    )
    slug = models.SlugField(
        help_text=_("URL slug used to build article links."),
    )
    author = models.ForeignKey(
        Author,
        models.CASCADE,
        help_text=_("Author that wrote the article."),
    )
    date_created = models.DateTimeField(
        help_text=_("Date and time when the article was created."),
    )


class SchemeIncludedURL(models.Model):
    url = models.URLField(
        max_length=100,
        help_text=_("URL including the scheme part."),
    )

    def get_absolute_url(self):
        return self.url


class ConcreteModel(models.Model):
    name = models.CharField(
        max_length=10,
        help_text=_("Simple name used in content type tests."),
    )


class ProxyModel(ConcreteModel):
    class Meta:
        proxy = True


class FooWithoutUrl(models.Model):
    """
    Fake model not defining ``get_absolute_url`` for
    ContentTypesTests.test_shortcut_view_without_get_absolute_url()
    """

    name = models.CharField(
        max_length=30,
        unique=True,
        help_text=_("Unique text used as a lookup key."),
    )


class FooWithUrl(FooWithoutUrl):
    """
    Fake model defining ``get_absolute_url`` for
    ContentTypesTests.test_shortcut_view().
    """

    def get_absolute_url(self):
        return "/users/%s/" % quote(self.name)


class FooWithBrokenAbsoluteUrl(FooWithoutUrl):
    """
    Fake model defining a ``get_absolute_url`` method containing an error
    """

    def get_absolute_url(self):
        return "/users/%s/" % self.unknown_field


class Question(models.Model):
    text = models.CharField(
        max_length=200,
        help_text=_("Question text presented to users."),
    )
    answer_set = GenericRelation(
        "Answer",
        help_text=_("Answers associated with this question."),
    )


class Answer(models.Model):
    text = models.CharField(
        max_length=200,
        help_text=_("Answer text for the question."),
    )
    content_type = models.ForeignKey(
        GenericContentType,
        models.CASCADE,
        help_text=_("Content type of the related object."),
    )
    object_id = models.PositiveIntegerField(
        help_text=_("ID of the related object."),
    )
    question = FederatedForeignKey()

    class Meta:
        order_with_respect_to = "question"


class Post(models.Model):
    """An ordered tag on an item."""

    title = models.CharField(
        max_length=200,
        help_text=_("Title for the post item."),
    )
    content_type = models.ForeignKey(
        GenericContentType,
        models.CASCADE,
        null=True,
        help_text=_("Type of the related object if any."),
    )
    object_id = models.PositiveIntegerField(
        null=True,
        help_text=_("ID of the related object if any."),
    )
    parent = FederatedForeignKey()
    children = GenericRelation(
        "Post",
        help_text=_("Child posts linked to this post."),
    )

    class Meta:
        order_with_respect_to = "parent"


class ModelWithNullFKToSite(models.Model):
    title = models.CharField(
        max_length=200,
        help_text=_("Descriptive title for the object."),
    )
    site = models.ForeignKey(
        Site,
        null=True,
        on_delete=models.CASCADE,
        help_text=_("Optional site owning this entry."),
    )
    post = models.ForeignKey(
        Post,
        null=True,
        on_delete=models.CASCADE,
        help_text=_("Optional post referenced by this entry."),
    )

    def get_absolute_url(self):
        return "/title/%s/" % quote(self.title)


class ModelWithM2MToSite(models.Model):
    title = models.CharField(
        max_length=200,
        help_text=_("Title for the item."),
    )
    sites = models.ManyToManyField(
        Site,
        help_text=_("Sites this item appears on."),
    )

    def get_absolute_url(self):
        return "/title/%s/" % quote(self.title)


class UUIDModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        help_text=_("Unique identifier stored as UUID."),
    )

    def get_absolute_url(self):
        return "/uuid/%s/" % self.pk
