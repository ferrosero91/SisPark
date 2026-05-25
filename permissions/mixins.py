"""
Mixins para control de acceso en Class-Based Views.
"""
from django.contrib.auth.mixins import AccessMixin
from django.contrib import messages
from django.shortcuts import redirect
from .services import PermissionService


class ModuleRequiredMixin(AccessMixin):
    """
    Mixin que verifica acceso a un módulo específico para CBVs.
    Usa PermissionService para consistencia con el decorador @module_required.
    
    Usage:
        class MyView(ModuleRequiredMixin, ListView):
            module_name = 'parking'
            ...
    """
    module_name = None  # Must be set in subclass

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Verificar acceso al módulo usando el servicio centralizado
        if self.module_name and not PermissionService.has_module_access(
            request.user, self.module_name, 'view'
        ):
            messages.error(request, 'No tiene acceso a este módulo')
            return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)
