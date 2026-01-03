"""
Configuración del admin para terceros.
"""
from django.contrib import admin
from .models import ThirdParty, ThirdPartyVehicle


class ThirdPartyVehicleInline(admin.TabularInline):
    """Inline para vehículos de un tercero"""
    model = ThirdPartyVehicle
    extra = 1
    fields = ['plate', 'vehicle_type', 'brand', 'color', 'is_primary', 'is_active']


@admin.register(ThirdParty)
class ThirdPartyAdmin(admin.ModelAdmin):
    """Admin para terceros"""
    list_display = [
        'full_name',
        'document_type',
        'document_number',
        'phone',
        'email',
        'is_active',
        'tenant'
    ]
    list_filter = ['is_active', 'document_type', 'tenant']
    search_fields = ['first_name', 'last_name', 'document_number', 'email', 'phone']
    ordering = ['last_name', 'first_name']
    inlines = [ThirdPartyVehicleInline]
    
    fieldsets = (
        ('Identificación', {
            'fields': ('document_type', 'document_number')
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'address')
        }),
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Estado', {
            'fields': ('is_active', 'notes')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(ThirdPartyVehicle)
class ThirdPartyVehicleAdmin(admin.ModelAdmin):
    """Admin para vehículos"""
    list_display = [
        'plate',
        'third_party',
        'vehicle_type',
        'brand',
        'color',
        'is_primary',
        'is_active'
    ]
    list_filter = ['vehicle_type', 'is_primary', 'is_active']
    search_fields = ['plate', 'brand', 'third_party__first_name', 'third_party__last_name']
    autocomplete_fields = ['third_party']
