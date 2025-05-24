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
    problems = Problem.objects.filter(user=request.user).order_by('-date_created')
    return render(request, 'users/dashboard.html', {
        'problems': problems
    })
