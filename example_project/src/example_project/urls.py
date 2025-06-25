from django.urls import path
from . import views

urlpatterns = [
    path("books/", views.unified_books, name="unified-books"),
]
