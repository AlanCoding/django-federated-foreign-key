# django-federated-foreign-key
A `GenericForeignKey` drop-in replacement with ability to point to items in another server.
Install with pip:

```bash
pip install django-federated-foreign-key
```

[![PyPI version](https://img.shields.io/pypi/v/django-federated-foreign-key.svg)](https://pypi.org/project/django-federated-foreign-key/)

## GenericForeignKey

A `GenericForeignKey` allows pointing to objects of any type.
To do this, it uses 2 existing fields on the model:
 - A reference to a `ContentType` entry, usually named `content_type` and
 - An id of the related object, usually named `object_id`

https://docs.djangoproject.com/en/5.2/ref/contrib/contenttypes/#django.contrib.contenttypes.fields.GenericForeignKey

## Difference for Federated Foreign Key

The limitation that `FederatedForeignKey` address is that `ContentType` is only designed to
reference models that exist within the local system, and thus, `GenericForeignKey` as well.
It is taken as obvious that `object_id` (the related object id) is the id of the object, in another table, in the same database.

The intent of `FederatedForeignKey` is to provide the same interface,
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

### Example

```python
from federated_foreign_key.fields import FederatedForeignKey
from federated_foreign_key.models import GenericContentType

class Reference(models.Model):
    content_type = models.ForeignKey(GenericContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = FederatedForeignKey("content_type", "object_id")
```

#### Referencing a remote object

If the referenced item does not exist in the local database, `content_object`
becomes a `RemoteObject` placeholder. `GenericContentType.model_class()`
returns a stand‑in class that can be used for `isinstance` checks.

```python
remote_ct = GenericContentType.objects.create(
    project="project_b",
    app_label="testapp",
    model="book",
)
cls = remote_ct.model_class()
ref = Reference.objects.create(content_type=remote_ct, object_id=42)
assert isinstance(ref.content_object, cls)
```

### Development

Install development requirements and run linting and tests:

```bash
pip install -r requirements-dev.txt
pip install -e .
pip install -e example_project
ruff check .
flake8
pytest -q
# Run Django's contenttypes tests as shipped in `dj_tests/`
# Use --parallel=1 to avoid multiprocessing issues
python dj_tests/runtests.py contenttypes_tests --parallel=1
```

## Demo

Run the included `run_demo.sh` script to start two demo servers.
The main `example_project` exposes `/books/` which lists local books and
books fetched from the `remote_project` server. SQLite database files are
created in each project directory when the script sets the `DATABASE_NAME`
environment variable.

```bash
./run_demo.sh
```

Provided that is running, go visit in your browser the URL:

http://localhost:8000/books/

You should see the example_project showing the reqest,
but in the logs from the remote_project, it should show
requests coming from the example_project.
It shows the names being filled in with values from the remote server.

## Remote Model Use Cases

There are 3 cases that this is likely to be used for.
This library doesn't provide you with everything you need, just the relationship
to store a `content_object` that may be non-local.

1. Same model, different servers, different data
2. Shared model, different servers, different data
3. Different model, on remote server

### Same model, different servers

This is what is illustrated in the demo.
Consider that you have 2 book shops, and they both have their own listings of books.
A book listing will be duplicate, in the sense that both entries reference the same book.
But maybe the two shops have different prices.
This helps present a unified list of shopping options for books.
Each entry could have its own shopping cart icon, to buy that book from that server, at that cost.

In this case, you would need to create a `GenericContentType` for the remote model.
This can have the same (app_label, model_name) as the local model, which is also a `GenericContentType`.
However, the model is also unique on project name, so this is allowed.

### Synchronized tables

In this case we assume a table is sychronized by some other mechanism.
This is not in scope of this project, but could be done by something like the DAB resource_registry app.

https://github.com/ansible/django-ansible-base/tree/devel/ansible_base/resource_registry

To avoid setting a specific owner of the table, a value of "shared" for the project name
will signify that all servers should treat the item as a local object (within the same DB).

### Different model on remote server

Finally, it would likely to useful to reference a model that doesn't exist locally.
Say that you were a book shop, but you didn't cary any audiobooks.
Perhaps another server has an `Audiobook` model, and you want to reference audiobooks.

This is a good example of where you would need to create a `GenericContentType`,
where the (app_label, model_name) combination does not exist locally.

## Illustration

This shows how FederatedForeignKey works compared to GenericForeignKey.

The `object_id` values specify the row location in all cases.

```mermaid
graph TD
  %% First scenario: GenericForeignKey
  subgraph GenericForeignKey
    GFKPointerTable[Generic FK Table]
    ContentType[ContentType Table]
    TargetTable[Target Model Table]

    GFKPointerTable -->|content_type_id| ContentType
    GFKPointerTable -->|object_id| TargetTable
  end

  %% Second scenario: FederatedForeignKey
  subgraph FederatedForeignKey
    FFKPointerTable[Federated FK Table]
    GenericContentType[GenericContentType Table]
    LocalTargetTable[Local Target Table]

    FFKPointerTable -->|generic_content_type_id| GenericContentType
    FFKPointerTable -->|object_id| LocalTargetTable
  end

  subgraph External Database
    RemoteTargetTable[Remote Target Table]
  end

  FFKPointerTable -->|object_id| RemoteTargetTable
```

