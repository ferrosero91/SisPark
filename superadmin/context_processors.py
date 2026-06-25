"""
Context processors para anuncios del sistema.
Inyecta anuncios activos en todos los templates de los tenants.
"""
from django.utils import timezone


def system_announcements(request):
    """
    Agrega anuncios activos al contexto de todos los templates.
    Solo carga anuncios si el usuario está autenticado y tiene tenant.
    """
    context = {'system_announcements': []}
    
    if not request.user.is_authenticated:
        return context
    
    # Superadmin no ve banners de anuncios
    if getattr(request.user, 'is_superadmin', False):
        return context
    
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return context
    
    # Importar aquí para evitar circular imports
    from .models import SystemAnnouncement
    
    now = timezone.now()
    
    try:
        # Obtener anuncios activos vigentes
        announcements = SystemAnnouncement.objects.filter(
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now,
        )
        
        # Filtrar por tenant (globales + específicos para este tenant)
        visible = []
        for announcement in announcements:
            if announcement.is_global:
                visible.append(announcement)
            elif announcement.target_tenants.filter(pk=tenant.pk).exists():
                visible.append(announcement)
        
        # Excluir anuncios que el usuario ya cerró (guardados en sesión)
        dismissed = request.session.get('dismissed_announcements', [])
        visible = [a for a in visible if str(a.id) not in dismissed]
        
        context['system_announcements'] = visible
    except Exception:
        pass
    
    return context
