"""
Configuración del admin para contratos mensuales.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import MonthlyContract, ContractPayment


class ContractPaymentInline(admin.TabularInline):
    """Inline para pagos de un contrato"""
    model = ContractPayment
    extra = 0
    readonly_fields = ['payment_date']
    fields = ['amount', 'payment_method', 'months_paid', 'reference', 'is_confirmed', 'payment_date']


@admin.register(MonthlyContract)
class MonthlyContractAdmin(admin.ModelAdmin):
    """Admin para contratos mensuales"""
    list_display = [
        'vehicle',
        'third_party',
        'start_date',
        'end_date',
        'monthly_rate',
        'get_status_display',
        'get_days_remaining',
        'tenant'
    ]
    list_filter = ['status', 'is_active', 'tenant', 'category']
    search_fields = [
        'vehicle__plate',
        'third_party__first_name',
        'third_party__last_name',
        'third_party__document_number'
    ]
    date_hierarchy = 'start_date'
    ordering = ['-start_date']
    inlines = [ContractPaymentInline]
    autocomplete_fields = ['third_party', 'vehicle', 'category']
    
    fieldsets = (
        ('Información del Contrato', {
            'fields': ('third_party', 'vehicle', 'category')
        }),
        ('Período', {
            'fields': ('start_date', 'end_date')
        }),
        ('Tarifa', {
            'fields': ('monthly_rate',)
        }),
        ('Estado', {
            'fields': ('status', 'is_active', 'notes')
        }),
        ('Tenant', {
            'fields': ('tenant',)
        }),
    )
    
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


@admin.register(ContractPayment)
class ContractPaymentAdmin(admin.ModelAdmin):
    """Admin para pagos de contratos"""
    list_display = [
        'contract',
        'amount',
        'payment_method',
        'months_paid',
        'is_confirmed',
        'payment_date',
        'received_by'
    ]
    list_filter = ['payment_method', 'is_confirmed', 'payment_date']
    search_fields = ['contract__vehicle__plate', 'reference']
    date_hierarchy = 'payment_date'
    ordering = ['-payment_date']
    readonly_fields = ['payment_date']
