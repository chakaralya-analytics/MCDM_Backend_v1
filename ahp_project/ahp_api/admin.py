from django.contrib import admin
from .models import AHPProject

class AHPProjectAdmin(admin.ModelAdmin):
    list_display = ['project_name', 'user', 'project_type', 'created_at', 'get_alternative_count']
    search_fields = ['project_name', 'user__username', 'user__email']
    list_filter = ['project_type']
    readonly_fields = ['consistency_ratio', 'get_alternative_count']

    def get_alternative_count(self, obj):
        """Display alternative count in admin list"""
        return obj.get_alternative_count()
    get_alternative_count.short_description = 'Alternatives'

admin.site.register(AHPProject, AHPProjectAdmin)