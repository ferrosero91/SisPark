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
        max_digits=6, decimal_places=2, default=0,
        verbose_name="Tarifa primera hora"
    )
    additional_hour_rate = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
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
        code = Code128(self.placa, writer=ImageWriter())
        code.write(buffer)
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
        
        # Generar el código de barras con la placa si no existe
        if not self.barcode:
            code = barcode.Code128(self.placa, writer=ImageWriter())
            buffer = BytesIO()
            code.write(buffer)
            self.barcode.save(
                f'barcode_{self.placa}.png',
                File(buffer),
                save=False
            )
        
        # Asegurarse de que entry_time tenga un valor
        if not self.entry_time:
            self.entry_time = timezone.now()
        
        # Si es categoría mensual y no tiene fecha de vencimiento
        if self.category.is_monthly and not self.monthly_expiry:
            self.monthly_expiry = self.entry_time + timedelta(days=30)
        
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