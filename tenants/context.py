"""
Gestión del contexto de tenant usando contextvars.
Permite acceder al tenant actual desde cualquier parte del código.
Compatible con async y threading.
"""
import contextvars
from contextlib import contextmanager

# ContextVar for the current tenant (async-safe replacement for threading.local)
_current_tenant: contextvars.ContextVar = contextvars.ContextVar('current_tenant', default=None)


def get_current_tenant():
    """
    Obtiene el tenant actual del contexto.
    Retorna None si no hay tenant establecido.
    """
    return _current_tenant.get()


def set_current_tenant(tenant):
    """
    Establece el tenant actual en el contexto.
    
    Args:
        tenant: Instancia de Tenant o None
    """
    _current_tenant.set(tenant)


def clear_current_tenant():
    """
    Limpia el tenant del contexto.
    Debe llamarse al finalizar cada request.
    """
    _current_tenant.set(None)


@contextmanager
def tenant_context(tenant):
    """
    Context manager para ejecutar código en el contexto de un tenant específico.
    Útil para operaciones que necesitan cambiar temporalmente de tenant.
    
    Ejemplo:
        with tenant_context(other_tenant):
            # Código que se ejecuta en el contexto de other_tenant
            tickets = ParkingTicket.objects.all()
    
    Args:
        tenant: Instancia de Tenant
    """
    token = _current_tenant.set(tenant)
    try:
        yield
    finally:
        _current_tenant.reset(token)


def get_current_tenant_id():
    """
    Obtiene el ID del tenant actual.
    Útil para queries raw o cuando solo se necesita el ID.
    """
    tenant = get_current_tenant()
    return tenant.id if tenant else None
