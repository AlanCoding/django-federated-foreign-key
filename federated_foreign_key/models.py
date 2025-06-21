from django.conf import settings
from django.apps import apps
from django.db import models

PROJECT_SETTING_NAME = 'FEDERATION_PROJECT_NAME'


def get_current_project_name():
    return getattr(settings, PROJECT_SETTING_NAME, 'default')


class GenericContentTypeManager(models.Manager):
    def get_for_model(self, model, project=None):
        if project is None:
            project = get_current_project_name()
        opts = model._meta
        return self.get_or_create(
            project=project,
            app_label=opts.app_label,
            model=opts.model_name,
        )[0]

    def get_by_natural_key(self, project, app_label, model):
        return self.get(project=project, app_label=app_label, model=model)


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
        return f"{self.project}:{self.app_label}.{self.model}"

    def model_class(self):
        if self.project not in ('shared', get_current_project_name()):
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

    def natural_key(self):
        return (self.project, self.app_label, self.model)
