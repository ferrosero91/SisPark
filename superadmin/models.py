"""
Modelos del panel SuperAdmin.
"""
from django.db import models
from django.utils import timezone
import uuid


class SystemAnnouncement(models.Model):
    """
    Anuncios del sistema que se muestran como banners a los usuarios de los tenants.
    El superadmin puede crear, programar y dirigir anuncios a todos o a tenants específicos.
    """
    
    class AnnouncementType(models.TextChoices):
        INFO = 'info', 'Información'
        WARNING = 'warning', 'Advertencia'
        CRITICAL = 'critical', 'Crítico'
        MAINTENANCE = 'maintenance', 'Mantenimiento'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    title = models.CharField(
        max_length=200,
        verbose_name="Título",
        help_text="Título corto del anuncio"
    )
    message = models.TextField(
        verbose_name="Mensaje",
        help_text="Mensaje completo que verán los usuarios"
    )
    announcement_type = models.CharField(
        max_length=20,
        choices=AnnouncementType.choices,
        default=AnnouncementType.INFO,
        verbose_name="Tipo"
    )
    
    # Programación
    starts_at = models.DateTimeField(
        verbose_name="Inicio",
        help_text="Fecha y hora desde la cual se muestra el anuncio"
    )
    ends_at = models.DateTimeField(
        verbose_name="Fin",
        help_text="Fecha y hora hasta la cual se muestra el anuncio"
    )
    
    # Alcance
    is_global = models.BooleanField(
        default=True,
        verbose_name="Global",
        help_text="Si está activo, se muestra a todos los parqueaderos"
    )
    target_tenants = models.ManyToManyField(
        'tenants.Tenant',
        blank=True,
        related_name='announcements',
        verbose_name="Parqueaderos específicos",
        help_text="Solo aplica si no es global. Seleccione los parqueaderos que verán el anuncio."
    )
    
    # Control
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    is_dismissible = models.BooleanField(
        default=True,
        verbose_name="Se puede cerrar",
        help_text="Si los usuarios pueden cerrar/ocultar el banner"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Creado por"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Anuncio del Sistema"
        verbose_name_plural = "Anuncios del Sistema"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"[{self.get_announcement_type_display()}] {self.title}"
    
    def is_currently_active(self):
        """Verifica si el anuncio está activo ahora mismo."""
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at
    
    def is_visible_for_tenant(self, tenant):
        """Verifica si el anuncio es visible para un tenant específico."""
        if not self.is_currently_active():
            return False
        if self.is_global:
            return True
        return self.target_tenants.filter(pk=tenant.pk).exists()
