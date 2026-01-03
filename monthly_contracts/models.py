"""
Modelos para gestión de contratos mensuales.
"""
from django.db import models
from django.utils import timezone
from tenants.managers import TenantModel
from datetime import timedelta
from decimal import Decimal
import uuid


class MonthlyContract(TenantModel):
    """
    Contrato de mensualidad para un vehículo.
    """
    
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Activo'
        EXPIRED = 'expired', 'Vencido'
        CANCELLED = 'cancelled', 'Cancelado'
        PENDING = 'pending', 'Pendiente de pago'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Relaciones
    third_party = models.ForeignKey(
        'third_parties.ThirdParty',
        on_delete=models.CASCADE,
        related_name='contracts',
        verbose_name="Tercero"
    )
    vehicle = models.ForeignKey(
        'third_parties.ThirdPartyVehicle',
        on_delete=models.CASCADE,
        related_name='contracts',
        verbose_name="Vehículo"
    )
    category = models.ForeignKey(
        'parking.VehicleCategory',
        on_delete=models.PROTECT,
        related_name='monthly_contracts',
        verbose_name="Categoría"
    )
    
    # Período del contrato
    start_date = models.DateField(
        verbose_name="Fecha de inicio"
    )
    end_date = models.DateField(
        verbose_name="Fecha de fin"
    )
    
    # Tarifa
    monthly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Tarifa mensual"
    )
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Estado"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    # Auto-renovación
    auto_renew = models.BooleanField(
        default=False,
        verbose_name="Renovación automática"
    )
    
    # Tipo de contrato
    contract_type = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Mensual'),
            ('biweekly', 'Quincenal'),
            ('weekly', 'Semanal'),
            ('daily', 'Diario'),
        ],
        default='monthly',
        verbose_name="Tipo de contrato"
    )
    
    # Notas
    notes = models.TextField(
        blank=True,
        verbose_name="Notas"
    )
    
    # Fechas de auditoría
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_contracts',
        verbose_name="Creado por"
    )
    
    class Meta:
        verbose_name = "Contrato Mensual"
        verbose_name_plural = "Contratos Mensuales"
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.vehicle.plate} - {self.start_date} a {self.end_date}"
    
    def calculate_status(self):
        """Calcula el estado actual del contrato basado en fechas y pagos."""
        today = timezone.now().date()
        
        if not self.is_active:
            return self.Status.CANCELLED
        
        if today > self.end_date:
            return self.Status.EXPIRED
        
        if not self.payments.filter(is_confirmed=True).exists():
            return self.Status.PENDING
        
        return self.Status.ACTIVE
    
    def update_status(self):
        """Actualiza el estado del contrato"""
        new_status = self.calculate_status()
        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])
    
    def is_valid(self, check_date=None):
        """Verifica si el contrato es válido para una fecha específica."""
        if check_date is None:
            check_date = timezone.now().date()
        
        return (
            self.is_active and
            self.status == self.Status.ACTIVE and
            self.start_date <= check_date <= self.end_date
        )
    
    def days_until_expiry(self):
        """Retorna los días hasta el vencimiento"""
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        return (self.end_date - today).days
    
    def is_expiring_soon(self, days=5):
        """Verifica si el contrato está por vencer"""
        return 0 < self.days_until_expiry() <= days
    
    def get_balance(self):
        """Calcula el saldo pendiente del contrato"""
        total_paid = self.payments.filter(is_confirmed=True).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        return self.monthly_rate - total_paid
    
    def get_total_paid(self):
        """Total pagado en este contrato"""
        return self.payments.filter(is_confirmed=True).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
    
    def renew(self, months=1):
        """Renueva el contrato por un número de meses."""
        today = timezone.now().date()
        
        # Si el contrato ya venció, empezar desde hoy
        if self.end_date < today:
            self.start_date = today
            new_end_date = today + timedelta(days=30 * months)
        else:
            new_end_date = self.end_date + timedelta(days=30 * months)
        
        self.end_date = new_end_date
        self.status = self.Status.ACTIVE
        self.save()
        
        return self
    
    @classmethod
    def get_expiring_contracts(cls, tenant, days=5):
        """Obtiene contratos que vencen en los próximos días."""
        today = timezone.now().date()
        end_threshold = today + timedelta(days=days)
        
        return cls.objects.filter(
            tenant=tenant,
            is_active=True,
            status=cls.Status.ACTIVE,
            end_date__gte=today,
            end_date__lte=end_threshold
        )
    
    @classmethod
    def get_pending_payments(cls, tenant):
        """Obtiene contratos con pagos pendientes o vencidos."""
        today = timezone.now().date()
        return cls.objects.all_tenants().filter(
            tenant=tenant,
            is_active=True,
            status__in=[cls.Status.PENDING, cls.Status.EXPIRED]
        ).select_related('third_party', 'vehicle', 'category')


