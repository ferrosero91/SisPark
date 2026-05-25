"""
Mixins para control de acceso en Class-Based Views.
"""
from django.contrib.auth.mixins import AccessMixin
from django.contrib import messages
from django.shortcuts import redirect


class ModuleRequiredMixin(AccessMixin):
    """
    Mixin que verifica acceso a un módulo específico para CBVs.
    
    Usage:
        class MyView(ModuleRequiredMixin, ListView):
            module_name = 'parking'
            ...
    """
    module_name = None  # Must be set in subclass

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Admin users have full access
        if getattr(request.user, 'is_tenant_admin', False) or getattr(request.user, 'is_superadmin', False):
            return super().dispatch(request, *args, **kwargs)
        # Check module permission
        if self.module_name and not request.user.module_permissions.filter(module__code_name=self.module_name).exists():
            messages.error(request, 'No tiene acceso a este módulo')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
