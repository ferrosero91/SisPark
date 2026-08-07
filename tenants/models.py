from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import uuid


class SubscriptionPlan(models.Model):
    """Planes de suscripción disponibles"""
    
    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Mensual'
        ANNUAL = 'annual', 'Anual'
    
    name = models.CharField(max_length=100, verbose_name="Nombre del Plan")
    description = models.TextField(blank=True, verbose_name="Descripción")
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio")
    billing_cycle = models.CharField(
        max_length=20, 
        choices=BillingCycle.choices, 
        default=BillingCycle.MONTHLY,
        verbose_name="Ciclo de facturación"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Plan de Suscripción"
        verbose_name_plural = "Planes de Suscripción"
        ordering = ['price']
    
    def __str__(self):
        cycle = "mes" if self.billing_cycle == 'monthly' else "año"
        return f"{self.name} - ${self.price:,.0f}/{cycle}"


class Tenant(models.Model):
    """
    Representa un parqueadero/organización en la plataforma.
    Cada tenant tiene sus propios datos aislados.
    """
    
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Activo'
        SUSPENDED = 'suspended', 'Suspendido'
        TRIAL = 'trial', 'Prueba'
        CANCELLED = 'cancelled', 'Cancelado'
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    
    # Identificación
    name = models.CharField(
        max_length=255, 
        verbose_name="Nombre del Parqueadero"
    )
    slug = models.SlugField(
        unique=True, 
        max_length=100,
        verbose_name="Código único",
        help_text="Identificador interno del parqueadero"
    )
    
    # Información de la empresa
    business_name = models.CharField(
        max_length=255, 
        verbose_name="Razón Social"
    )
    nit = models.CharField(
        max_length=20, 
        verbose_name="NIT"
    )
    phone = models.CharField(
        max_length=20, 
        verbose_name="Teléfono"
    )
    address = models.CharField(
        max_length=200, 
        verbose_name="Dirección"
    )
    email = models.EmailField(
        verbose_name="Email de contacto"
    )
    city = models.CharField(
        max_length=100, 
        blank=True,
        verbose_name="Ciudad"
    )
    
    # Logo
    logo = models.ImageField(
        upload_to='tenants/logos/', 
        null=True, 
        blank=True,
        verbose_name="Logo"
    )
    
    # Tipo de parqueadero
    is_residential = models.BooleanField(
        default=False,
        verbose_name="Es conjunto residencial",
        help_text="Active esta opción si el parqueadero pertenece a un conjunto residencial"
    )
    
    # Estado y configuración
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.TRIAL,
        verbose_name="Estado"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    # Fechas
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    trial_ends_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Fin del período de prueba"
    )
    
    # Configuración personalizada (JSON)
    settings = models.JSONField(
        default=dict, 
        blank=True,
        verbose_name="Configuración",
        help_text="Configuración personalizada del parqueadero"
    )
    
    # Notas internas (solo visible para superadmin)
    internal_notes = models.TextField(
        blank=True,
        verbose_name="Notas internas"
    )
    
    # Suscripción
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Plan de suscripción"
    )
    subscription_start = models.DateField(
        null=True,
        blank=True,
        verbose_name="Inicio de suscripción"
    )
    subscription_end = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fin de suscripción"
    )
    
    class Meta:
        verbose_name = "Parqueadero"
        verbose_name_plural = "Parqueaderos"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Generar slug automáticamente si no existe
        if not self.slug:
            self.slug = slugify(self.name)
            # Asegurar unicidad
            original_slug = self.slug
            counter = 1
            while Tenant.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def is_accessible(self):
        """
        Verifica si el tenant puede ser accedido por sus usuarios.
        Retorna False si está suspendido, inactivo, el trial expiró o la suscripción venció.
        """
        if not self.is_active:
            return False
        
        if self.status == self.Status.SUSPENDED:
            return False
        
        if self.status == self.Status.CANCELLED:
            return False
        
        if self.status == self.Status.TRIAL and self.trial_ends_at:
            if timezone.now() > self.trial_ends_at:
                return False
        
        # Verificar si la suscripción ha expirado
        if self.subscription_end and self.status == self.Status.ACTIVE:
            if timezone.now().date() > self.subscription_end:
                return False
        
        return True
    
    def get_suspension_reason(self):
        """Retorna el motivo por el cual el tenant no es accesible"""
        if not self.is_active:
            return "La cuenta ha sido desactivada."
        
        if self.status == self.Status.SUSPENDED:
            return "La cuenta ha sido suspendida por falta de pago."
        
        if self.status == self.Status.CANCELLED:
            return "La cuenta ha sido cancelada."
        
        if self.status == self.Status.TRIAL and self.trial_ends_at:
            if timezone.now() > self.trial_ends_at:
                return "El período de prueba ha expirado."
        
        # Suscripción vencida
        if self.subscription_end and self.status == self.Status.ACTIVE:
            if timezone.now().date() > self.subscription_end:
                return "La suscripción ha vencido. Contacte al administrador para renovar."
        
        return None
    
    def get_domain(self):
        """Retorna el dominio completo del tenant"""
        from django.conf import settings
        base_domain = getattr(settings, 'BASE_DOMAIN', 'solupark.shop')
        return f"{self.slug}.{base_domain}"
    
    def days_until_expiration(self):
        """Retorna los días hasta que expire la suscripción"""
        if not self.subscription_end:
            return None
        today = timezone.now().date()
        delta = self.subscription_end - today
        return delta.days
    
    def is_subscription_expiring_soon(self):
        """Verifica si la suscripción vence en los próximos 7 días"""
        days = self.days_until_expiration()
        if days is None:
            return False
        return 0 < days <= 7
    
    def is_subscription_expired(self):
        """Verifica si la suscripción ya expiró"""
        days = self.days_until_expiration()
        if days is None:
            return False
        return days <= 0


class SubscriptionPayment(models.Model):
    """Pagos de suscripción de los tenants"""
    
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        CONFIRMED = 'confirmed', 'Confirmado'
        REJECTED = 'rejected', 'Rechazado'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='subscription_payments',
        verbose_name="Parqueadero"
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        verbose_name="Plan"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto")
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de pago")
    confirmed_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de confirmación")
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        verbose_name="Estado"
    )
    period_start = models.DateField(verbose_name="Inicio del período")
    period_end = models.DateField(verbose_name="Fin del período")
    notes = models.TextField(blank=True, verbose_name="Notas")
    confirmed_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_subscriptions',
        verbose_name="Confirmado por"
    )
    
    class Meta:
        verbose_name = "Pago de Suscripción"
        verbose_name_plural = "Pagos de Suscripción"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name} - ${self.amount:,.0f}"
