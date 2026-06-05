from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile

# Define an inline admin for UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('max_projects', 'phone_number')  # REMOVED max_alternatives

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_phone', 'is_staff', 'get_max_projects')  # REMOVED get_max_alternatives
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email')
    
    def get_max_projects(self, obj):
        try:
            return obj.profile.max_projects
        except UserProfile.DoesNotExist:
            return '-'
    
    def get_phone(self, obj):
        try:
            return obj.profile.phone_number
        except UserProfile.DoesNotExist:
            return 'Not provided'
    
    # REMOVED get_max_alternatives method completely
    
    get_max_projects.short_description = 'Project Limit'
    get_phone.short_description = 'Phone Number'

# Register the UserProfile model on its own
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'max_projects')  # REMOVED max_alternatives
    search_fields = ('user__username', 'user__email', 'phone_number')
    list_filter = ('max_projects',)  # REMOVED max_alternatives
    
    # Add ability to search by phone number
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        try:
            # Add phone number search
            queryset |= self.model.objects.filter(phone_number__icontains=search_term)
        except:
            pass
        return queryset, use_distinct

# Re-register UserAdmin to replace the default one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(UserProfile, UserProfileAdmin)