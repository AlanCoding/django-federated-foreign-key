import json
from urllib.request import urlopen
from django.http import JsonResponse
from example_project.testapp.models import Book


def unified_books(request):
    local = list(Book.objects.values("id", "title"))
    with urlopen("http://localhost:8001/books/") as resp:
        remote = json.load(resp)
    combined = [{"id": b["id"], "title": b["title"], "source": "local"} for b in local]
    combined += [
        {"id": b["id"], "title": b["title"], "source": "remote"} for b in remote
    ]
    return JsonResponse(combined, safe=False)
