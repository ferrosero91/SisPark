from django.db import models
import uuid
import math
from django.utils import timezone
from datetime import timedelta
from io import BytesIO
from django.core.files import File
import barcode
from barcode.writer import ImageWriter
import base64
from barcode import Code128

from tenants.managers import TenantModel, TenantManager

# Importar modelos de configuración
from .models_config import PaymentMethod, Currency


class VehicleCategory(TenantModel):
    """
    Categorías de vehículos por tenant.
    Cada parqueadero define sus propias categorías y tarifas.
    """
    name = models.CharField(max_length=50, verbose_name="Nombre")
    first_hour_rate = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name="Tarifa primera hora"
    )
    additional_hour_rate = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name="Tarifa hora adicional"
    )
    is_monthly = models.BooleanField(default=False, verbose_name="Es mensualidad")
    monthly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Tarifa mensual"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Categoría de Vehículo"
        verbose_name_plural = "Categorías de Vehículos"
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_category_per_tenant'
            )
        ]

class ParkingTicket(TenantModel):
    """
    Ticket de estacionamiento multitenant.
    Incluye soporte para terceros y contratos mensuales.
    """
    ticket_id = models.UUIDField(default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(
        max_length=20, blank=True,
        verbose_name="Número de ticket"
    )
    category = models.ForeignKey(
        'VehicleCategory', on_delete=models.CASCADE,
        verbose_name="Categoría"
    )
    placa = models.CharField(max_length=20, verbose_name="Placa")
    color = models.CharField(max_length=50, verbose_name="Color")
    marca = models.CharField(max_length=50, verbose_name="Marca")
    cascos = models.IntegerField(null=True, blank=True, verbose_name="Cascos")
    entry_time = models.DateTimeField(auto_now_add=True, verbose_name="Hora entrada")
    exit_time = models.DateTimeField(null=True, blank=True, verbose_name="Hora salida")
    amount_paid = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Monto pagado"
    )
    payment_method = models.ForeignKey(
        'parking.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tickets',
        verbose_name="Método de pago"
    )
    barcode = models.ImageField(upload_to='barcodes/', blank=True)
    monthly_expiry = models.DateTimeField(null=True, blank=True)
    
    # Relaciones con terceros y contratos mensuales
    third_party = models.ForeignKey(
        'third_parties.ThirdParty',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Tercero"
    )
    monthly_contract = models.ForeignKey(
        'monthly_contracts.MonthlyContract',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Contrato mensual"
    )
    is_monthly_entry = models.BooleanField(
        default=False,
        verbose_name="Entrada con mensualidad"
    )

    class Meta:
        verbose_name = "Ticket de Estacionamiento"
        verbose_name_plural = "Tickets de Estacionamiento"
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'placa'],
                condition=models.Q(exit_time__isnull=True),
                name='unique_active_plate_per_tenant'
            )
        ]

    def __str__(self):
        return f"{self.placa} - {self.entry_time.strftime('%Y-%m-%d %H:%M')}"
    
    def get_barcode_base64(self):
        buffer = BytesIO()
        # Configurar barras más gruesas para impresoras térmicas
        options = {
            'module_width': 0.4,      # Ancho de cada barra (más grueso)
            'module_height': 12.0,    # Altura del código
            'quiet_zone': 2.0,        # Zona silenciosa
            'font_size': 10,          # Tamaño de fuente
            'text_distance': 3.0,     # Distancia del texto
            'write_text': False,      # No escribir texto debajo (ya lo ponemos en HTML)
        }
        code = Code128(self.placa, writer=ImageWriter())
        code.write(buffer, options=options)
        base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{base64_data}'

    def generate_ticket_number(self):
        """Genera número de ticket único por tenant"""
        today = timezone.now()
        prefix = today.strftime('%Y%m%d')
        
        # Contar tickets del día para este tenant
        if self.tenant_id:
            count = ParkingTicket.objects.filter(
                tenant=self.tenant,
                entry_time__date=today.date()
            ).count()
        else:
            count = ParkingTicket.objects.filter(
                entry_time__date=today.date()
            ).count()
        
        return f"{prefix}-{count + 1:04d}"

    def save(self, *args, **kwargs):
        # Generar número de ticket si no existe (después de asignar tenant)
        if not self.ticket_number and self.tenant_id:
            self.ticket_number = self.generate_ticket_number()
        elif not self.ticket_number:
            # Generar un número temporal si no hay tenant aún
            today = timezone.now()
            self.ticket_number = f"{today.strftime('%Y%m%d')}-TEMP"
        
        # Ya no guardamos barcode en disco - usamos get_barcode_base64() en los templates
        
        # Asegurarse de que entry_time tenga un valor
        if not self.entry_time:
            self.entry_time = timezone.now()
        
        # Si es categoría mensual y no tiene fecha de vencimiento
        if self.category.is_monthly and not self.monthly_expiry:
            self.monthly_expiry = self.entry_time + timedelta(days=30)
        
        # Si se está registrando salida, borrar imagen de barcode si existe
        if self.exit_time and self.barcode:
            try:
                self.barcode.delete(save=False)
            except Exception:
                pass
        
        super().save(*args, **kwargs)

    def calculate_fee(self):
        """Calcula la tarifa considerando contratos mensuales"""
        if self.exit_time:
            # Si tiene contrato mensual vigente, no cobra
            if self.is_monthly_entry and self.monthly_contract:
                if self.monthly_contract.is_valid():
                    return 0.0
            
            # Lógica original para mensualidades por categoría
            if self.category.is_monthly and self.monthly_expiry and self.exit_time <= self.monthly_expiry:
                return float(self.category.monthly_rate or 0)
            
            duration = self.exit_time - self.entry_time
            hours = duration.total_seconds() / 3600

            total = float(self.category.first_hour_rate)
            if hours > 1:
                additional_hours = math.ceil(hours - 1)
                total += additional_hours * float(self.category.additional_hour_rate)

            return round(total, 2)
        return self.calculate_current_fee()

    def calculate_current_fee(self):
        """Calcula la tarifa actual considerando contratos mensuales"""
        if not self.exit_time:
            # Si tiene contrato mensual vigente, no cobra
            if self.is_monthly_entry and self.monthly_contract:
                if self.monthly_contract.is_valid():
                    return 0.0
            
            # Lógica original para mensualidades por categoría
            if self.category.is_monthly and self.monthly_expiry and timezone.now() <= self.monthly_expiry:
                return float(self.category.monthly_rate or 0)
            
            duration = timezone.now() - self.entry_time
            hours = duration.total_seconds() / 3600

            total = float(self.category.first_hour_rate)
            if hours > 1:
                additional_hours = math.ceil(hours - 1)
                total += additional_hours * float(self.category.additional_hour_rate)

            return round(total, 2)
        return 0

    def get_duration(self):
        if self.exit_time:
            duration = self.exit_time - self.entry_time
            return math.ceil(duration.total_seconds() / 3600)
        return self.get_current_duration()['hours']

    def get_current_duration(self):
        if not self.exit_time:
            duration = timezone.now() - self.entry_time
            hours = duration.total_seconds() // 3600
            minutes = (duration.total_seconds() % 3600) // 60
            return {'hours': int(hours), 'minutes': int(minutes)}
        return {'hours': 0, 'minutes': 0}

    def get_status(self):
        if not self.exit_time:
            duration = self.get_current_duration()
            current_fee = self.calculate_current_fee()
            monthly_status = None
            if self.category.is_monthly:
                monthly_status = 'Vigente' if timezone.now() <= self.monthly_expiry else 'Vencido'
            return {
                'duration': duration,
                'current_fee': current_fee,
                'is_active': True,
                'monthly_status': monthly_status
            }
        return {
            'duration': {'hours': 0, 'minutes': 0},
            'current_fee': self.amount_paid or 0,
            'is_active': False,
            'monthly_status': None
        }

