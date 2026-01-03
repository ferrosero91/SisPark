"""
Configuración del admin para el sistema de permisos.
"""
from django.contrib import admin
from .models import Module, Role, RoleModulePermission, UserModulePermission


class RoleModulePermissionInline(admin.TabularInline):
    """Inline para permisos de módulos en roles"""
    model = RoleModulePermission
    extra = 1
    autocomplete_fields = ['module']


class UserModulePermissionInline(admin.TabularInline):
    """Inline para permisos directos de usuario"""
    model = UserModulePermission
    extra = 1
    autocomplete_fields = ['module']


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    """Admin para módulos del sistema"""
    list_display = ['name', 'code', 'parent', 'order', 'is_active', 'icon']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'code', 'description']
    ordering = ['order', 'name']
    list_editable = ['order', 'is_active']
    
    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'description')
        }),
        ('Navegación', {
            'fields': ('icon', 'url_name', 'order', 'parent')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin para roles"""
    list_display = ['name', 'tenant', 'is_default', 'created_at']
    list_filter = ['is_default', 'tenant']
    search_fields = ['name', 'description']
    inlines = [RoleModulePermissionInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'tenant')
        }),
        ('Configuración', {
            'fields': ('is_default',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(UserModulePermission)
class UserModulePermissionAdmin(admin.ModelAdmin):
    """Admin para permisos directos de usuario"""
    list_display = [
        'user', 
        'module', 
        'can_view', 
        'can_create', 
        'can_edit', 
        'can_delete'
    ]
    list_filter = ['module', 'can_view', 'can_create', 'can_edit', 'can_delete']
    search_fields = ['user__email', 'module__name']
    autocomplete_fields = ['user', 'module']
