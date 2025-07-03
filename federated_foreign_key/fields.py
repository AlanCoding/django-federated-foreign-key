from __future__ import annotations

import functools
import itertools

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist
from django.core import checks
from django.db import DEFAULT_DB_ALIAS, models, router, transaction
from django.db.models import DO_NOTHING, ForeignObject, ForeignObjectRel
from django.db.models.base import ModelBase, make_foreign_order_accessors

from django.db.models.fields.related import (
    ReverseManyToOneDescriptor,
    lazy_related_operation,
)
from django.db.models.query_utils import PathInfo
from django.db.models.sql import AND
from django.db.models.sql.where import WhereNode
from django.db.models.utils import AltersData
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.contrib.contenttypes.fields import (
    GenericForeignKey as DjangoGenericForeignKey,
)

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


_REMOTE_STANDIN_CACHE: dict[tuple[str, str, str], type[RemoteObject]] = {}


def get_remote_standin_class(content_type: GenericContentType):
    """Return a RemoteObject subclass unique to ``content_type``."""
    key = (content_type.project, content_type.app_label, content_type.model)
    standin = _REMOTE_STANDIN_CACHE.get(key)
    if standin is None:
        base = get_remote_object_class()
        name = (
            f"Remote[{content_type.project}:{content_type.app_label}.{content_type.model}]"
        )

        class StandinMeta:
            def __init__(self, ct: GenericContentType):
                self.model_name = ct.model
                self.app_label = ct.app_label
                self.service = ct.project

        standin = type(
            name,
            (base,),
            {
                "_meta": StandinMeta(content_type),
                "get_content_type": classmethod(
                    lambda cls: GenericContentType.objects.get_for_model(cls)
                ),
            },
        )
        _REMOTE_STANDIN_CACHE[key] = standin
    return standin


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
        super().__init__(
            ct_field=ct_field, fk_field=fk_field, for_concrete_model=for_concrete_model
        )

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
                        "'%s.%s' is not a ForeignKey."
                        % (self.model._meta.object_name, self.ct_field),
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
            return GenericContentType.objects.db_manager(obj._state.db).get_for_model(
                obj.__class__,
            )
        elif id is not None:
            return GenericContentType.objects.db_manager(using).get_for_id(id)
        elif model is not None:
            return GenericContentType.objects.db_manager(using).get_for_model(model)
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
                rel_obj = ct.get_object_for_this_type(pk=pk_val)
        self.set_cached_value(instance, rel_obj)
        return rel_obj


class FederatedRel(ForeignObjectRel):
    def __init__(
        self,
        field,
        to,
        related_name=None,
        related_query_name=None,
        limit_choices_to=None,
    ):
        super().__init__(
            field,
            to,
            related_name=related_query_name or "+",
            related_query_name=related_query_name,
            limit_choices_to=limit_choices_to,
            on_delete=DO_NOTHING,
        )


