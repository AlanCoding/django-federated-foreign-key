from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.core import checks
from django.db import models
from django.utils.module_loading import import_string
from django.contrib.contenttypes.fields import GenericForeignKey as DjangoGenericForeignKey

from .models import GenericContentType, get_current_project_name

REMOTE_OBJECT_CLASS_SETTING = "FEDERATED_REMOTE_OBJECT_CLASS"


def get_remote_object_class():
    """Return the class used for remote objects."""
    path = getattr(
        settings,
        REMOTE_OBJECT_CLASS_SETTING,
        "federated_foreign_key.fields.RemoteObject",
    )
    return import_string(path)


class RemoteObject:
    """Placeholder for objects that live in another project."""

    def __init__(self, content_type, object_id):
        self.content_type = content_type
        self.object_id = object_id

    def __repr__(self):
        return f"<RemoteObject {self.content_type} id={self.object_id}>"


class FederatedForeignKey(DjangoGenericForeignKey):
    """A GenericForeignKey variant aware of project boundaries."""
    def __init__(
        self,
        ct_field="content_type",
        fk_field="object_id",
        for_concrete_model=True,
    ):
        super().__init__(ct_field=ct_field, fk_field=fk_field, for_concrete_model=for_concrete_model)

    def _check_content_type_field(self):
        try:
            field = self.model._meta.get_field(self.ct_field)
        except FieldDoesNotExist:
            return [
                checks.Error(
                    "The GenericForeignKey content type references the nonexistent field '%s.%s'."
                    % (self.model._meta.object_name, self.ct_field),
                    obj=self,
                    id="contenttypes.E002",
                )
            ]
        else:
            if not isinstance(field, models.ForeignKey):
                return [
                    checks.Error(
                        "'%s.%s' is not a ForeignKey." % (self.model._meta.object_name, self.ct_field),
                        hint=(
                            "GenericForeignKeys must use a ForeignKey to "
                            "'federated_foreign_key.GenericContentType' as the "
                            "'content_type' field."
                        ),
                        obj=self,
                        id="contenttypes.E003",
                    )
                ]
            elif field.remote_field.model != GenericContentType:
                return [
                    checks.Error(
                        "'%s.%s' is not a ForeignKey to 'federated_foreign_key.GenericContentType'."
                        % (self.model._meta.object_name, self.ct_field),
                        hint=(
                            "GenericForeignKeys must use a ForeignKey to "
                            "'federated_foreign_key.GenericContentType' as the "
                            "'content_type' field."
                        ),
                        obj=self,
                        id="contenttypes.E004",
                    )
                ]
            else:
                return []

    def get_content_type(self, obj=None, id=None, using=None, model=None):
        if obj is not None:
            return GenericContentType.objects.get_for_model(obj.__class__)
        elif id is not None:
            return GenericContentType.objects.get(pk=id)
        elif model is not None:
            return GenericContentType.objects.get_for_model(model)
        else:
            raise Exception("Impossible arguments to get_content_type")

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        f = instance._meta.get_field(self.ct_field)
        ct_id = getattr(instance, f.attname, None)
        pk_val = getattr(instance, self.fk_field)
        rel_obj = self.get_cached_value(instance, default=None)
        if rel_obj is None and self.is_cached(instance):
            return rel_obj
        if rel_obj is not None:
            ct_match = ct_id == self.get_content_type(obj=rel_obj).id
            pk_match = ct_match and rel_obj.pk == pk_val
            if pk_match:
                return rel_obj
            else:
                rel_obj = None
        if ct_id is not None:
            ct = self.get_content_type(id=ct_id)
            if ct.project in (get_current_project_name(), "shared"):
                try:
                    rel_obj = ct.get_object_for_this_type(pk=pk_val)
                except (ObjectDoesNotExist, LookupError):
                    rel_obj = None
            else:
                rel_obj = get_remote_object_class()(ct, pk_val)
        self.set_cached_value(instance, rel_obj)
        return rel_obj
