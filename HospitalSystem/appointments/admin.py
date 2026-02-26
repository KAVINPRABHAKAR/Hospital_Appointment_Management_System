from django.contrib import admin
from .models import Department, Doctor, Appointment

# Customizing the Admin Header
admin.site.site_header = "MedQueue Pro Administration"
admin.site.site_title = "OPD Admin Portal"
admin.site.index_title = "Hospital Management System"

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    # Displaying linked User and Department in the list
    list_display = ('name', 'user', 'department', 'room_number')
    list_filter = ('department',)
    search_fields = ('name', 'user__username')
    
    # Organization for the editing form
    fieldsets = (
        ('Personal Info', {
            'fields': ('name', 'department')
        }),
        ('Clinic Details', {
            'fields': ('room_number',)
        }),
        ('Login Credentials', {
            'fields': ('user',),
            'description': 'Link this doctor to a User account for private queue access.'
        }),
    )

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    # Professional list view with status colors
    list_display = ('token_number', 'patient_name', 'doctor', 'is_emergency', 'status', 'registration_time')
    list_filter = ('status', 'doctor', 'is_emergency', 'registration_time')
    search_fields = ('patient_name', 'token_number')
    list_editable = ('status',) # Allows changing status directly from the list view
    readonly_fields = ('token_number', 'registration_time', 'estimated_time')
    
    # Sorting by emergency first
    ordering = ('-is_emergency', 'registration_time')

    # Adding custom action to mark multiple patients as consulted
    actions = ['make_consulted']

    @admin.action(description='Mark selected appointments as Consulted')
    def make_consulted(self, request, queryset):
        queryset.update(status='Consulted')