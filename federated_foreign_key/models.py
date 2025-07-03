from collections import defaultdict
from typing import Any, Dict, Optional, Sequence, Tuple, Type

from django.conf import settings
from django.apps import apps
from django.db import models as django_models
from django.utils.translation import gettext_lazy as _
from django.db.models.options import Options


PROJECT_SETTING_NAME = "FEDERATION_PROJECT_NAME"


def get_current_project_name():
    """Return the current project name used for federated lookups."""
    return getattr(settings, PROJECT_SETTING_NAME, "default")


class GenericContentTypeManager(django_models.Manager["GenericContentType"]):
    """Manager storing ``GenericContentType`` objects per project."""

    use_in_migrations = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cache: Dict[str, Dict[Tuple[str, str, str] | int, "GenericContentType"]] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def create(self, *args: Any, **kwargs: Any) -> "GenericContentType":
        obj = super().create(*args, **kwargs)
        self._add_to_cache(self.db, obj)
        return obj

    def _add_to_cache(self, using: str, ct: "GenericContentType") -> None:
        """Store ``ct`` in the manager cache for the given database alias."""
        key = (ct.project, ct.app_label, ct.model)
        self._cache.setdefault(using, {})[key] = ct
        self._cache.setdefault(using, {})[ct.id] = ct

    def _get_from_cache(self, opts: Options, project: str) -> "GenericContentType":
        """Return a cached ``GenericContentType`` for ``opts`` and ``project``."""
        key = (project, opts.app_label, opts.model_name)
        return self._cache[self.db][key]

    def _get_opts(self, model: Type[django_models.Model], for_concrete_model: bool) -> Options:
        """Return the ``Options`` object for ``model``."""
        try:
            return model._meta.concrete_model._meta if for_concrete_model else model._meta
        except AttributeError:
            return model._meta

    def get_for_model(
        self,
        model: Type[django_models.Model],
        for_concrete_model: bool = True,
        project: Optional[str] = None,
    ) -> "GenericContentType":
        from .fields import get_remote_object_class

        remote_base = get_remote_object_class()
        model_cls = model if isinstance(model, type) else model.__class__
        if issubclass(model_cls, remote_base) and not issubclass(model_cls, django_models.Model):
            if project is None:
                project = getattr(model_cls._meta, "service", get_current_project_name())
            opts = model_cls._meta
        else:
            if project is None:
                project = get_current_project_name()
            opts = self._get_opts(model_cls, for_concrete_model)
        try:
            return self._get_from_cache(opts, project)
        except KeyError:
            pass

        try:
            ct = self.get(
                project=project, app_label=opts.app_label, model=opts.model_name
            )
        except self.model.DoesNotExist:
            ct, _ = self.get_or_create(
                project=project,
                app_label=opts.app_label,
                model=opts.model_name,
            )
        self._add_to_cache(self.db, ct)
        return ct

    def get_for_models(
        self,
        *model_list: Type[django_models.Model],
        for_concrete_models: bool = True,
        project: Optional[str] = None,
    ) -> Dict[Type[django_models.Model], "GenericContentType"]:
        """Return ``GenericContentType`` objects for each model in ``model_list``."""
        if project is None:
            project = get_current_project_name()
        results: Dict[Type[django_models.Model], "GenericContentType"] = {}
        needed_models: Dict[str, set[str]] = defaultdict(set)
        needed_opts: Dict[Tuple[str, str], list[Type[django_models.Model]]] = defaultdict(list)
        for model in model_list:
            opts = self._get_opts(model, for_concrete_models)
            try:
                ct = self._get_from_cache(opts, project)
            except KeyError:
                needed_models[opts.app_label].add(opts.model_name)
                needed_opts[(opts.app_label, opts.model_name)].append(model)
            else:
                results[model] = ct

        if needed_opts:
            condition = django_models.Q(
                *(
                    django_models.Q(
                        ("project", project),
                        ("app_label", app_label),
                        ("model__in", models),
                    )
                    for app_label, models in needed_models.items()
                ),
                _connector=django_models.Q.OR,
            )
            cts = self.filter(condition)
            for ct in cts:
                opts_models = needed_opts.pop((ct.app_label, ct.model), [])
                for model in opts_models:
                    results[model] = ct
                self._add_to_cache(self.db, ct)
            for (app_label, model_name), opts_models in needed_opts.items():
                ct = self.create(project=project, app_label=app_label, model=model_name)
                self._add_to_cache(self.db, ct)
                for model in opts_models:
                    results[model] = ct
        return results

    def get_by_natural_key(self, *args: str) -> "GenericContentType":
        """Return the content type identified by its natural key."""
        if len(args) == 2:
            project = get_current_project_name()
            app_label, model = args
        else:
            project, app_label, model = args
        key = (project, app_label, model)
        try:
            return self._cache[self.db][key]
        except KeyError:
            ct = self.get(project=project, app_label=app_label, model=model)
            self._add_to_cache(self.db, ct)
            return ct

    def get_for_id(self, id: int) -> "GenericContentType":
        """Return the content type with primary key ``id`` from the cache."""
        try:
            return self._cache[self.db][id]
        except KeyError:
            ct = self.get(pk=id)
            self._add_to_cache(self.db, ct)
            return ct


