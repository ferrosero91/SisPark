"""
Modelos para el sistema de permisos por módulos.
"""
from django.db import models
from tenants.managers import TenantModel
import uuid


class Module(models.Model):
    """
    Representa un módulo/funcionalidad del sistema.
    Los módulos son globales (no pertenecen a un tenant específico).
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Código",
        help_text="Identificador único del módulo (ej: parking, reports)"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Icono",
        help_text="Clase de icono (ej: fas fa-car)"
    )
    url_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="URL Name",
        help_text="Nombre de la URL de Django para este módulo"
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Orden de aparición en el menú"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Módulo padre"
    )
    
    class Meta:
        verbose_name = "Módulo"
        verbose_name_plural = "Módulos"
        ordering = ['order', 'name']
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def get_children(self):
        """Retorna los submódulos activos"""
        return self.children.filter(is_active=True).order_by('order')


class Role(TenantModel):
    """
    Rol personalizado por tenant.
    Agrupa permisos de módulos para asignar a usuarios.
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Rol por defecto",
        help_text="Se asigna automáticamente a nuevos usuarios"
    )
    modules = models.ManyToManyField(
        Module,
        through='RoleModulePermission',
        related_name='roles',
        verbose_name="Módulos"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_role_name_per_tenant'
            )
        ]
    
    def __str__(self):
        return self.name


class RoleModulePermission(models.Model):
    """
    Permisos específicos de un rol sobre un módulo.
    """
    
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='module_permissions'
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='role_permissions'
    )
    can_view = models.BooleanField(
        default=True,
        verbose_name="Ver"
    )
    can_create = models.BooleanField(
        default=False,
        verbose_name="Crear"
    )
    can_edit = models.BooleanField(
        default=False,
        verbose_name="Editar"
    )
    can_delete = models.BooleanField(
        default=False,
        verbose_name="Eliminar"
    )
    
    class Meta:
        verbose_name = "Permiso de Rol"
        verbose_name_plural = "Permisos de Rol"
        unique_together = ['role', 'module']
    
    def __str__(self):
        perms = []
        if self.can_view:
            perms.append('Ver')
        if self.can_create:
            perms.append('Crear')
        if self.can_edit:
            perms.append('Editar')
        if self.can_delete:
            perms.append('Eliminar')
        return f"{self.role.name} - {self.module.name}: {', '.join(perms)}"


class UserModulePermission(models.Model):
    """
    Permisos específicos de un usuario sobre un módulo.
    Sobrescribe los permisos del rol si existen.
    """
    
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='module_permissions'
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='user_permissions_custom'
    )
    can_view = models.BooleanField(
        default=True,
        verbose_name="Ver"
    )
    can_create = models.BooleanField(
        default=False,
        verbose_name="Crear"
    )
    can_edit = models.BooleanField(
        default=False,
        verbose_name="Editar"
    )
    can_delete = models.BooleanField(
        default=False,
        verbose_name="Eliminar"
    )
    
    class Meta:
        verbose_name = "Permiso de Usuario"
        verbose_name_plural = "Permisos de Usuario"
        unique_together = ['user', 'module']
    
    def __str__(self):
        perms = []
        if self.can_view:
            perms.append('Ver')
        if self.can_create:
            perms.append('Crear')
        if self.can_edit:
            perms.append('Editar')
        if self.can_delete:
            perms.append('Eliminar')
        return f"{self.user.email} - {self.module.name}: {', '.join(perms)}"
