"""
URL configuration for linearis_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Inclure les URLs d'authentification de Django
    path('accounts/', include('django.contrib.auth.urls')), # Fournit login, logout, password change/reset URLs
    path('users/', include('users.urls')),
    # path('problems/', include('problems.urls')), # Exemple

    # Ajouter une page d'accueil simple pour l'instant
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
]
