from django.contrib import admin
from .models import Problem

@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('nom', 'user', 'objective_type', 'date_created')
    list_filter = ('objective_type', 'date_created')
    search_fields = ('nom', 'description')
    date_hierarchy = 'date_created'