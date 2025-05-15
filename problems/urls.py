from django.urls import path
from . import views

urlpatterns = [
    path('create/manual/', views.create_manual_problem, name='create_manual_problem'),
]