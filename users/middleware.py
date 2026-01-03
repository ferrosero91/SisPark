from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class ForcePasswordChangeMiddleware:
    """
    Middleware que fuerza al usuario a cambiar su contraseña
    si tiene el flag must_change_password=True
    """
    
    EXEMPT_URLS = [
        '/usuarios/cambiar-password/',
        '/usuarios/logout/',
        '/admin/logout/',
        '/static/',
        '/media/',
        '/health/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Verificar si debe cambiar contraseña
            if getattr(request.user, 'must_change_password', False):
                # Permitir acceso a URLs exentas
                path = request.path
                if not any(path.startswith(url) for url in self.EXEMPT_URLS):
                    # Redirigir a cambio de contraseña
                    change_password_url = reverse('force_change_password')
                    if path != change_password_url:
                        messages.warning(
                            request, 
                            'Debe cambiar su contraseña antes de continuar.'
                        )
                        return redirect(change_password_url)
        
        response = self.get_response(request)
        return response
