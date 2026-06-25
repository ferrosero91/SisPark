"""
Vista para que los usuarios de tenant puedan cerrar anuncios.
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST


@login_required
@require_POST
def dismiss_announcement(request, announcement_id):
    """Marca un anuncio como cerrado para la sesión actual del usuario."""
    dismissed = request.session.get('dismissed_announcements', [])
    announcement_id_str = str(announcement_id)
    
    if announcement_id_str not in dismissed:
        dismissed.append(announcement_id_str)
        request.session['dismissed_announcements'] = dismissed
    
    return JsonResponse({'status': 'ok'})
