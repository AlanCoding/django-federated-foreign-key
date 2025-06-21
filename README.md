# django-federated-foreign-key
A GenericForeignKey drop-in with ability to point to items in another server

## GenericForeignKey

A generic foreign key allows pointing to objects of any type.
To do this, it uses 2 existing fields on the model:
 - A reference to a `ContentType` entry and
 - An id of the related object

https://docs.djangoproject.com/en/5.2/ref/contrib/contenttypes/#django.contrib.contenttypes.fields.GenericForeignKey

## Difference for Federated Foreign Key

The limitation that we are addressing here is that `ContentType` is only designed to
reference models that exist within the local system.
It is also taken as obvious that the `object_id` (the related object id) is the id
of the object, in the related table, in the same database.

The intent of a federated foreign key is to provide the same interface,
but expand this to allow referencing objects in different databases.

## Usage

Add `federated_foreign_key` to `INSTALLED_APPS` and define `FEDERATION_PROJECT_NAME` in your Django settings:

```python
FEDERATION_PROJECT_NAME = 'project_a'
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'federated_foreign_key',
    # your apps...
]
```

Use `FederatedForeignKey` in place of `GenericForeignKey` together with `GenericContentType`.
