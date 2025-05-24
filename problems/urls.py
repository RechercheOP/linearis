from django.urls import path
from . import views

urlpatterns = [
    path('create/manual/', views.create_manual_problem, name='create_manual_problem'),
    path('problem/<int:pk>/', views.problem_detail, name='problem_detail'),
    path('problem/<int:pk>/solve/', views.solve_problem, name='solve_problem'),
    path('import/', views.import_problem, name='import_problem'),
]