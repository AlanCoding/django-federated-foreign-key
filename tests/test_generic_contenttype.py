import pytest
from django.db import models
from django.test import TestCase
from django.test.utils import isolate_apps
from django.utils.translation import gettext_lazy as _

from federated_foreign_key.models import GenericContentType
from example_project.testapp.models import Book

pytestmark = pytest.mark.django_db


def test_post_migrate_creates_contenttype():
    ct = GenericContentType.objects.get(app_label="testapp", model="book")
    assert ct.project == "project_a"


def test_post_migrate_creates_contenttype_with_existing_remote():
    """A content type is created even if another project already defined it."""
    # Remove the content type created during migrations.
    GenericContentType.objects.filter(
        project="project_a", app_label="testapp", model="book"
    ).delete()

    # Simulate a content type created by a different project.
    GenericContentType.objects.create(
        project="project_b", app_label="testapp", model="book"
    )

    from django.apps import apps
    from federated_foreign_key import management as contenttypes_management

    app_config = apps.get_app_config("testapp")
    contenttypes_management.create_generic_contenttypes(app_config, verbosity=0)

    ct = GenericContentType.objects.get(project="project_a", app_label="testapp", model="book")
    assert ct.project == "project_a"


class GenericContentTypeTests(TestCase):
    def setUp(self):
        GenericContentType.objects.clear_cache()
        self.addCleanup(GenericContentType.objects.clear_cache)

    def test_lookup_cache(self):
        with self.assertNumQueries(1):
            GenericContentType.objects.get_for_model(Book)
        with self.assertNumQueries(0):
            ct = GenericContentType.objects.get_for_model(Book)
        with self.assertNumQueries(0):
            GenericContentType.objects.get_for_id(ct.id)
        with self.assertNumQueries(0):
            GenericContentType.objects.get_by_natural_key(
                ct.project,
                ct.app_label,
                ct.model,
            )
        GenericContentType.objects.clear_cache()
        with self.assertNumQueries(1):
            GenericContentType.objects.get_for_model(Book)

    @isolate_apps("tests")
    def test_get_for_model_create_contenttype(self):
        class ModelCreatedOnTheFly(models.Model):
            name = models.CharField(
                max_length=10,
                help_text=_("Label for the temporary model instance."),
            )

            class Meta:
                app_label = "tests"

        ct = GenericContentType.objects.get_for_model(ModelCreatedOnTheFly)
        assert ct.app_label == "tests"
        assert ct.model == "modelcreatedonthefly"


def test_get_object_for_this_type_remote():
    """Remote objects should return a remote proxy."""
    ct = GenericContentType.objects.create(
        project="remote_proj",
        app_label="testapp",
        model="book",
    )

    obj = ct.get_object_for_this_type(pk=1)

    from federated_foreign_key.fields import RemoteObject

    assert isinstance(obj, RemoteObject)
    assert obj.object_id == 1
    assert obj.content_type == ct


def test_get_all_objects_for_this_type_remote():
    ct = GenericContentType.objects.create(
        project="remote_proj2",
        app_label="testapp",
        model="book",
    )

    objs = ct.get_all_objects_for_this_type(pk__in=[1, 2])

    from federated_foreign_key.fields import RemoteObject

    assert [o.object_id for o in objs] == [1, 2]
    assert all(isinstance(o, RemoteObject) for o in objs)


def test_model_class_remote_returns_standin():
    ct = GenericContentType.objects.create(
        project="remote_proj3",
        app_label="testapp",
        model="book",
    )

    cls1 = ct.model_class()
    cls2 = ct.model_class()
    from federated_foreign_key.fields import RemoteObject

    assert issubclass(cls1, RemoteObject)
    assert cls1._meta.model_name == "book"
    assert cls1._meta.app_label == "testapp"
    assert cls1 is cls2
    obj = ct.get_object_for_this_type(pk=5)
    assert isinstance(obj, cls1)


def test_get_for_model_remote():
    ct = GenericContentType.objects.create(
        project="remote_proj4",
        app_label="testapp",
        model="book",
    )

    cls = ct.model_class()
    assert cls._meta.service == "remote_proj4"

    fetched = GenericContentType.objects.get_for_model(cls)
    assert fetched == ct


def test_remote_class_get_content_type():
    ct = GenericContentType.objects.create(
        project="remote_proj5",
        app_label="testapp",
        model="book",
    )

    cls = ct.model_class()
    assert cls.get_content_type() == ct
