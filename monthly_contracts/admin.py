"""
Configuración del admin para contratos mensuales.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import MonthlyContract, ContractVehicle, ContractPayment


class ContractVehicleInline(admin.TabularInline):
    """Inline para vehículos de un contrato"""
    model = ContractVehicle
    extra = 1
    fields = ['vehicle', 'category', 'monthly_rate', 'is_active', 'notes']
    autocomplete_fields = ['vehicle', 'category']


class ContractPaymentInline(admin.TabularInline):
    """Inline para pagos de un contrato"""
    model = ContractPayment
    extra = 0
    readonly_fields = ['payment_date']
    fields = ['amount', 'payment_method', 'payment_month', 'payment_year', 'reference', 'is_confirmed', 'payment_date']


@admin.register(MonthlyContract)
class MonthlyContractAdmin(admin.ModelAdmin):
    """Admin para contratos mensuales"""
    list_display = [
        'third_party',
        'get_vehicles',
        'start_date',
        'end_date',
        'get_monthly_rate',
        'get_status_display',
        'get_days_remaining',
        'tenant'
    ]
    list_filter = ['status', 'is_active', 'tenant']
    search_fields = [
        'third_party__first_name',
        'third_party__last_name',
        'third_party__document_number',
        'vehicles__vehicle__plate'
    ]
    date_hierarchy = 'start_date'
    ordering = ['-start_date']
    inlines = [ContractVehicleInline, ContractPaymentInline]
    autocomplete_fields = ['third_party']
    
    fieldsets = (
        ('Cliente', {
            'fields': ('third_party',)
        }),
        ('Período', {
            'fields': ('start_date', 'end_date')
        }),
        ('Estado', {
            'fields': ('status', 'is_active', 'auto_renew', 'notes')
        }),
        ('Tenant', {
            'fields': ('tenant',)
        }),
    )
    
    def get_vehicles(self, obj):
        """Muestra los vehículos del contrato"""
        vehicles = obj.vehicles.all()
        if vehicles:
            return ", ".join([v.vehicle.plate for v in vehicles])
        return "-"
    get_vehicles.short_description = 'Vehículos'
    
    def get_monthly_rate(self, obj):
        """Muestra la tarifa mensual total"""
        return f"${obj.monthly_rate:,.0f}"
    get_monthly_rate.short_description = 'Tarifa Mensual'
    
    def get_status_display(self, obj):
        """Muestra el estado con color"""
        colors = {
            'active': 'green',
            'expired': 'red',
            'cancelled': 'gray',
            'pending': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    get_status_display.short_description = 'Estado'
    
    def get_days_remaining(self, obj):
        """Muestra días restantes"""
        days = obj.days_until_expiry()
        if days == 0:
            return format_html('<span style="color: red;">Vencido</span>')
        elif days <= 5:
            return format_html('<span style="color: orange;">{} días</span>', days)
        return f"{days} días"
    get_days_remaining.short_description = 'Días restantes'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superadmin:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()


@admin.register(ContractVehicle)
class ContractVehicleAdmin(admin.ModelAdmin):
    """Admin para vehículos de contratos"""
    list_display = ['vehicle', 'contract', 'category', 'monthly_rate', 'is_active']
    list_filter = ['is_active', 'category']
    search_fields = ['vehicle__plate', 'contract__third_party__first_name']
    autocomplete_fields = ['contract', 'vehicle', 'category']


@admin.register(ContractPayment)
class ContractPaymentAdmin(admin.ModelAdmin):
    """Admin para pagos de contratos"""
    list_display = [
        'contract',
        'amount',
        'payment_method',
        'payment_month',
        'payment_year',
        'is_confirmed',
        'payment_date',
        'received_by'
    ]
    list_filter = ['payment_method', 'is_confirmed', 'payment_date', 'payment_year']
    search_fields = ['contract__third_party__first_name', 'reference']
    date_hierarchy = 'payment_date'
    ordering = ['-payment_date']
    readonly_fields = ['payment_date']
