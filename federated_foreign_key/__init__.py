DEFAULT_APP_CONFIG = 'federated_foreign_key.apps.FederatedForeignKeyConfig'

__all__ = ['FederatedForeignKey', 'RemoteObject', 'GenericContentType', 'get_current_project_name']

from importlib import import_module


def __getattr__(name):
    if name in __all__:
        module = import_module('federated_foreign_key.fields' if name in ['FederatedForeignKey', 'RemoteObject'] else 'federated_foreign_key.models')
        return getattr(module, name)
    raise AttributeError(name)
