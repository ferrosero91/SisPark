"""
Configuración del admin para la app parking.
"""
from django.contrib import admin
from .models import VehicleCategory, ParkingTicket, Caja, CashMovement


@admin.register(VehicleCategory)
class VehicleCategoryAdmin(admin.ModelAdmin):
    """Admin para categorías de vehículos"""
    list_display = ['name', 'tenant', 'first_hour_rate', 'additional_hour_rate', 'is_monthly', 'monthly_rate']
    search_fields = ['name']
    list_filter = ['is_monthly', 'tenant']
    ordering = ['tenant', 'name']


@admin.register(ParkingTicket)
class ParkingTicketAdmin(admin.ModelAdmin):
    """Admin para tickets de parqueo"""
    list_display = [
        'ticket_number',
        'placa',
        'category',
        'tenant',
        'entry_time',
        'exit_time',
        'amount_paid',
        'is_monthly_entry',
        'get_status_display'
    ]
    list_filter = ['category', 'entry_time', 'tenant', 'is_monthly_entry']
    search_fields = ['placa', 'marca', 'color', 'ticket_number']
    date_hierarchy = 'entry_time'
    ordering = ['-entry_time']
    readonly_fields = ['ticket_id', 'ticket_number', 'entry_time', 'barcode']
    
    def get_status_display(self, obj):
        """Muestra si el ticket está activo o cerrado"""
        return "Activo" if obj.exit_time is None else "Cerrado"
    get_status_display.short_description = 'Estado'


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    """Admin para caja"""
    list_display = [
        'fecha',
        'tenant',
        'tipo',
        'monto',
        'dinero_inicial',
        'dinero_final',
        'cuadre_realizado'
    ]
    list_filter = ['tipo', 'cuadre_realizado', 'fecha', 'tenant']
    date_hierarchy = 'fecha'
    ordering = ['-fecha']


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    """Admin para movimientos de caja"""
    list_display = ['caja', 'movement_type', 'amount', 'description', 'created_at', 'created_by']
    list_filter = ['movement_type', 'created_at', 'tenant']
    search_fields = ['description']
    ordering = ['-created_at']
