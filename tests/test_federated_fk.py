import pytest

from federated_foreign_key.models import GenericContentType
from federated_foreign_key.fields import RemoteObject
from federated_foreign_key.prefetch import FederatedPrefetch
from django.db import models, connection
from django.test.utils import CaptureQueriesContext
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


def test_prefetch_remote_content_object_twice():
    ct = GenericContentType.objects.create(
        project="remote_proj_twice",
        app_label="testapp",
        model="book",
    )
    Reference.objects.create(content_type=ct, object_id=1)

    qs = Reference.objects.prefetch_related("content_object", "content_object")
    result = list(qs)[0]
    first = result.content_object
    second = result.content_object

    from federated_foreign_key.fields import RemoteObject

    assert isinstance(first, RemoteObject)
    assert first.object_id == 1
    assert first is second


def test_prefetch_related_objects():
    """Prefetch ``content_object`` for local references only."""
    books = [Book.objects.create(title=f"Prefetch {i}") for i in range(5)]
    ct_local = GenericContentType.objects.get_for_model(Book)
    local_refs = [
        Reference.objects.create(content_type=ct_local, object_id=b.pk)
        for b in books
    ]

    ct_remote = GenericContentType.objects.create(
        project="project_remote",
        app_label="testapp",
        model="book",
    )
    remote_ref = Reference.objects.create(content_type=ct_remote, object_id=99)

    models.prefetch_related_objects(
        local_refs,
        FederatedPrefetch("content_object", [Book.objects.all()]),
    )

    with CaptureQueriesContext(connection) as ctx:
        local_objs = [r.content_object for r in local_refs]
        remote_obj = remote_ref.content_object
    assert len(ctx.captured_queries) == 0
    assert local_objs == books
    assert isinstance(remote_obj, RemoteObject)
    assert remote_obj.object_id == 99


def test_remote_object_hashing():
    """Remote objects referencing the same item should hash equally."""
    ct = GenericContentType.objects.create(
        project="hash_proj",
        app_label="testapp",
        model="book",
    )
    refs = [
        Reference.objects.create(content_type=ct, object_id=7)
        for _ in range(5)
    ]
    objs = [r.content_object for r in refs]

    # objects should compare equal and condense to a single entry in a set
    assert len(set(objs)) == 1
    assert all(o == objs[0] for o in objs)
