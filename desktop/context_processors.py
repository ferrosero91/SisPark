"""
Context processors para el modo desktop.
Agrega información de sincronización y estado offline al contexto de templates.
"""
from django.conf import settings


def desktop_context(request):
    """Agrega variables de contexto para el modo desktop."""
    context = {
        'is_desktop_mode': getattr(settings, 'DESKTOP_MODE', False),
    }
    
    if context['is_desktop_mode']:
        sync_status = getattr(request, 'sync_status', None)
        if sync_status:
            context['sync_is_online'] = sync_status.get('is_online', False)
            context['sync_pending_count'] = sync_status.get('pending_count', 0)
            context['sync_last_sync'] = sync_status.get('last_sync')
        else:
            context['sync_is_online'] = False
            context['sync_pending_count'] = 0
            context['sync_last_sync'] = None
    
    return context
