"""
Middleware para identificar y establecer el tenant actual basado en el usuario autenticado.
"""
from django.shortcuts import render, redirect
from django.conf import settings
from .models import Tenant
from .context import set_current_tenant, clear_current_tenant
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    Middleware que identifica el tenant basado en el usuario autenticado.
    
    Flujo:
    1. Si el usuario está autenticado, obtiene su tenant
    2. Si es superadmin, no establece tenant específico
    3. Verifica que el tenant esté accesible
    4. Establece el tenant en el contexto
    """
    
    # URLs que no requieren tenant (públicas)
    PUBLIC_URLS = [
        '/',
        '/login/',
        '/logout/',
        '/accounts/login/',
        '/accounts/logout/',
        '/admin/',
        '/superadmin/',
        '/static/',
        '/media/',
        '/favicon.ico',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Limpiar contexto anterior
        clear_current_tenant()
        
        # Verificar si es URL pública
        path = request.path
        is_public = any(path.startswith(url) for url in self.PUBLIC_URLS)
        
        # Si es URL pública, no verificar tenant
        if is_public:
            request.tenant = None
            request.is_superadmin_panel = path.startswith('/superadmin/') or path.startswith('/admin/')
            return self.get_response(request)
        
        # Si el usuario no está autenticado, redirigir a login
        if not request.user.is_authenticated:
            request.tenant = None
            request.is_superadmin_panel = False
            return self.get_response(request)
        
        # Si es superadmin, puede acceder sin tenant
        if request.user.is_superadmin:
            request.tenant = None
            request.is_superadmin_panel = True
            return self.get_response(request)
        
        # Obtener tenant del usuario
        tenant = request.user.tenant
        
        if not tenant:
            logger.warning(f"Usuario {request.user.email} sin tenant asignado")
            request.tenant = None
            return self.get_response(request)
        
        # Verificar si el tenant está accesible
        if not tenant.is_accessible():
            logger.warning(f"Acceso denegado a tenant suspendido: {tenant.name}")
            return self._render_suspended(request, tenant)
        
        # Establecer contexto
        set_current_tenant(tenant)
        request.tenant = tenant
        request.is_superadmin_panel = False
        
        # Procesar request
        response = self.get_response(request)
        
        # Limpiar contexto después del request
        clear_current_tenant()
        
        return response
    
    def _render_suspended(self, request, tenant):
        """Renderiza página de tenant suspendido"""
        return render(
            request, 
            'tenants/suspended.html', 
            {
                'tenant': tenant,
                'reason': tenant.get_suspension_reason(),
                'contact_email': getattr(settings, 'SUPPORT_EMAIL', 'soporte@solupark.shop')
            }, 
            status=403
        )
