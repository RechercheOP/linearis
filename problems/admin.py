from django.contrib import admin
from .models import Problem, ImportedProblem

@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('nom', 'user', 'objective_type', 'date_created')
    list_filter = ('objective_type', 'date_created')
    search_fields = ('nom', 'description')
    date_hierarchy = 'date_created'

@admin.register(ImportedProblem)
class ImportedProblemAdmin(admin.ModelAdmin):
    list_display = ('nom', 'user', 'status', 'processing_started_at')
    list_filter = ('status', 'date_created')
    search_fields = ('nom', 'description', 'error_message')
    date_hierarchy = 'date_created'
    readonly_fields = ('processing_started_at', 'processing_completed_at', 'error_message')