from django.http import JsonResponse
from .models import Book


def book_list(request):
    data = [{"id": b.id, "title": b.title} for b in Book.objects.all()]
    return JsonResponse(data, safe=False)


def book_detail(request, pk):
    book = Book.objects.get(pk=pk)
    return JsonResponse({"id": book.id, "title": book.title})