# Al final del archivo, añade el modelo Caja si no está


class Caja(TenantModel):
    """
    Registro de caja diario por tenant.
    """
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha")
    tipo = models.CharField(
        max_length=50,
        choices=[('Ingreso', 'Ingreso'), ('Egreso', 'Egreso')],
        verbose_name="Tipo"
    )
    monto = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name="Monto"
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    dinero_inicial = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name="Dinero inicial"
    )
    dinero_final = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Dinero final"
    )
    cuadre_realizado = models.BooleanField(
        default=False,
        verbose_name="Cuadre realizado"
    )

    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'fecha', 'tipo'],
                name='unique_caja_per_tenant_date_type'
            )
        ]

    def __str__(self):
        return f"{self.fecha} - {self.tipo} - ${self.monto}"


class Turno(TenantModel):
    """
    Turno de trabajo por usuario.
    Cada usuario debe abrir un turno para poder registrar vehículos.
    Enlazado con el modelo Caja para el cuadre diario.
    """
    user = models.ForeignKey(
        'users.User', on_delete=models.CASCADE,
        related_name='turnos',
        verbose_name="Usuario"
    )
    caja = models.ForeignKey(
        'Caja', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='turnos',
        verbose_name="Caja del día"
    )
    start_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Hora de apertura"
    )
    end_time = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Hora de cierre"
    )
    initial_cash = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name="Dinero inicial"
    )
    final_cash = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Dinero final"
    )
    expected_cash = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Dinero esperado"
    )
    difference = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Diferencia"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Turno activo"
    )
    closed_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='turnos_cerrados',
        verbose_name="Cerrado por"
    )

    class Meta:
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"
        ordering = ['-start_time']

    def __str__(self):
        status = "Activo" if self.is_active else "Cerrado"
        return f"Turno de {self.user.get_full_name()} - {self.start_time.strftime('%d/%m/%Y %H:%M')} ({status})"

    def calculate_expected_cash(self):
        """Calcula el dinero esperado basado en ventas en efectivo durante el turno"""
        from decimal import Decimal
        
        if not self.start_time:
            return Decimal('0')
        
        end = self.end_time or timezone.now()
        
        # Tickets pagados en efectivo durante el turno
        tickets_cash = ParkingTicket.objects.all_tenants().filter(
            tenant=self.tenant,
            exit_time__gte=self.start_time,
            exit_time__lte=end,
            exit_time__isnull=False,
            amount_paid__isnull=False,
            payment_method__payment_type='cash'
        ).aggregate(total=models.Sum('amount_paid'))['total'] or Decimal('0')
        
        # Tickets sin método de pago (asumimos efectivo)
        tickets_no_method = ParkingTicket.objects.all_tenants().filter(
            tenant=self.tenant,
            exit_time__gte=self.start_time,
            exit_time__lte=end,
            exit_time__isnull=False,
            amount_paid__isnull=False,
            payment_method__isnull=True
        ).aggregate(total=models.Sum('amount_paid'))['total'] or Decimal('0')
        
        # Pagos de contratos en efectivo
        from monthly_contracts.models import ContractPayment
        contracts_cash = ContractPayment.objects.filter(
            tenant=self.tenant,
            payment_date__gte=self.start_time,
            payment_date__lte=end,
            is_confirmed=True,
            payment_method__payment_type='cash'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        return self.initial_cash + tickets_cash + tickets_no_method + contracts_cash

    def get_sales_summary(self):
        """Obtiene resumen de ventas del turno"""
        from decimal import Decimal
        from collections import defaultdict
        
        if not self.start_time:
            return {}
        
        end = self.end_time or timezone.now()
        
        # Tickets del turno
        tickets = ParkingTicket.objects.all_tenants().filter(
            tenant=self.tenant,
            exit_time__gte=self.start_time,
            exit_time__lte=end,
            exit_time__isnull=False,
            amount_paid__isnull=False
        ).select_related('payment_method')
        
        # Pagos de contratos del turno
        from monthly_contracts.models import ContractPayment
        contract_payments = ContractPayment.objects.filter(
            tenant=self.tenant,
            payment_date__gte=self.start_time,
            payment_date__lte=end,
            is_confirmed=True
        ).select_related('payment_method')
        
        # Agrupar por método de pago
        by_method = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
        
        for t in tickets:
            method = t.payment_method.name if t.payment_method else 'Efectivo'
            by_method[method]['count'] += 1
            by_method[method]['total'] += t.amount_paid or Decimal('0')
        
        for p in contract_payments:
            method = p.payment_method.name if p.payment_method else 'Efectivo'
            by_method[method]['count'] += 1
            by_method[method]['total'] += p.amount or Decimal('0')
        
        return {
            'tickets_count': tickets.count(),
            'tickets_total': sum(t.amount_paid or 0 for t in tickets),
            'contracts_count': contract_payments.count(),
            'contracts_total': sum(p.amount for p in contract_payments),
            'by_method': dict(by_method),
            'total': sum(t.amount_paid or 0 for t in tickets) + sum(p.amount for p in contract_payments)
        }
    
    def get_or_create_caja(self):
        """Obtiene o crea la caja del día para este turno"""
        from decimal import Decimal
        
        fecha = self.start_time.date() if self.start_time else timezone.now().date()
        
        caja, created = Caja.objects.get_or_create(
            tenant=self.tenant,
            fecha=fecha,
            tipo='Ingreso',
            defaults={
                'dinero_inicial': Decimal('0'),
                'monto': Decimal('0'),
                'descripcion': f'Caja del {fecha}'
            }
        )
        return caja


class CashMovement(TenantModel):
    """
    Movimientos de caja manuales (ingresos/egresos adicionales).
    """
    MOVEMENT_TYPES = [
        ('income', 'Ingreso'),
        ('expense', 'Egreso'),
    ]
    
    caja = models.ForeignKey(
        Caja, on_delete=models.CASCADE,
        related_name='movements',
        verbose_name="Caja"
    )
    movement_type = models.CharField(
        max_length=10, choices=MOVEMENT_TYPES,
        verbose_name="Tipo de movimiento"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Monto"
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Descripción"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Creado por"
    )

    class Meta:
        verbose_name = "Movimiento de Caja"
        verbose_name_plural = "Movimientos de Caja"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} - ${self.amount}"


class ExpenseCategory(TenantModel):
    """Categorías de gastos por tenant."""
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    is_active = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        verbose_name = "Categoría de Gasto"
        verbose_name_plural = "Categorías de Gastos"
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_expense_category_per_tenant'
            )
        ]

    def __str__(self):
        return self.name


class Expense(TenantModel):
    """Registro de gastos/salidas de dinero."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT,
        related_name='expenses',
        verbose_name="Categoría"
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Monto"
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Descripción"
    )
    date = models.DateField(
        default=timezone.now,
        verbose_name="Fecha"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expenses_created',
        verbose_name="Registrado por"
    )
    turno = models.ForeignKey(
        'Turno', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expenses',
        verbose_name="Turno"
    )
    notes = models.TextField(blank=True, verbose_name="Notas adicionales")

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.category.name} - ${self.amount} - {self.date}"
