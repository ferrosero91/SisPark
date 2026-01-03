"""
Servicio centralizado para registro de auditoría.
"""
from django.contrib.contenttypes.models import ContentType
from tenants.context import get_current_tenant
from .models import AuditLog


class AuditService:
    """
    Servicio para registrar eventos de auditoría.
    """
    
    @classmethod
    def log(cls, action, user=None, obj=None, changes=None, message='', request=None):
        """
        Registra un evento de auditoría.
        
        Args:
            action: Tipo de acción (AuditLog.Action)
            user: Usuario que realizó la acción
            obj: Objeto afectado (opcional)
            changes: Dict con los cambios realizados
            message: Mensaje descriptivo
            request: HttpRequest para extraer IP y user agent
        
        Returns:
            AuditLog: El registro creado
        """
        tenant = get_current_tenant()
        
        # Extraer información del request
        ip_address = None
        user_agent = ''
        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Información del objeto
        content_type = None
        object_id = ''
        object_repr = ''
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = str(obj.pk)
            object_repr = str(obj)[:255]
        
        return AuditLog.objects.create(
            tenant=tenant,
            user=user,
            action=action,
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            changes=changes or {},
            message=message,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @classmethod
    def log_create(cls, user, obj, request=None):
        """Registra la creación de un objeto"""
        return cls.log(
            action=AuditLog.Action.CREATE,
            user=user,
            obj=obj,
            message=f"Creado: {obj}",
            request=request
        )
    
    @classmethod
    def log_update(cls, user, obj, changes, request=None):
        """Registra la actualización de un objeto"""
        return cls.log(
            action=AuditLog.Action.UPDATE,
            user=user,
            obj=obj,
            changes=changes,
            message=f"Actualizado: {obj}",
            request=request
        )
    
    @classmethod
    def log_delete(cls, user, obj, request=None):
        """Registra la eliminación de un objeto"""
        return cls.log(
            action=AuditLog.Action.DELETE,
            user=user,
            obj=obj,
            message=f"Eliminado: {obj}",
            request=request
        )
    
    @classmethod
    def log_login(cls, user, request=None, success=True):
        """Registra un intento de login"""
        action = AuditLog.Action.LOGIN if success else AuditLog.Action.LOGIN_FAILED
        message = "Inicio de sesión exitoso" if success else "Intento de login fallido"
        
        return cls.log(
            action=action,
            user=user if success else None,
            message=message,
            request=request
        )
    
    @classmethod
    def log_logout(cls, user, request=None):
        """Registra un cierre de sesión"""
        return cls.log(
            action=AuditLog.Action.LOGOUT,
            user=user,
            message="Cierre de sesión",
            request=request
        )
    
    @classmethod
    def log_password_change(cls, user, changed_by=None, request=None):
        """Registra un cambio de contraseña"""
        if changed_by and changed_by != user:
            message = f"Contraseña cambiada por {changed_by.email}"
        else:
            message = "Contraseña cambiada por el usuario"
        
        return cls.log(
            action=AuditLog.Action.PASSWORD_CHANGE,
            user=changed_by or user,
            obj=user,
            message=message,
            request=request
        )
    
    @classmethod
    def log_model_change(cls, user, obj, old_values, new_values, request=None):
        """
        Registra cambios en un modelo comparando valores anteriores y nuevos.
        
        Args:
            user: Usuario que realizó el cambio
            obj: Objeto modificado
            old_values: Dict con valores anteriores
            new_values: Dict con valores nuevos
            request: HttpRequest
        """
        changes = {}
        for field, old_val in old_values.items():
            new_val = new_values.get(field)
            if old_val != new_val:
                changes[field] = {
                    'old': str(old_val) if old_val is not None else None,
                    'new': str(new_val) if new_val is not None else None
                }
        
        if changes:
            return cls.log_update(user, obj, changes, request)
        return None
    
    @classmethod
    def _get_client_ip(cls, request):
        """Obtiene la IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @classmethod
    def get_object_history(cls, obj, limit=50):
        """
        Obtiene el historial de auditoría de un objeto.
        
        Args:
            obj: Objeto del cual obtener historial
            limit: Número máximo de registros
        
        Returns:
            QuerySet de AuditLog
        """
        content_type = ContentType.objects.get_for_model(obj)
        return AuditLog.objects.filter(
            content_type=content_type,
            object_id=str(obj.pk)
        )[:limit]
    
    @classmethod
    def get_user_activity(cls, user, limit=50):
        """
        Obtiene la actividad reciente de un usuario.
        
        Args:
            user: Usuario
            limit: Número máximo de registros
        
        Returns:
            QuerySet de AuditLog
        """
        return AuditLog.objects.filter(user=user)[:limit]
