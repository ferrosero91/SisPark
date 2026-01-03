"""
Modelos de configuración del parqueadero.
"""
from django.db import models
from tenants.managers import TenantModel
import uuid


class PaymentMethod(TenantModel):
    """
    Métodos de pago configurables por parqueadero.
    """
    class PaymentType(models.TextChoices):
        CASH = 'cash', 'Efectivo'
        CREDIT = 'credit', 'Crédito'
        DEBIT = 'debit', 'Débito'
        TRANSFER = 'transfer', 'Transferencia'
        DIGITAL = 'digital', 'Billetera Digital'
        QR = 'qr', 'Código QR'
        OTHER = 'other', 'Otro'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, verbose_name="Nombre")
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.CASH,
        verbose_name="Tipo"
    )
    description = models.CharField(max_length=200, blank=True, verbose_name="Descripción")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    allow_for_exit = models.BooleanField(
        default=True, 
        verbose_name="Permitir en salidas",
        help_text="Si se puede usar para cobrar salidas de vehículos"
    )
    allow_for_contracts = models.BooleanField(
        default=True,
        verbose_name="Permitir en contratos",
        help_text="Si se puede usar para pagos de mensualidades"
    )
    is_credit = models.BooleanField(
        default=False,
        verbose_name="Es crédito",
        help_text="Si es pago a crédito (solo para clientes registrados)"
    )
    icon = models.CharField(max_length=50, default='fa-money-bill', verbose_name="Icono")
    order = models.PositiveIntegerField(default=0, verbose_name="Orden")
    
    class Meta:
        verbose_name = "Método de Pago"
        verbose_name_plural = "Métodos de Pago"
        ordering = ['order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_payment_method_per_tenant'
            )
        ]
    
    def __str__(self):
        return self.name


class Currency(TenantModel):
    """
    Monedas configurables por parqueadero.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=3, verbose_name="Código")
    name = models.CharField(max_length=50, verbose_name="Nombre")
    symbol = models.CharField(max_length=5, verbose_name="Símbolo")
    is_default = models.BooleanField(default=False, verbose_name="Moneda principal")
    exchange_rate = models.DecimalField(
        max_digits=10, decimal_places=4, default=1,
        verbose_name="Tasa de cambio"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    
    class Meta:
        verbose_name = "Moneda"
        verbose_name_plural = "Monedas"
        ordering = ['-is_default', 'name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if self.is_default:
            # Desmarcar otras monedas como default
            Currency.objects.all_tenants().filter(
                tenant=self.tenant, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
