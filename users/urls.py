from django.urls import path
from .views import RegisterView # Importer notre vue d'enregistrement

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
]