"""
Backend de autenticación personalizado con soporte multitenant.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from tenants.context import get_current_tenant
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class TenantAuthBackend(ModelBackend):
    """
    Backend de autenticación que:
    - Verifica el estado del tenant antes de autenticar
    - Registra intentos fallidos de login
    - Bloquea cuentas después de múltiples intentos fallidos
    - Registra la IP del último login
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Autentica un usuario verificando:
        1. Que el usuario exista
        2. Que la cuenta no esté bloqueada
        3. Que el tenant esté activo (si aplica)
        4. Que la contraseña sea correcta
        """
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        if username is None or password is None:
            return None
        
        try:
            # Buscar usuario por email (case-insensitive)
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # Ejecutar hasher para prevenir timing attacks
            User().set_password(password)
            return None
        
        # Verificar si la cuenta está bloqueada
        if user.is_locked():
            logger.warning(
                f"Intento de login a cuenta bloqueada: {username}. "
                f"Bloqueada por {user.get_lock_remaining_time()} minutos más."
            )
            return None
        
        # Verificar contraseña
        if not user.check_password(password):
            user.record_failed_login()
            logger.warning(
                f"Contraseña incorrecta para: {username}. "
                f"Intentos fallidos: {user.failed_login_attempts}"
            )
            return None
        
        # Verificar estado del tenant (si el usuario tiene uno)
        if user.tenant and not user.is_superadmin:
            if not user.tenant.is_accessible():
                logger.warning(
                    f"Login denegado - tenant suspendido: {user.tenant.slug}"
                )
                return None
        
        # Verificar que el usuario puede acceder al tenant actual
        current_tenant = get_current_tenant()
        if current_tenant and not user.is_superadmin:
            if user.tenant_id != current_tenant.id:
                logger.warning(
                    f"Login denegado - usuario {username} no pertenece al tenant {current_tenant.slug}"
                )
                return None
        
        # Login exitoso - resetear intentos fallidos
        user.reset_failed_logins()
        
        # Registrar IP del login
        if request:
            ip = self._get_client_ip(request)
            user.update_last_login_ip(ip)
        
        logger.info(f"Login exitoso: {username}")
        return user
    
    def _get_client_ip(self, request):
        """Obtiene la IP real del cliente considerando proxies"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def get_user(self, user_id):
        """Obtiene un usuario por su ID"""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
