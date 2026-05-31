"""
Vistas para el módulo desktop.
Incluye endpoints de sincronización y estado.
"""
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.conf import settings


@require_GET
@login_required
def sync_status(request):
    """Retorna el estado actual de sincronización."""
    if not getattr(settings, 'DESKTOP_MODE', False):
        return JsonResponse({'error': 'Not in desktop mode'}, status=400)
    
    sync_info = getattr(request, 'sync_status', {})
    
    return JsonResponse({
        'is_online': sync_info.get('is_online', False),
        'pending_count': sync_info.get('pending_count', 0),
        'last_sync': sync_info.get('last_sync', '').isoformat() if sync_info.get('last_sync') else None,
        'desktop_mode': True,
    })


@require_POST
@login_required
def force_sync(request):
    """Fuerza una sincronización inmediata."""
    if not getattr(settings, 'DESKTOP_MODE', False):
        return JsonResponse({'error': 'Not in desktop mode'}, status=400)
    
    try:
        from desktop.sync_engine import sync_engine
        
        if not sync_engine.is_online:
            return JsonResponse({
                'success': False,
                'message': 'Sin conexión a internet'
            })
        
        # Ejecutar sincronización en segundo plano
        import threading
        thread = threading.Thread(target=sync_engine.sync_all, daemon=True)
        thread.start()
        
        return JsonResponse({
            'success': True,
            'message': 'Sincronización iniciada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@require_GET
@login_required
def sync_queue_info(request):
    """Retorna información detallada de la cola de sincronización."""
    if not getattr(settings, 'DESKTOP_MODE', False):
        return JsonResponse({'error': 'Not in desktop mode'}, status=400)
    
    from desktop.sync_models import SyncQueue, SyncLog
    
    # Resumen de la cola
    queue_stats = {
        'pending': SyncQueue.objects.filter(status='pending').count(),
        'synced': SyncQueue.objects.filter(status='synced').count(),
        'error': SyncQueue.objects.filter(status='error').count(),
        'failed': SyncQueue.objects.filter(status='failed').count(),
    }
    
    # Últimas sincronizaciones
    recent_syncs = list(
        SyncLog.objects.order_by('-started_at')[:5].values(
            'started_at', 'completed_at', 'records_pushed',
            'records_pulled', 'errors', 'success'
        )
    )
    
    return JsonResponse({
        'queue': queue_stats,
        'recent_syncs': recent_syncs,
    })
