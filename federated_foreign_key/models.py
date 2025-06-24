from django.conf import settings
from django.apps import apps
from django.db import models

PROJECT_SETTING_NAME = "FEDERATION_PROJECT_NAME"


def get_current_project_name():
    """Return the current project name used for federated lookups."""
    return getattr(settings, PROJECT_SETTING_NAME, "default")


class GenericContentTypeManager(models.Manager):
    """Manager storing ``GenericContentType`` objects per project."""

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
        needed = {}
        cache = self._get_cache()
        for model in models:
            opts = model._meta.concrete_model._meta if for_concrete_models else model._meta
            key = (project, opts.app_label, opts.model_name)
            if key in cache:
                results[model] = cache[key]
            else:
                needed.setdefault((opts.app_label, opts.model_name), []).append(model)

        if needed:
            condition = models.Q()
            for (app_label, model_name) in needed.keys():
                condition |= models.Q(project=project, app_label=app_label, model=model_name)
            cts = self.filter(condition)
            for ct in cts:
                key = (ct.app_label, ct.model)
                for model in needed.pop(key, []):
                    results[model] = ct
                cache[(ct.project, ct.app_label, ct.model)] = ct
            for (app_label, model_name), models_list in needed.items():
                ct = self.create(project=project, app_label=app_label, model=model_name)
                cache[(project, app_label, model_name)] = ct
                for model in models_list:
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
    """Like Django's ``ContentType`` model but scoped by project."""

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
