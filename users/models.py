from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid


class UserManager(BaseUserManager):
    """
    Manager personalizado para el modelo User.
    Soporta creación de usuarios normales y superusuarios.
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """Crea y guarda un usuario regular"""
        if not email:
            raise ValueError('El email es obligatorio')
        
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Crea y guarda un superusuario"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_superadmin', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)
    
    def for_tenant(self, tenant):
        """Retorna usuarios de un tenant específico"""
        return self.filter(tenant=tenant)


class User(AbstractUser):
    """
    Modelo de usuario extendido con soporte multitenant.
    
    Características:
    - UUID como primary key
    - Relación opcional con tenant (null para superadmins)
    - Campos adicionales para perfil y seguridad
    - Control de bloqueo por intentos fallidos
    """
    
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    
    # Email como identificador principal
    email = models.EmailField(
        unique=True,
        verbose_name="Email"
    )
    
    # Relación con tenant (null para superadmins globales)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
        verbose_name="Parqueadero"
    )
    
    # Roles especiales
    is_superadmin = models.BooleanField(
        default=False, 
        verbose_name="Es SuperAdmin",
        help_text="Acceso global a todos los parqueaderos"
    )
    is_tenant_admin = models.BooleanField(
        default=False, 
        verbose_name="Es Admin del Parqueadero",
        help_text="Acceso completo dentro de su parqueadero"
    )
    
    # Información adicional
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Teléfono"
    )
    avatar = models.ImageField(
        upload_to='avatars/', 
        null=True, 
        blank=True,
        verbose_name="Avatar"
    )
    
    # Seguridad y auditoría
    last_login_ip = models.GenericIPAddressField(
        null=True, 
        blank=True,
        verbose_name="Última IP de login"
    )
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name="Intentos fallidos de login"
    )
    locked_until = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Bloqueado hasta"
    )
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Último cambio de contraseña"
    )
    must_change_password = models.BooleanField(
        default=False,
        verbose_name="Debe cambiar contraseña",
        help_text="Forzar cambio de contraseña en el próximo login"
    )
    
    # Roles asignados (ManyToMany con Role del módulo permissions)
    roles = models.ManyToManyField(
        'permissions.Role',
        blank=True,
        related_name='users',
        verbose_name="Roles"
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ['first_name', 'last_name']
    
    def __str__(self):
        return self.get_full_name() or self.email
    
    def save(self, *args, **kwargs):
        # Usar email como username si no se especifica
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)
    
    def is_locked(self):
        """Verifica si la cuenta está bloqueada por intentos fallidos"""
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False
    
    def get_lock_remaining_time(self):
        """Retorna el tiempo restante de bloqueo en minutos"""
        if self.is_locked():
            remaining = self.locked_until - timezone.now()
            return max(0, int(remaining.total_seconds() / 60))
        return 0
    
    def record_failed_login(self):
        """
        Registra un intento fallido de login.
        Bloquea la cuenta después de 5 intentos.
        """
        from django.conf import settings
        
        max_attempts = getattr(settings, 'LOGIN_RATE_LIMIT_ATTEMPTS', 5)
        lockout_minutes = getattr(settings, 'LOGIN_RATE_LIMIT_TIMEOUT', 15)
        
        self.failed_login_attempts += 1
        
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = timezone.now() + timedelta(minutes=lockout_minutes)
        
        self.save(update_fields=['failed_login_attempts', 'locked_until'])
    
    def reset_failed_logins(self):
        """Resetea el contador de intentos fallidos después de login exitoso"""
        if self.failed_login_attempts > 0 or self.locked_until:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=['failed_login_attempts', 'locked_until'])
    
    def update_last_login_ip(self, ip_address):
        """Actualiza la última IP de login"""
        self.last_login_ip = ip_address
        self.save(update_fields=['last_login_ip'])
    
    def has_tenant_access(self, tenant):
        """Verifica si el usuario tiene acceso a un tenant específico"""
        if self.is_superadmin:
            return True
        return self.tenant_id == tenant.id if tenant else False
    
    def get_accessible_modules(self):
        """Retorna los códigos de módulos accesibles para este usuario"""
        from permissions.services import PermissionService
        return PermissionService.get_user_modules(self)
