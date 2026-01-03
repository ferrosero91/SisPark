"""
Context processors para el módulo de parking.
"""
from .models import Turno


def turno_context(request):
    """
    Agrega información del turno activo al contexto de todos los templates.
    """
    context = {
        'turno_activo': None,
        'show_turno_alert': False,
    }
    
    if not request.user.is_authenticated:
        return context
    
    # Superadmin no necesita turno
    if getattr(request.user, 'is_superadmin', False):
        return context
    
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return context
    
    # Buscar turno activo del usuario
    try:
        turno_activo = Turno.objects.all_tenants().filter(
            tenant=tenant,
            user=request.user,
            is_active=True
        ).first()
    except Exception:
        turno_activo = None
    
    context['turno_activo'] = turno_activo
    
    # Mostrar alerta si no tiene turno y está en páginas de operación
    operation_paths = ['/entry/', '/exit/', '/dashboard/']
    if not turno_activo and any(path in request.path for path in operation_paths):
        context['show_turno_alert'] = True
    
    return context
