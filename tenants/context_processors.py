"""
Context processors para templates.
Hacen disponible el tenant actual en todos los templates.
"""
from .context import get_current_tenant


def tenant_context(request):
    """
    Agrega el tenant actual al contexto de todos los templates.
    
    Variables disponibles en templates:
    - current_tenant: Instancia del tenant actual o None
    - is_superadmin_panel: Boolean indicando si es panel de superadmin
    """
    return {
        'current_tenant': getattr(request, 'tenant', None),
        'is_superadmin_panel': getattr(request, 'is_superadmin_panel', False),
    }
