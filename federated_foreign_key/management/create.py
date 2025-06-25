from django.apps import apps as global_apps
from django.db import DEFAULT_DB_ALIAS, router


def get_generic_contenttypes_and_models(app_config, using, GenericContentType, project):
    if not router.allow_migrate_model(using, GenericContentType):
        return None, None

    clear_cache = getattr(GenericContentType.objects, "clear_cache", None)
    if clear_cache:
        clear_cache()

    content_types = {
        ct.model: ct
        for ct in GenericContentType.objects.using(using).filter(
            project=project, app_label=app_config.label
        )
    }
    app_models = {model._meta.model_name: model for model in app_config.get_models()}
    return content_types, app_models


def create_generic_contenttypes(
    app_config,
    verbosity=2,
    using=DEFAULT_DB_ALIAS,
    apps=global_apps,
    **kwargs,
):
    """Create generic content types for models in the given app."""
    if not app_config.models_module:
        return

    app_label = app_config.label
    try:
        app_config = apps.get_app_config(app_label)
        GenericContentType = apps.get_model(
            "federated_foreign_key", "GenericContentType"
        )
        from ..models import get_current_project_name
    except LookupError:
        return

    project = get_current_project_name()

    content_types, app_models = get_generic_contenttypes_and_models(
        app_config, using, GenericContentType, project
    )

    if not app_models:
        return

    cts = [
        GenericContentType(
            project=project,
            app_label=app_label,
            model=model_name,
        )
        for model_name in app_models
        if model_name not in content_types
    ]
    if not cts:
        return
    GenericContentType.objects.using(using).bulk_create(cts)
    if verbosity >= 2:
        for ct in cts:
            print(
                "Adding generic content type "
                f"'{ct.project}:{ct.app_label} | {ct.model}'"
            )
