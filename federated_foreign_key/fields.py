from django.db.models.fields.mixins import FieldCacheMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Field

from .models import GenericContentType, get_current_project_name


class RemoteObject:
    def __init__(self, content_type, object_id):
        self.content_type = content_type
        self.object_id = object_id

    def __repr__(self):
        return f"<RemoteObject {self.content_type} id={self.object_id}>"


class FederatedForeignKey(FieldCacheMixin, Field):
    def __init__(
        self,
        ct_field="content_type",
        fk_field="object_id",
        for_concrete_model=True,
    ):
        Field.__init__(self, editable=False)
        FieldCacheMixin.__init__(self)
        self.ct_field = ct_field
        self.fk_field = fk_field
        self.for_concrete_model = for_concrete_model
        self.is_relation = True

    @property
    def cache_name(self):
        return self.name

    def get_cache_name(self):
        return self.cache_name

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, private_only=True, **kwargs)
        setattr(cls, self.attname, self)

    def get_attname_column(self):
        attname, column = super().get_attname_column()
        return attname, None

    def get_content_type(self, obj=None, id=None, model=None):
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
                rel_obj = RemoteObject(ct, pk_val)
        self.set_cached_value(instance, rel_obj)
        return rel_obj

    def __set__(self, instance, value):
        if value is None:
            setattr(instance, self.ct_field, None)
            setattr(instance, self.fk_field, None)
            self.set_cached_value(instance, None)
            return
        ct = self.get_content_type(obj=value)
        setattr(instance, self.ct_field, ct)
        setattr(instance, self.fk_field, value.pk)
        self.set_cached_value(instance, value)
