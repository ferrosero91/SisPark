"""
Configuración del admin de Django para el modelo User.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin personalizado para el modelo User"""
    
    list_display = [
        'email', 
        'get_full_name', 
        'tenant', 
        'is_superadmin',
        'is_tenant_admin',
        'is_active',
        'get_lock_status',
        'last_login'
    ]
    list_filter = [
        'is_superadmin', 
        'is_tenant_admin', 
        'is_active', 
        'is_staff',
        'tenant'
    ]
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['email']
    
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'phone', 'avatar')
        }),
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Roles', {
            'fields': ('is_superadmin', 'is_tenant_admin', 'roles')
        }),
        ('Permisos Django', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Seguridad', {
            'fields': (
                'last_login_ip', 
                'failed_login_attempts', 
                'locked_until',
                'password_changed_at'
            ),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 
                'first_name', 
                'last_name',
                'password1', 
                'password2',
                'tenant',
                'is_superadmin',
                'is_tenant_admin'
            ),
        }),
    )
    
    readonly_fields = [
        'last_login', 
        'date_joined', 
        'last_login_ip',
        'failed_login_attempts',
        'locked_until',
        'password_changed_at'
    ]
    
    filter_horizontal = ['groups', 'user_permissions', 'roles']
    
    def get_lock_status(self, obj):
        """Muestra el estado de bloqueo de la cuenta"""
        if obj.is_locked():
            minutes = obj.get_lock_remaining_time()
            return format_html(
                '<span style="color: red;">🔒 Bloqueado ({} min)</span>',
                minutes
            )
        return format_html('<span style="color: green;">✓ Activo</span>')
    get_lock_status.short_description = 'Estado'
    
    def get_queryset(self, request):
        """Filtra usuarios según el contexto"""
        qs = super().get_queryset(request)
        # Los superadmins ven todos los usuarios
        if request.user.is_superadmin:
            return qs
        # Los admins de tenant solo ven usuarios de su tenant
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
