"""
Modelos para gestión de terceros (clientes) del parqueadero.
"""
from django.db import models
from tenants.managers import TenantModel
import uuid


class ThirdParty(TenantModel):
    """
    Representa un tercero/cliente del parqueadero.
    Puede tener múltiples vehículos asociados.
    """
    
    class DocumentType(models.TextChoices):
        CC = 'CC', 'Cédula de Ciudadanía'
        CE = 'CE', 'Cédula de Extranjería'
        NIT = 'NIT', 'NIT'
        PASSPORT = 'PP', 'Pasaporte'
        OTHER = 'OT', 'Otro'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Identificación
    document_type = models.CharField(
        max_length=10,
        choices=DocumentType.choices,
        default=DocumentType.CC,
        verbose_name="Tipo de documento"
    )
    document_number = models.CharField(
        max_length=20,
        verbose_name="Número de documento"
    )
    
    # Información personal
    first_name = models.CharField(
        max_length=100,
        verbose_name="Nombres"
    )
    last_name = models.CharField(
        max_length=100,
        verbose_name="Apellidos"
    )
    email = models.EmailField(
        blank=True,
        verbose_name="Email"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Teléfono"
    )
    address = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Dirección"
    )
    
    # Estado
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    # Notas
    notes = models.TextField(
        blank=True,
        verbose_name="Notas"
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
    
    class Meta:
        verbose_name = "Tercero"
        verbose_name_plural = "Terceros"
        ordering = ['last_name', 'first_name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'document_type', 'document_number'],
                name='unique_document_per_tenant'
            )
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_document(self):
        return f"{self.get_document_type_display()} {self.document_number}"
    
    def get_primary_vehicle(self):
        """Retorna el vehículo principal del tercero"""
        return self.vehicles.filter(is_primary=True).first()
    
    def get_active_contracts(self):
        """Retorna los contratos activos del tercero"""
        return self.contracts.filter(is_active=True, status='active')


class ThirdPartyVehicle(models.Model):
    """
    Vehículo asociado a un tercero.
    """
    
    class VehicleType(models.TextChoices):
        CAR = 'car', 'Carro'
        MOTORCYCLE = 'motorcycle', 'Moto'
        BICYCLE = 'bicycle', 'Bicicleta'
        TRUCK = 'truck', 'Camión'
        OTHER = 'other', 'Otro'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    third_party = models.ForeignKey(
        ThirdParty,
        on_delete=models.CASCADE,
        related_name='vehicles',
        verbose_name="Tercero"
    )
    
    # Información del vehículo
    plate = models.CharField(
        max_length=10,
        verbose_name="Placa"
    )
    brand = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Marca"
    )
    model = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Modelo"
    )
    color = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Color"
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.CAR,
        verbose_name="Tipo de vehículo"
    )
    
    # Configuración
    is_primary = models.BooleanField(
        default=False,
        verbose_name="Vehículo principal"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    
    # Notas
    notes = models.TextField(
        blank=True,
        verbose_name="Notas"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    
    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ['-is_primary', 'plate']
    
    def __str__(self):
        return f"{self.plate} - {self.get_vehicle_type_display()}"
    
    def save(self, *args, **kwargs):
        # Normalizar placa a mayúsculas
        self.plate = self.plate.upper().replace(' ', '').replace('-', '')
        
        # Si es el primer vehículo, marcarlo como principal
        if not self.pk and not self.third_party.vehicles.exists():
            self.is_primary = True
        
        # Si se marca como principal, desmarcar los demás
        if self.is_primary:
            self.third_party.vehicles.exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)
