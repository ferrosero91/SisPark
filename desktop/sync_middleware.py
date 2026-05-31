"""
Middleware y signals para capturar cambios en modelos y agregarlos a la cola de sincronización.
"""
import json
import logging
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.serializers import serialize
from django.apps import apps

logger = logging.getLogger('solupark.sync')

# Modelos que se deben sincronizar
SYNCABLE_MODELS = [
    'parking.ParkingTicket',
    'parking.VehicleCategory',
    'parking.Caja',
    'parking.Turno',
    'parking.CashMovement',
    'parking.Expense',
    'parking.ExpenseCategory',
    'parking.PaymentMethod',
    'parking.Currency',
    'third_parties.ThirdParty',
    'third_parties.ThirdPartyVehicle',
    'monthly_contracts.MonthlyContract',
    'monthly_contracts.ContractVehicle',
    'monthly_contracts.ContractPayment',
    'users.User',
    'tenants.Tenant',
    'permissions.Role',
    'permissions.RoleModulePermission',
]


def get_model_label(instance):
    """Obtiene el label del modelo (app_label.ModelName)."""
    return f"{instance._meta.app_label}.{instance.__class__.__name__}"


def serialize_instance(instance):
    """Serializa una instancia de modelo a JSON."""
    try:
        data = serialize('json', [instance])
        parsed = json.loads(data)
        if parsed:
            fields = parsed[0].get('fields', {})
            fields['pk'] = str(parsed[0].get('pk', ''))
            return json.dumps(fields, default=str)
    except Exception as e:
        logger.warning(f"Error serializando {instance}: {e}")
    return '{}'


def add_to_sync_queue(instance, action):
    """Agrega un registro a la cola de sincronización."""
    if not getattr(settings, 'DESKTOP_MODE', False):
        return
    
    model_label = get_model_label(instance)
    
    if model_label not in SYNCABLE_MODELS:
        return
    
    # Evitar recursión (no sincronizar los propios modelos de sync)
    if model_label.startswith('desktop.'):
        return
    
    try:
        from desktop.sync_models import SyncQueue
        
        record_id = str(instance.pk) if instance.pk else ''
        if not record_id:
            return
        
        data = serialize_instance(instance)
        
        SyncQueue.objects.create(
            model_name=model_label,
            record_id=record_id,
            action=action,
            data=data,
        )
        
        logger.debug(f"Sync queue: {action} {model_label}/{record_id}")
        
    except Exception as e:
        # No fallar si hay error en la cola de sync
        logger.warning(f"Error agregando a cola de sync: {e}")


def connect_sync_signals():
    """Conecta las señales de Django para capturar cambios."""
    
    @receiver(post_save)
    def on_model_save(sender, instance, created, **kwargs):
        """Captura creaciones y actualizaciones."""
        action = 'create' if created else 'update'
        add_to_sync_queue(instance, action)
    
    @receiver(post_delete)
    def on_model_delete(sender, instance, **kwargs):
        """Captura eliminaciones."""
        add_to_sync_queue(instance, 'delete')


class SyncStatusMiddleware:
    """
    Middleware que agrega información del estado de sincronización
    al contexto de cada request.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if getattr(settings, 'DESKTOP_MODE', False):
            try:
                from desktop.sync_models import SyncQueue
                from desktop.sync_engine import sync_engine
                
                pending_count = SyncQueue.objects.filter(status='pending').count()
                request.sync_status = {
                    'is_online': sync_engine.is_online,
                    'pending_count': pending_count,
                    'last_sync': sync_engine._last_sync,
                }
            except Exception:
                request.sync_status = {
                    'is_online': False,
                    'pending_count': 0,
                    'last_sync': None,
                }
        
        response = self.get_response(request)
        return response
