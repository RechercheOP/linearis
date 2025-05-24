from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views import generic
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from problems.models import Problem


class RegisterView(generic.CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'registration/register.html'


@login_required
def dashboard(request):
    # Récupérer les problèmes normaux
    normal_problems = Problem.objects.filter(
        user=request.user,
        importedproblem__isnull=True
    ).order_by('-date_created')
    
    # Récupérer les problèmes importés
    imported_problems = Problem.objects.filter(
        user=request.user,
        importedproblem__isnull=False  # Inclure uniquement les problèmes importés
    ).order_by('-date_created')
    
    total_problems = normal_problems.count()
    total_imported = imported_problems.count()
    
    return render(request, 'users/dashboard.html', {
        'normal_problems': normal_problems,
        'imported_problems': imported_problems,
        'total_problems' : total_problems,
        'total_imported' : total_imported
    })