class FederatedRelation(ForeignObject):
    auto_created = False
    empty_strings_allowed = False

    many_to_many = False
    many_to_one = False
    one_to_many = True
    one_to_one = False

    rel_class = FederatedRel

    mti_inherited = False

    def __init__(
        self,
        to,
        object_id_field="object_id",
        content_type_field="content_type",
        for_concrete_model=True,
        related_query_name=None,
        limit_choices_to=None,
        **kwargs,
    ):
        kwargs["rel"] = self.rel_class(
            self,
            to,
            related_query_name=related_query_name,
            limit_choices_to=limit_choices_to,
        )
        kwargs["null"] = True
        kwargs["blank"] = True
        kwargs["on_delete"] = models.CASCADE
        kwargs["editable"] = False
        kwargs["serialize"] = False
        super().__init__(to, from_fields=[object_id_field], to_fields=[], **kwargs)
        self.object_id_field_name = object_id_field
        self.content_type_field_name = content_type_field
        self.for_concrete_model = for_concrete_model

    def check(self, **kwargs):
        return [
            *super().check(**kwargs),
            *self._check_generic_foreign_key_existence(),
        ]

    def _is_matching_generic_foreign_key(self, field):
        return (
            isinstance(field, FederatedForeignKey)
            and field.ct_field == self.content_type_field_name
            and field.fk_field == self.object_id_field_name
        )

    def _check_generic_foreign_key_existence(self):
        target = self.remote_field.model
        if isinstance(target, ModelBase):
            fields = target._meta.private_fields
            if any(self._is_matching_generic_foreign_key(field) for field in fields):
                return []
            else:
                return [
                    checks.Error(
                        (
                            "The GenericRelation defines a relation with the model '%s', "
                            "but that model does not have a GenericForeignKey."
                        )
                        % target._meta.label,
                        obj=self,
                        id="contenttypes.E004",
                    )
                ]
        else:
            return []

    def resolve_related_fields(self):
        self.to_fields = [self.model._meta.pk.name]
        return [
            (
                self.remote_field.model._meta.get_field(self.object_id_field_name),
                self.model._meta.pk,
            )
        ]

    def get_local_related_value(self, instance):
        return self.get_instance_value_for_fields(instance, self.foreign_related_fields)

    def get_foreign_related_value(self, instance):
        return tuple(
            foreign_field.to_python(val)
            for foreign_field, val in zip(
                self.foreign_related_fields,
                self.get_instance_value_for_fields(instance, self.local_related_fields),
            )
        )

    def _get_path_info_with_parent(self, filtered_relation):
        path = []
        opts = self.remote_field.model._meta.concrete_model._meta
        parent_opts = opts.get_field(self.object_id_field_name).model._meta
        target = parent_opts.pk
        path.append(
            PathInfo(
                from_opts=self.model._meta,
                to_opts=parent_opts,
                target_fields=(target,),
                join_field=self.remote_field,
                m2m=True,
                direct=False,
                filtered_relation=filtered_relation,
            )
        )
        parent_field_chain = []
        while parent_opts != opts:
            field = opts.get_ancestor_link(parent_opts.model)
            parent_field_chain.append(field)
            opts = field.remote_field.model._meta
        parent_field_chain.reverse()
        for field in parent_field_chain:
            path.extend(field.remote_field.path_infos)
        return path

    def get_path_info(self, filtered_relation=None):
        opts = self.remote_field.model._meta
        object_id_field = opts.get_field(self.object_id_field_name)
        if object_id_field.model != opts.model:
            return self._get_path_info_with_parent(filtered_relation)
        else:
            target = opts.pk
            return [
                PathInfo(
                    from_opts=self.model._meta,
                    to_opts=opts,
                    target_fields=(target,),
                    join_field=self.remote_field,
                    m2m=True,
                    direct=False,
                    filtered_relation=filtered_relation,
                )
            ]

    def get_reverse_path_info(self, filtered_relation=None):
        opts = self.model._meta
        from_opts = self.remote_field.model._meta
        return [
            PathInfo(
                from_opts=from_opts,
                to_opts=opts,
                target_fields=(opts.pk,),
                join_field=self,
                m2m=False,
                direct=False,
                filtered_relation=filtered_relation,
            )
        ]

    def value_to_string(self, obj):
        qs = getattr(obj, self.name).all()
        return str([instance.pk for instance in qs])

    def contribute_to_class(self, cls, name, **kwargs):
        kwargs["private_only"] = True
        super().contribute_to_class(cls, name, **kwargs)
        self.model = cls
        if self.mti_inherited:
            self.remote_field.related_name = "+"
            self.remote_field.related_query_name = None
        setattr(cls, self.name, ReverseFederatedManyToOneDescriptor(self.remote_field))

        if not cls._meta.abstract:

            def make_generic_foreign_order_accessors(related_model, model):
                if self._is_matching_generic_foreign_key(
                    model._meta.order_with_respect_to
                ):
                    make_foreign_order_accessors(model, related_model)

            lazy_related_operation(
                make_generic_foreign_order_accessors,
                self.model,
                self.remote_field.model,
            )

    def set_attributes_from_rel(self):
        pass

    def get_internal_type(self):
        return "ManyToManyField"

    def get_content_type(self):
        return GenericContentType.objects.get_for_model(
            self.model, for_concrete_model=self.for_concrete_model
        )

    def get_extra_restriction(self, alias, remote_alias):
        field = self.remote_field.model._meta.get_field(self.content_type_field_name)
        contenttype_pk = self.get_content_type().pk
        lookup = field.get_lookup("exact")(field.get_col(remote_alias), contenttype_pk)
        return WhereNode([lookup], connector=AND)

    def bulk_related_objects(self, objs, using=DEFAULT_DB_ALIAS):
        return self.remote_field.model._base_manager.db_manager(using).filter(
            **{
                f"{self.content_type_field_name}__pk": GenericContentType.objects.db_manager(
                    using
                )
                .get_for_model(self.model, for_concrete_model=self.for_concrete_model)
                .pk,
                f"{self.object_id_field_name}__in": [obj.pk for obj in objs],
            }
        )


