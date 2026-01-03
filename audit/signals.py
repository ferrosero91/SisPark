"""
Signals para auditoría automática de modelos.
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .services import AuditService
from .models import AuditLog

# Modelos a auditar automáticamente
AUDITED_MODELS = []

# Cache para valores anteriores (pre_save)
_pre_save_cache = {}


def register_audited_model(model_class):
    """
    Registra un modelo para auditoría automática.
    
    Usage:
        from audit.signals import register_audited_model
        register_audited_model(MyModel)
    """
    if model_class not in AUDITED_MODELS:
        AUDITED_MODELS.append(model_class)


def get_model_fields_dict(instance, exclude_fields=None):
    """
    Obtiene un diccionario con los valores de los campos del modelo.
    """
    exclude = exclude_fields or ['id', 'created_at', 'updated_at', 'password']
    fields = {}
    for field in instance._meta.fields:
        if field.name not in exclude:
            value = getattr(instance, field.name, None)
            # Convertir ForeignKey a su pk
            if hasattr(value, 'pk'):
                value = value.pk
            fields[field.name] = value
    return fields


@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    """
    Captura valores anteriores antes de guardar.
    """
    if sender in AUDITED_MODELS and instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            cache_key = f"{sender.__name__}_{instance.pk}"
            _pre_save_cache[cache_key] = get_model_fields_dict(old_instance)
        except sender.DoesNotExist:
            pass


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """
    Registra creación o actualización de modelos auditados.
    """
    if sender not in AUDITED_MODELS:
        return
    
    # Evitar auditar el propio AuditLog
    if sender == AuditLog:
        return
    
    # Obtener usuario actual del contexto (si está disponible)
    user = getattr(instance, '_audit_user', None)
    request = getattr(instance, '_audit_request', None)
    
    if created:
        AuditService.log_create(user, instance, request)
    else:
        cache_key = f"{sender.__name__}_{instance.pk}"
        old_values = _pre_save_cache.pop(cache_key, {})
        new_values = get_model_fields_dict(instance)
        
        if old_values:
            AuditService.log_model_change(
                user, 
                instance, 
                old_values, 
                new_values, 
                request
            )


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    """
    Registra eliminación de modelos auditados.
    """
    if sender not in AUDITED_MODELS:
        return
    
    if sender == AuditLog:
        return
    
    user = getattr(instance, '_audit_user', None)
    request = getattr(instance, '_audit_request', None)
    
    AuditService.log_delete(user, instance, request)


class AuditMixin:
    """
    Mixin para agregar contexto de auditoría a modelos.
    
    Usage:
        class MyModel(AuditMixin, models.Model):
            ...
        
        # En la vista:
        obj = MyModel()
        obj.set_audit_context(request.user, request)
        obj.save()
    """
    
    def set_audit_context(self, user=None, request=None):
        """Establece el contexto de auditoría para el próximo save/delete"""
        self._audit_user = user
        self._audit_request = request
