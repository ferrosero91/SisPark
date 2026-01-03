"""
Configuración del admin para auditoría.
"""
from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin para visualizar logs de auditoría"""
    
    list_display = [
        'timestamp',
        'user_email',
        'action',
        'object_repr',
        'ip_address',
        'tenant'
    ]
    list_filter = [
        'action',
        'timestamp',
        'tenant',
        'content_type'
    ]
    search_fields = [
        'user_email',
        'object_repr',
        'message',
        'ip_address'
    ]
    readonly_fields = [
        'id',
        'tenant',
        'user',
        'user_email',
        'action',
        'content_type',
        'object_id',
        'object_repr',
        'changes',
        'message',
        'ip_address',
        'user_agent',
        'timestamp'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Información General', {
            'fields': ('id', 'timestamp', 'action', 'message')
        }),
        ('Usuario', {
            'fields': ('user', 'user_email', 'tenant')
        }),
        ('Objeto Afectado', {
            'fields': ('content_type', 'object_id', 'object_repr')
        }),
        ('Cambios', {
            'fields': ('changes',),
            'classes': ('collapse',)
        }),
        ('Request', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """No permitir crear logs manualmente"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir editar logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Solo superadmins pueden eliminar logs"""
        return request.user.is_superadmin
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
