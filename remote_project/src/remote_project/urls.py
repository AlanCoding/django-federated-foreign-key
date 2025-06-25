from django.urls import path
from remote_project.remoteapp import views

urlpatterns = [
    path("books/", views.book_list, name="book-list"),
    path("books/<int:pk>/", views.book_detail, name="book-detail"),
]