class GenericContentType(django_models.Model):
    """Like Django's ``ContentType`` model but scoped by project."""

    project = django_models.CharField(
        max_length=100,
        default=get_current_project_name,
        help_text=_("Project namespace used for federated lookups."),
    )
    app_label = django_models.CharField(
        max_length=100,
        help_text=_(
            "Django app label where the referenced model is defined."
        ),
    )
    model = django_models.CharField(
        max_length=100,
        help_text=_(
            "Name of the model in Django's ``Model._meta.model_name`` format. "
            "For example ``JobTemplate`` becomes ``jobtemplate``."
        ),
    )

    objects = GenericContentTypeManager()

    class Meta:
        unique_together = [
            ("project", "app_label", "model"),
        ]

    def __str__(self) -> str:
        return self.app_labeled_name

    @property
    def name(self) -> str:
        model = self.model_class()
        if (
            not model
            or not hasattr(model, "_meta")
            or not hasattr(model._meta, "verbose_name")
        ):
            return self.model
        return str(model._meta.verbose_name)

    @property
    def app_labeled_name(self) -> str:
        model = self.model_class()
        if (
            not model
            or not hasattr(model, "_meta")
            or not hasattr(model._meta, "app_config")
            or not hasattr(model._meta, "verbose_name")
        ):
            return self.model
        return f"{model._meta.app_config.verbose_name} | {model._meta.verbose_name}"

    def model_class(self) -> Optional[Type[django_models.Model]]:
        """Return the model class or a remote stand-in."""
        if self.project not in ("shared", get_current_project_name()):
            from .fields import get_remote_standin_class
            return get_remote_standin_class(self)
        try:
            return apps.get_model(self.app_label, self.model)
        except LookupError:
            return None

    def get_object_for_this_type(self, **kwargs: Any) -> django_models.Model:
        """Return the object referenced by this content type."""
        model = self.model_class()
        if model is None:
            raise LookupError("Model not available in this project")
        from .fields import get_remote_object_class
        remote_base = get_remote_object_class()
        if issubclass(model, remote_base):
            object_id = (
                kwargs.get("pk")
                or kwargs.get("id")
                or kwargs.get("pk__exact")
                or kwargs.get("id__exact")
            )
            if object_id is None:
                raise LookupError("Model not available in this project")
            return model(self, object_id)
        return model._base_manager.get(**kwargs)

    def get_all_objects_for_this_type(
        self, **kwargs: Any
    ) -> django_models.QuerySet | Sequence[django_models.Model]:
        """Return all objects referenced by this content type."""
        model = self.model_class()
        if model is None:
            raise LookupError("Model not available in this project")
        from .fields import get_remote_object_class
        remote_base = get_remote_object_class()
        if issubclass(model, remote_base):
            ids = (
                kwargs.get("pk__in")
                or kwargs.get("id__in")
                or (kwargs.get("pk") and [kwargs["pk"]])
                or (kwargs.get("id") and [kwargs["id"]])
            )
            if not ids:
                return []
            return [model(self, obj_id) for obj_id in ids]
        return list(model._base_manager.filter(**kwargs))

    def natural_key(self) -> Tuple[str, str, str]:
        return (self.project, self.app_label, self.model)
