from importlib import import_module

DEFAULT_APP_CONFIG = "federated_foreign_key.apps.FederatedForeignKeyConfig"

__all__ = [
    "FederatedForeignKey",
    "RemoteObject",
    "get_remote_object_class",
    "GenericContentType",
    "get_current_project_name",
    "FederatedRelation",
    "FederatedPrefetch",
    "shortcut",
]


def __getattr__(name):
    if name in __all__:
        if name in [
            "FederatedForeignKey",
            "RemoteObject",
            "get_remote_object_class",
            "FederatedRelation",
        ]:
            module_name = "federated_foreign_key.fields"
        elif name == "FederatedPrefetch":
            module_name = "federated_foreign_key.prefetch"
        elif name == "shortcut":
            module_name = "federated_foreign_key.views"
        else:
            module_name = "federated_foreign_key.models"
        module = import_module(module_name)
        return getattr(module, name)
    raise AttributeError(name)
