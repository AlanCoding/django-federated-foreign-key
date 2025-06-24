from django.db import DEFAULT_DB_ALIAS, router


def _get_models():
    from ..models import GenericContentType, get_current_project_name

    return GenericContentType, get_current_project_name


def create_generic_contenttypes(
    app_config,
    verbosity=2,
    using=DEFAULT_DB_ALIAS,
    **kwargs,
):
    if not app_config.models_module:
        return
    GenericContentTypeModel, get_current_project_name = _get_models()
    if not router.allow_migrate_model(using, GenericContentTypeModel):
        return
    project = get_current_project_name()
    for model in app_config.get_models():
        GenericContentTypeModel.objects.get_or_create(
            project=project,
            app_label=app_config.label,
            model=model._meta.model_name,
        )
        if verbosity >= 2:
            print(
                "Adding generic content type "
                f"'{project}:{app_config.label} | {model._meta.model_name}'"
            )
