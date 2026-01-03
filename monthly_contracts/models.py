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
    Contrato de mensualidad para un cliente.
    Puede incluir múltiples vehículos con sus respectivas tarifas.
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
    
    # Cliente del contrato
    third_party = models.ForeignKey(
        'third_parties.ThirdParty',
        on_delete=models.CASCADE,
        related_name='contracts',
        verbose_name="Cliente"
    )
    
    # Período del contrato
    start_date = models.DateField(
        verbose_name="Fecha de inicio"
    )
    end_date = models.DateField(
        verbose_name="Fecha de fin"
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
    
    # Tarifa tipo combo (tarifa única para todos los vehículos)
    use_combo_rate = models.BooleanField(
        default=False,
        verbose_name="Usar tarifa combo",
        help_text="Si está activo, se usa una tarifa única en lugar de sumar las tarifas individuales"
    )
    combo_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Tarifa combo",
        help_text="Tarifa única mensual para todos los vehículos del contrato"
    )
    combo_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nombre del combo",
        help_text="Ej: 'Combo Familiar', 'Plan Empresarial'"
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
        return f"Contrato {self.third_party.full_name} - {self.start_date}"
    
    @property
    def monthly_rate(self):
        """Tarifa mensual total (combo o suma de vehículos)"""
        if self.use_combo_rate and self.combo_rate:
            return self.combo_rate
        return self.vehicles.filter(is_active=True).aggregate(
            total=models.Sum('monthly_rate')
        )['total'] or Decimal('0')
    
    @property
    def vehicles_list(self):
        """Lista de placas de vehículos"""
        return ", ".join([v.vehicle.plate for v in self.vehicles.all()])
    
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
    
    def get_total_paid(self):
        """Total pagado en este contrato"""
        return self.payments.filter(is_confirmed=True).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
    
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
        return cls.objects.all_tenants().filter(
            tenant=tenant,
            is_active=True,
            status__in=[cls.Status.PENDING, cls.Status.EXPIRED]
        ).select_related('third_party')


class ContractVehicle(models.Model):
    """
    Vehículo asociado a un contrato con su tarifa individual.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    contract = models.ForeignKey(
        MonthlyContract,
        on_delete=models.CASCADE,
        related_name='vehicles',
        verbose_name="Contrato"
    )
    
    vehicle = models.ForeignKey(
        'third_parties.ThirdPartyVehicle',
        on_delete=models.CASCADE,
        related_name='contract_vehicles',
        verbose_name="Vehículo"
    )
    
    category = models.ForeignKey(
        'parking.VehicleCategory',
        on_delete=models.PROTECT,
        related_name='contract_vehicles',
        verbose_name="Categoría"
    )
    
    monthly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Tarifa mensual"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Notas"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    class Meta:
        verbose_name = "Vehículo del Contrato"
        verbose_name_plural = "Vehículos del Contrato"
        ordering = ['created_at']
        # Un vehículo solo puede estar en un contrato activo a la vez
        constraints = [
            models.UniqueConstraint(
                fields=['contract', 'vehicle'],
                name='unique_vehicle_per_contract'
            )
        ]
    
    def __str__(self):
        return f"{self.vehicle.plate} - ${self.monthly_rate}"


class ContractPayment(models.Model):
    """
    Registro de pagos de contratos mensuales.
    Cada pago corresponde a un mes específico.
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
    
    # Método de pago
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
    
    # Referencia de pago
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia"
    )
    
    # Mes y año que cubre el pago
    payment_month = models.PositiveIntegerField(
        verbose_name="Mes",
        help_text="Mes que cubre este pago (1-12)",
        default=1
    )
    payment_year = models.PositiveIntegerField(
        verbose_name="Año",
        help_text="Año que cubre este pago",
        default=2026
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
        ordering = ['-payment_year', '-payment_month', '-payment_date']
        constraints = [
            models.UniqueConstraint(
                fields=['contract', 'payment_month', 'payment_year'],
                name='unique_payment_per_month'
            )
        ]
    
    def __str__(self):
        return f"Pago ${self.amount} - {self.contract.third_party.full_name} ({self.get_month_name()} {self.payment_year})"
    
    def get_month_name(self):
        """Retorna el nombre del mes"""
        months = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        return months[self.payment_month] if 1 <= self.payment_month <= 12 else ''
    
    def save(self, *args, **kwargs):
        if not self.tenant_id and self.contract_id:
            self.tenant = self.contract.tenant
        
        # Calcular cambio si es efectivo
        if self.amount_received and self.amount:
            self.change_amount = self.amount_received - self.amount
        
        # Calcular período si no está definido
        if not self.period_start:
            import calendar
            self.period_start = timezone.datetime(self.payment_year, self.payment_month, 1).date()
            last_day = calendar.monthrange(self.payment_year, self.payment_month)[1]
            self.period_end = timezone.datetime(self.payment_year, self.payment_month, last_day).date()
        
        super().save(*args, **kwargs)
        
        # Actualizar estado y fecha fin del contrato
        if self.is_confirmed:
            self.contract.update_status()
            if self.period_end and (not self.contract.end_date or self.period_end > self.contract.end_date):
                self.contract.end_date = self.period_end
                self.contract.status = MonthlyContract.Status.ACTIVE
                self.contract.save(update_fields=['end_date', 'status'])
