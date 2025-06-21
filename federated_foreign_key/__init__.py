from importlib import import_module

DEFAULT_APP_CONFIG = "federated_foreign_key.apps.FederatedForeignKeyConfig"

__all__ = [
    "FederatedForeignKey",
    "RemoteObject",
    "GenericContentType",
    "get_current_project_name",
]


def __getattr__(name):
    if name in __all__:
        if name in ["FederatedForeignKey", "RemoteObject"]:
            module_name = "federated_foreign_key.fields"
        else:
            module_name = "federated_foreign_key.models"
        module = import_module(module_name)
        return getattr(module, name)
    raise AttributeError(name)
