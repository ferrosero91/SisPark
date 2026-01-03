from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'business_name', 'status', 'is_active', 'created_at']
    list_filter = ['status', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'business_name', 'nit', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'name', 'slug')
        }),
        ('Información de la Empresa', {
            'fields': ('business_name', 'nit', 'phone', 'email', 'address', 'city', 'logo')
        }),
        ('Estado', {
            'fields': ('status', 'is_active', 'trial_ends_at')
        }),
        ('Configuración', {
            'fields': ('settings',),
            'classes': ('collapse',)
        }),
        ('Notas Internas', {
            'fields': ('internal_notes',),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
