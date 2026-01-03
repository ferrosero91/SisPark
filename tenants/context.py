"""
Gestión del contexto de tenant usando thread-local storage.
Permite acceder al tenant actual desde cualquier parte del código.
"""
import threading
from contextlib import contextmanager

# Thread-local storage para el tenant actual
_thread_locals = threading.local()


def get_current_tenant():
    """
    Obtiene el tenant actual del contexto de thread.
    Retorna None si no hay tenant establecido.
    """
    return getattr(_thread_locals, 'tenant', None)


def set_current_tenant(tenant):
    """
    Establece el tenant actual en el contexto de thread.
    
    Args:
        tenant: Instancia de Tenant o None
    """
    _thread_locals.tenant = tenant


def clear_current_tenant():
    """
    Limpia el tenant del contexto de thread.
    Debe llamarse al finalizar cada request.
    """
    if hasattr(_thread_locals, 'tenant'):
        del _thread_locals.tenant


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
    previous_tenant = get_current_tenant()
    set_current_tenant(tenant)
    try:
        yield
    finally:
        if previous_tenant:
            set_current_tenant(previous_tenant)
        else:
            clear_current_tenant()


def get_current_tenant_id():
    """
    Obtiene el ID del tenant actual.
    Útil para queries raw o cuando solo se necesita el ID.
    """
    tenant = get_current_tenant()
    return tenant.id if tenant else None
