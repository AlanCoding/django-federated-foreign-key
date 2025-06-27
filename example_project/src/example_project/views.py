from django.http import JsonResponse

from example_project.testapp.models import Reference


def unified_books(request):
    """Return a list of local and remote books using ``Reference`` objects."""

    books = []
    for ref in Reference.objects.all().select_related("content_type"):
        obj = ref.content_object
        if hasattr(obj, "fetch"):
            data = obj.fetch()
            books.append(
                {"id": obj.object_id, "title": data["title"], "source": "remote"}
            )
        else:
            books.append({"id": obj.pk, "title": obj.title, "source": "local"})
    return JsonResponse(books, safe=False)
