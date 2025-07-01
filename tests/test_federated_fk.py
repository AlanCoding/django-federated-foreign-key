import pytest

from federated_foreign_key.models import GenericContentType
from federated_foreign_key.fields import RemoteObject
from example_project.testapp.models import Book, Reference

pytestmark = pytest.mark.django_db


class ExtraRemoteObject(RemoteObject):
    """Custom remote object used in tests."""

    def extra(self):
        return self.content_type.project


def test_local_reference():
    book = Book.objects.create(title="Django")
    ct = GenericContentType.objects.get_for_model(Book)
    Reference.objects.create(content_type=ct, object_id=book.pk)

    ref = Reference.objects.get()
    assert isinstance(ref.content_object, Book)
    assert ref.content_object.pk == book.pk


def test_remote_reference():
    # simulate remote project
    remote_project = "project_b"
    ct = GenericContentType.objects.create(
        project=remote_project,
        app_label="testapp",
        model="book",
    )
    ref = Reference.objects.create(content_type=ct, object_id=1)
    obj = ref.content_object
    from federated_foreign_key.fields import RemoteObject

    assert isinstance(obj, RemoteObject)
    assert isinstance(obj, ct.model_class())
    assert obj.object_id == 1
    assert obj.content_type.project == remote_project


def test_custom_remote_object(settings):
    settings.FEDERATED_REMOTE_OBJECT_CLASS = "tests.test_federated_fk.ExtraRemoteObject"
    remote_project = "project_c"
    ct = GenericContentType.objects.create(
        project=remote_project,
        app_label="testapp",
        model="book",
    )
    ref = Reference.objects.create(content_type=ct, object_id=2)

    obj = ref.content_object

    assert isinstance(obj, ExtraRemoteObject)
    assert isinstance(obj, ct.model_class())
    assert obj.extra() == remote_project


def test_shared_project_local_reference():
    """References to the 'shared' project are treated as local."""
    book = Book.objects.create(title="Shared book")
    ct = GenericContentType.objects.get_for_model(Book, project="shared")
    Reference.objects.create(content_type=ct, object_id=book.pk)

    ref = Reference.objects.get()
    assert ref.content_type.project == "shared"
    assert isinstance(ref.content_object, Book)
    assert ref.content_object.pk == book.pk


def test_reverse_manager_add_remove_clear():
    book = Book.objects.create(title="AddRemove")
    other = Book.objects.create(title="Other")
    ct = GenericContentType.objects.get_for_model(Book)
    ref1 = Reference.objects.create(content_type=ct, object_id=other.pk)
    ref2 = Reference.objects.create(content_type=ct, object_id=other.pk)

    book.references.add(ref1, ref2)
    ref1.refresh_from_db()
    ref2.refresh_from_db()
    assert set(book.references.all()) == {ref1, ref2}
    assert ref1.object_id == book.pk

    book.references.remove(ref1)
    assert list(book.references.all()) == [ref2]

    book.references.clear()
    assert book.references.count() == 0


def test_reverse_manager_create_and_get():
    book = Book.objects.create(title="Create")

    ref = book.references.create()
    assert ref.content_object == book
    assert list(book.references.all()) == [ref]

    same, created = book.references.get_or_create(pk=ref.pk)
    assert not created
    assert same == ref

    updated, created = book.references.update_or_create(pk=ref.pk)
    assert not created
    assert updated == ref
