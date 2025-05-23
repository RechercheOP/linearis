from django.contrib import admin
from .models import Problem

@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('nom', 'user', 'objective_type', 'num_variables', 'date_created')
    search_fields = ('nom', 'description')
    list_filter = ('objective_type', 'user')