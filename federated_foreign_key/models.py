from collections import defaultdict

from django.apps import apps
from django.conf import settings
from django.db import models
from django.db.models import Q

PROJECT_SETTING_NAME = 'FEDERATION_PROJECT_NAME'


def get_current_project_name():
    return getattr(settings, PROJECT_SETTING_NAME, 'default')


class GenericContentTypeManager(models.Manager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = None

    def _get_cache(self):
        if self._cache is None:
            self._cache = {
                (ct.project, ct.app_label, ct.model): ct
                for ct in super().get_queryset().all()
            }
        return self._cache

    def clear_cache(self):
        self._cache = None

    def _get_opts(self, model, for_concrete_model=True):
        if for_concrete_model:
            model = model._meta.concrete_model
        return model._meta

    def _get_from_cache(self, key):
        return self._get_cache()[key]

    def get_for_model(self, model, project=None):
        if project is None:
            project = get_current_project_name()
        opts = model._meta
        key = (project, opts.app_label, opts.model_name)
        cache = self._get_cache()
        if key in cache:
            return cache[key]
        ct, _ = self.get_or_create(
            project=project,
            app_label=opts.app_label,
            model=opts.model_name,
        )
        cache[key] = ct
        return ct

    def get_for_models(self, *models, for_concrete_models=True, project=None):
        if project is None:
            project = get_current_project_name()
        results = {}
        needed_models = defaultdict(set)
        needed_opts = defaultdict(list)
        for model in models:
            opts = self._get_opts(model, for_concrete_models)
            key = (project, opts.app_label, opts.model_name)
            cache = self._get_cache()
            if key in cache:
                results[model] = cache[key]
            else:
                needed_models[opts.app_label].add(opts.model_name)
                needed_opts[(opts.app_label, opts.model_name)].append(model)
        if needed_opts:
            condition = Q(
                *(
                    Q(("app_label", app_label), ("model__in", models))
                    for app_label, models in needed_models.items()
                ),
                project=project,
                _connector=Q.OR,
            )
            for ct in self.filter(condition):
                opts_models = needed_opts.pop((ct.app_label, ct.model), [])
                for model in opts_models:
                    results[model] = ct
                cache = self._get_cache()
                cache[(ct.project, ct.app_label, ct.model)] = ct
        for (app_label, model_name), opts_models in needed_opts.items():
            ct = self.create(project=project, app_label=app_label, model=model_name)
            cache = self._get_cache()
            cache[(ct.project, ct.app_label, ct.model)] = ct
            for model in opts_models:
                results[model] = ct
        return results

    def get_by_natural_key(self, project, app_label, model):
        key = (project, app_label, model)
        cache = self._get_cache()
        if key in cache:
            return cache[key]
        ct = self.get(project=project, app_label=app_label, model=model)
        cache[key] = ct
        return ct

    def get_for_id(self, id):
        cache = self._get_cache()
        for ct in cache.values():
            if ct.id == id:
                return ct
        ct = self.get(pk=id)
        cache[(ct.project, ct.app_label, ct.model)] = ct
        return ct


class GenericContentType(models.Model):
    project = models.CharField(max_length=100)
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

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
        if self.project not in ('shared', get_current_project_name()):
            return None
        try:
            return apps.get_model(self.app_label, self.model)
        except LookupError:
            return None

    def get_object_for_this_type(self, using=None, **kwargs):
        model = self.model_class()
        if model is None:
            raise LookupError("Model not available in this project")
        try:
            return model._base_manager.using(using).get(**kwargs)
        except Exception as exc:
            # Mirror ContentType behavior by raising ValueError for invalid keys
            if isinstance(exc, (models.ObjectDoesNotExist, ValueError)):
                raise
            from django.core.exceptions import ValidationError

            if isinstance(exc, ValidationError):
                raise ValueError from exc
            raise

    def get_all_objects_for_this_type(self, using=None, **kwargs):
        model = self.model_class()
        if model is None:
            raise LookupError("Model not available in this project")
        return model._base_manager.using(using).filter(**kwargs)

    def natural_key(self):
        return (self.project, self.app_label, self.model)