class ContractPayment(models.Model):
    """
    Registro de pagos de contratos mensuales.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    contract = models.ForeignKey(
        MonthlyContract,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name="Contrato"
    )
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='contract_payments',
        null=True,
        blank=True,
        verbose_name="Parqueadero"
    )
    
    # Método de pago (referencia al PaymentMethod configurado)
    payment_method = models.ForeignKey(
        'parking.PaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contract_payments',
        verbose_name="Método de pago"
    )
    
    # Información del pago
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Monto"
    )
    payment_date = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de pago"
    )
    
    # Para pagos en efectivo
    amount_received = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Monto recibido"
    )
    change_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Cambio"
    )
    
    # Referencia de pago (para transferencias, etc.)
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia"
    )
    
    # Meses pagados
    months_paid = models.PositiveIntegerField(
        default=1,
        verbose_name="Meses pagados"
    )
    
    # Período que cubre el pago
    period_start = models.DateField(
        null=True,
        blank=True,
        verbose_name="Inicio del período"
    )
    period_end = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fin del período"
    )
    
    # Confirmación
    is_confirmed = models.BooleanField(
        default=True,
        verbose_name="Confirmado"
    )
    
    # Notas
    notes = models.TextField(
        blank=True,
        verbose_name="Notas"
    )
    
    # Auditoría
    received_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_contract_payments',
        verbose_name="Recibido por"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    class Meta:
        verbose_name = "Pago de Contrato"
        verbose_name_plural = "Pagos de Contratos"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Pago ${self.amount} - {self.contract.vehicle.plate}"
    
    def save(self, *args, **kwargs):
        if not self.tenant_id and self.contract_id:
            self.tenant = self.contract.tenant
        
        # Calcular cambio si es efectivo
        if self.amount_received and self.amount:
            self.change_amount = self.amount_received - self.amount
        
        super().save(*args, **kwargs)
        
        # Actualizar estado del contrato después de guardar el pago
        if self.is_confirmed:
            self.contract.update_status()


class SpecialRate(TenantModel):
    """
    Tarifas especiales para terceros o grupos.
    Permite configurar descuentos, tarifas planas, etc.
    """
    
    class RateType(models.TextChoices):
        DISCOUNT = 'discount', 'Descuento porcentual'
        FLAT = 'flat', 'Tarifa plana'
        COURTESY = 'courtesy', 'Cortesía'
        DAILY_MAX = 'daily_max', 'Máximo diario'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name="Nombre de la tarifa"
    )
    
    # Puede aplicar a un tercero específico o a una categoría
    third_party = models.ForeignKey(
        'third_parties.ThirdParty',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='special_rates',
        verbose_name="Tercero"
    )
    
    category = models.ForeignKey(
        'parking.VehicleCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='special_rates',
        verbose_name="Categoría"
    )
    
    rate_type = models.CharField(
        max_length=20,
        choices=RateType.choices,
        default=RateType.DISCOUNT,
        verbose_name="Tipo de tarifa"
    )
    
    # Valor según el tipo
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Porcentaje de descuento"
    )
    
    flat_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Tarifa plana"
    )
    
    daily_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Máximo diario"
    )
    
    # Vigencia
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha inicio"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha fin"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Notas"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    class Meta:
        verbose_name = "Tarifa Especial"
        verbose_name_plural = "Tarifas Especiales"
        ordering = ['-created_at']
    
    def __str__(self):
        if self.third_party:
            return f"{self.name} - {self.third_party}"
        return self.name
    
    def is_valid(self, check_date=None):
        """Verifica si la tarifa está vigente"""
        if not self.is_active:
            return False
        
        if check_date is None:
            check_date = timezone.now().date()
        
        if self.start_date and check_date < self.start_date:
            return False
        
        if self.end_date and check_date > self.end_date:
            return False
        
        return True
    
    def calculate_amount(self, original_amount):
        """Calcula el monto final según el tipo de tarifa"""
        original = Decimal(str(original_amount))
        
        if self.rate_type == self.RateType.COURTESY:
            return Decimal('0')
        
        if self.rate_type == self.RateType.FLAT and self.flat_rate:
            return self.flat_rate
        
        if self.rate_type == self.RateType.DISCOUNT and self.discount_percent:
            discount = original * (self.discount_percent / 100)
            return original - discount
        
        if self.rate_type == self.RateType.DAILY_MAX and self.daily_max:
            return min(original, self.daily_max)
        
        return original
