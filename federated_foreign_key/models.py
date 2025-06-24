from collections import defaultdict

from django.conf import settings
from django.apps import apps
from django.db import models as django_models

PROJECT_SETTING_NAME = "FEDERATION_PROJECT_NAME"


def get_current_project_name():
    """Return the current project name used for federated lookups."""
    return getattr(settings, PROJECT_SETTING_NAME, "default")


class GenericContentTypeManager(django_models.Manager):
    """Manager storing ``GenericContentType`` objects per project."""

    use_in_migrations = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}

    def clear_cache(self):
        self._cache.clear()

    def create(self, *args, **kwargs):
        obj = super().create(*args, **kwargs)
        self._add_to_cache(self.db, obj)
        return obj

    def _add_to_cache(self, using, ct):
        key = (ct.project, ct.app_label, ct.model)
        self._cache.setdefault(using, {})[key] = ct
        self._cache.setdefault(using, {})[ct.id] = ct

    def _get_from_cache(self, opts, project):
        key = (project, opts.app_label, opts.model_name)
        return self._cache[self.db][key]

    def _get_opts(self, model, for_concrete_model):
        return model._meta.concrete_model._meta if for_concrete_model else model._meta

    def get_for_model(self, model, for_concrete_model=True, project=None):
        if project is None:
            project = get_current_project_name()
        opts = self._get_opts(model, for_concrete_model)
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

    def get_for_models(self, *model_list, for_concrete_models=True, project=None):
        if project is None:
            project = get_current_project_name()
        results = {}
        needed_models = defaultdict(set)
        needed_opts = defaultdict(list)
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

    def get_by_natural_key(self, *args):
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

    def get_for_id(self, id):
        try:
            return self._cache[self.db][id]
        except KeyError:
            ct = self.get(pk=id)
            self._add_to_cache(self.db, ct)
            return ct


class GenericContentType(django_models.Model):
    """Like Django's ``ContentType`` model but scoped by project."""

    project = django_models.CharField(max_length=100, default=get_current_project_name)
    app_label = django_models.CharField(max_length=100)
    model = django_models.CharField(max_length=100)

    objects = GenericContentTypeManager()

    class Meta:
        unique_together = [
            ("project", "app_label", "model"),
        ]

    def __str__(self):
        return self.app_labeled_name

    @property
    def name(self):
        model = self.model_class()
        if not model:
            return self.model
        return str(model._meta.verbose_name)

    @property
    def app_labeled_name(self):
        model = self.model_class()
        if not model:
            return self.model
        return f"{model._meta.app_config.verbose_name} | {model._meta.verbose_name}"

    def model_class(self):
        if self.project not in ("shared", get_current_project_name()):
            return None
        try:
            return apps.get_model(self.app_label, self.model)
        except LookupError:
            return None

    def get_object_for_this_type(self, **kwargs):
        model = self.model_class()
        if model is None:
            raise LookupError("Model not available in this project")
        return model._base_manager.get(**kwargs)

    def get_all_objects_for_this_type(self, **kwargs):
        model = self.model_class()
        if model is None:
            return []
        return model._base_manager.filter(**kwargs)

    def natural_key(self):
        return (self.project, self.app_label, self.model)
