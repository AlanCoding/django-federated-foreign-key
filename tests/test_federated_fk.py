import pytest

from federated_foreign_key.models import GenericContentType
from tests.example_project.testapp.models import Book, Reference

pytestmark = pytest.mark.django_db


def test_local_reference():
    book = Book.objects.create(title='Django')
    ct = GenericContentType.objects.get_for_model(Book)
    ref = Reference.objects.create(content_type=ct, object_id=book.pk)
    assert isinstance(ref.content_object, Book)
    assert ref.content_object.pk == book.pk


def test_remote_reference():
    # simulate remote project
    remote_project = 'project_b'
    ct = GenericContentType.objects.create(
        project=remote_project,
        app_label="testapp",
        model="book",
    )
    ref = Reference.objects.create(content_type=ct, object_id=1)
    obj = ref.content_object
    from federated_foreign_key.fields import RemoteObject
    assert isinstance(obj, RemoteObject)
    assert obj.object_id == 1
    assert obj.content_type.project == remote_project
