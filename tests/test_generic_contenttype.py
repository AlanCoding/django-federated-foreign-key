import pytest
from django.db import models
from django.test import TestCase
from django.test.utils import isolate_apps

from federated_foreign_key.models import GenericContentType
from example_project.testapp.models import Book

pytestmark = pytest.mark.django_db


def test_post_migrate_creates_contenttype():
    ct = GenericContentType.objects.get(app_label="testapp", model="book")
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
            name = models.CharField(max_length=10)

            class Meta:
                app_label = "tests"

        ct = GenericContentType.objects.get_for_model(ModelCreatedOnTheFly)
        assert ct.app_label == "tests"
        assert ct.model == "modelcreatedonthefly"
