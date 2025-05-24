from django.urls import path
from .views import RegisterView # Importer notre vue d'enregistrement
from . import views

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
]