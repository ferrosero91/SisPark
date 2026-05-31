"""
Modelos para el sistema de sincronización.
Cola de operaciones pendientes y registro de sincronización.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parking_system.settings_desktop')

from django.db import models
from django.utils import timezone
import uuid


class SyncQueue(models.Model):
    """
    Cola de operaciones pendientes de sincronización.
    Cada vez que se crea/modifica/elimina un registro localmente,
    se agrega una entrada aquí para sincronizar con el servidor.
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        SYNCED = 'synced', 'Sincronizado'
        ERROR = 'error', 'Error'
        FAILED = 'failed', 'Fallido'
        CONFLICT = 'conflict', 'Conflicto'
    
    class Action(models.TextChoices):
        CREATE = 'create', 'Crear'
        UPDATE = 'update', 'Actualizar'
        DELETE = 'delete', 'Eliminar'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Información del registro
    model_name = models.CharField(
        max_length=100,
        verbose_name="Modelo",
        help_text="app_label.ModelName"
    )
    record_id = models.CharField(
        max_length=255,
        verbose_name="ID del registro"
    )
    action = models.CharField(
        max_length=10,
        choices=Action.choices,
        verbose_name="Acción"
    )
    
    # Datos serializados del registro
    data = models.TextField(
        verbose_name="Datos JSON",
        help_text="Datos serializados del registro"
    )
    
    # Estado de sincronización
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Estado"
    )
    
    # Metadatos
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de creación"
    )
    synced_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fecha de sincronización"
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Intentos"
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="Mensaje de error"
    )
    
    class Meta:
        app_label = 'desktop'
        verbose_name = "Cola de Sincronización"
        verbose_name_plural = "Cola de Sincronización"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['model_name', 'record_id']),
        ]
    
    def __str__(self):
        return f"{self.action} {self.model_name}/{self.record_id} [{self.status}]"


class SyncLog(models.Model):
    """
    Registro histórico de sincronizaciones realizadas.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Inicio"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fin"
    )
    
    records_pushed = models.PositiveIntegerField(
        default=0,
        verbose_name="Registros enviados"
    )
    records_pulled = models.PositiveIntegerField(
        default=0,
        verbose_name="Registros recibidos"
    )
    errors = models.PositiveIntegerField(
        default=0,
        verbose_name="Errores"
    )
    
    success = models.BooleanField(
        default=False,
        verbose_name="Exitosa"
    )
    details = models.TextField(
        blank=True,
        verbose_name="Detalles"
    )
    
    class Meta:
        app_label = 'desktop'
        verbose_name = "Log de Sincronización"
        verbose_name_plural = "Logs de Sincronización"
        ordering = ['-started_at']
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} Sync {self.started_at.strftime('%Y-%m-%d %H:%M')}"
