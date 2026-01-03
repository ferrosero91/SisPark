"""
Modelo para registro de auditoría del sistema.
"""
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid


class AuditLog(models.Model):
    """
    Registro de auditoría para todas las acciones del sistema.
    """
    
    class Action(models.TextChoices):
        CREATE = 'create', 'Crear'
        UPDATE = 'update', 'Actualizar'
        DELETE = 'delete', 'Eliminar'
        LOGIN = 'login', 'Inicio de sesión'
        LOGOUT = 'logout', 'Cierre de sesión'
        LOGIN_FAILED = 'login_failed', 'Login fallido'
        PASSWORD_CHANGE = 'password_change', 'Cambio de contraseña'
        EXPORT = 'export', 'Exportación'
        IMPORT = 'import', 'Importación'
        VIEW = 'view', 'Visualización'
        OTHER = 'other', 'Otro'
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Tenant (null para acciones de superadmin)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Parqueadero"
    )
    
    # Usuario que realizó la acción
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Usuario"
    )
    user_email = models.EmailField(
        blank=True,
        verbose_name="Email del usuario",
        help_text="Guardado para mantener registro si el usuario se elimina"
    )
    
    # Acción realizada
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        verbose_name="Acción"
    )
    
    # Objeto afectado (usando GenericForeignKey)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tipo de objeto"
    )
    object_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ID del objeto"
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Representación del objeto (para cuando se elimine)
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Representación del objeto"
    )
    
    # Cambios realizados (JSON)
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Cambios",
        help_text="Detalle de los cambios realizados"
    )
    
    # Información adicional
    message = models.TextField(
        blank=True,
        verbose_name="Mensaje"
    )
    
    # Información del request
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Dirección IP"
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name="User Agent"
    )
    
    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora",
        db_index=True
    )
    
    class Meta:
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.user_email} - {self.get_action_display()} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        # Guardar email del usuario para referencia futura
        if self.user and not self.user_email:
            self.user_email = self.user.email
        super().save(*args, **kwargs)