class ReverseFederatedManyToOneDescriptor(ReverseManyToOneDescriptor):
    @cached_property
    def related_manager_cls(self):
        return create_federated_related_manager(
            self.rel.model._default_manager.__class__,
            self.rel,
        )


def create_federated_related_manager(superclass, rel):
    class FederatedRelatedObjectManager(superclass, AltersData):
        def __init__(self, instance=None):
            super().__init__()
            self.instance = instance
            self.model = rel.model
            self.get_content_type = functools.partial(
                GenericContentType.objects.db_manager(instance._state.db).get_for_model,
                for_concrete_model=rel.field.for_concrete_model,
            )
            self.content_type = self.get_content_type(instance)
            self.content_type_field_name = rel.field.content_type_field_name
            self.object_id_field_name = rel.field.object_id_field_name
            self.prefetch_cache_name = rel.field.attname
            self.pk_val = instance.pk
            self.core_filters = {
                f"{self.content_type_field_name}__pk": self.content_type.id,
                self.object_id_field_name: self.pk_val,
            }

        def __call__(self, *, manager):
            manager = getattr(self.model, manager)
            manager_class = create_federated_related_manager(manager.__class__, rel)
            return manager_class(instance=self.instance)

        do_not_call_in_templates = True

        def __str__(self):
            return repr(self)

        def _apply_rel_filters(self, queryset):
            db = self._db or router.db_for_read(self.model, instance=self.instance)
            return queryset.using(db).filter(**self.core_filters)

        def _remove_prefetched_objects(self):
            try:
                self.instance._prefetched_objects_cache.pop(self.prefetch_cache_name)
            except (AttributeError, KeyError):
                pass

        def get_queryset(self):
            try:
                return self.instance._prefetched_objects_cache[self.prefetch_cache_name]
            except (AttributeError, KeyError):
                queryset = super().get_queryset()
                return self._apply_rel_filters(queryset)

        def get_prefetch_querysets(self, instances, querysets=None):
            if querysets and len(querysets) != 1:
                raise ValueError(
                    "querysets argument of get_prefetch_querysets() should have a length of 1."
                )
            queryset = querysets[0] if querysets else super().get_queryset()
            queryset._add_hints(instance=instances[0])
            queryset = queryset.using(queryset._db or self._db)
            content_type_queries = [
                models.Q.create(
                    [
                        (f"{self.content_type_field_name}__pk", content_type_id),
                        (f"{self.object_id_field_name}__in", {obj.pk for obj in objs}),
                    ]
                )
                for content_type_id, objs in itertools.groupby(
                    sorted(instances, key=lambda obj: self.get_content_type(obj).pk),
                    lambda obj: self.get_content_type(obj).pk,
                )
            ]
            query = models.Q.create(content_type_queries, connector=models.Q.OR)
            object_id_converter = instances[0]._meta.pk.to_python
            content_type_id_field_name = f"{self.content_type_field_name}_id"
            return (
                queryset.filter(query),
                lambda relobj: (
                    object_id_converter(getattr(relobj, self.object_id_field_name)),
                    getattr(relobj, content_type_id_field_name),
                ),
                lambda obj: (obj.pk, self.get_content_type(obj).pk),
                False,
                self.prefetch_cache_name,
                False,
            )

        def add(self, *objs, bulk=True):
            self._remove_prefetched_objects()
            db = router.db_for_write(self.model, instance=self.instance)

            def check_and_update_obj(obj):
                if not isinstance(obj, self.model):
                    raise TypeError(
                        "'%s' instance expected, got %r"
                        % (self.model._meta.object_name, obj)
                    )
                setattr(obj, self.content_type_field_name, self.content_type)
                setattr(obj, self.object_id_field_name, self.pk_val)

            if bulk:
                pks = []
                for obj in objs:
                    if obj._state.adding or obj._state.db != db:
                        raise ValueError(
                            "%r instance isn't saved. Use bulk=False or save the object first."
                            % obj
                        )
                    check_and_update_obj(obj)
                    pks.append(obj.pk)

                self.model._base_manager.using(db).filter(pk__in=pks).update(
                    **{
                        self.content_type_field_name: self.content_type,
                        self.object_id_field_name: self.pk_val,
                    }
                )
            else:
                with transaction.atomic(using=db, savepoint=False):
                    for obj in objs:
                        check_and_update_obj(obj)
                        obj.save()

        add.alters_data = True

        def remove(self, *objs, bulk=True):
            if not objs:
                return
            self._clear(self.filter(pk__in=[o.pk for o in objs]), bulk)

        remove.alters_data = True

        def clear(self, *, bulk=True):
            self._clear(self, bulk)

        clear.alters_data = True

        def _clear(self, queryset, bulk):
            self._remove_prefetched_objects()
            db = router.db_for_write(self.model, instance=self.instance)
            queryset = queryset.using(db)
            if bulk:
                queryset.delete()
            else:
                with transaction.atomic(using=db, savepoint=False):
                    for obj in queryset:
                        obj.delete()

        _clear.alters_data = True

        def set(self, objs, *, bulk=True, clear=False):
            objs = tuple(objs)
            db = router.db_for_write(self.model, instance=self.instance)
            with transaction.atomic(using=db, savepoint=False):
                if clear:
                    self.clear()
                    self.add(*objs, bulk=bulk)
                else:
                    old_objs = set(self.using(db).all())
                    new_objs = []
                    for obj in objs:
                        if obj in old_objs:
                            old_objs.remove(obj)
                        else:
                            new_objs.append(obj)

                    self.remove(*old_objs)
                    self.add(*new_objs, bulk=bulk)

        set.alters_data = True

        def create(self, **kwargs):
            self._remove_prefetched_objects()
            kwargs[self.content_type_field_name] = self.content_type
            kwargs[self.object_id_field_name] = self.pk_val
            db = router.db_for_write(self.model, instance=self.instance)
            return super().using(db).create(**kwargs)

        create.alters_data = True

        def get_or_create(self, **kwargs):
            kwargs[self.content_type_field_name] = self.content_type
            kwargs[self.object_id_field_name] = self.pk_val
            db = router.db_for_write(self.model, instance=self.instance)
            return super().using(db).get_or_create(**kwargs)

        get_or_create.alters_data = True

        def update_or_create(self, **kwargs):
            kwargs[self.content_type_field_name] = self.content_type
            kwargs[self.object_id_field_name] = self.pk_val
            db = router.db_for_write(self.model, instance=self.instance)
            return super().using(db).update_or_create(**kwargs)

        update_or_create.alters_data = True

    return FederatedRelatedObjectManager
