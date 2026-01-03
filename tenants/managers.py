"""
Managers personalizados para modelos multitenant.
Proporcionan filtrado automático por tenant.
"""
from django.db import models
from .context import get_current_tenant


class TenantManager(models.Manager):
    """
    Manager que filtra automáticamente por el tenant actual.
    Todos los modelos que pertenecen a un tenant deben usar este manager.
    """
    
    def get_queryset(self):
        """
        Retorna queryset filtrado por tenant actual.
        Si no hay tenant en contexto, retorna queryset vacío por seguridad.
        """
        queryset = super().get_queryset()
        tenant = get_current_tenant()
        
        if tenant:
            return queryset.filter(tenant=tenant)
        
        # Si no hay tenant, retornar queryset vacío por seguridad
        # Esto previene acceso accidental a datos de otros tenants
        return queryset.none()
    
    def all_tenants(self):
        """
        Retorna queryset sin filtro de tenant.
        SOLO USAR PARA OPERACIONES DE SUPERADMIN.
        """
        return super().get_queryset()
    
    def for_tenant(self, tenant):
        """
        Retorna queryset filtrado por un tenant específico.
        Útil para operaciones de superadmin que necesitan ver datos de un tenant.
        
        Args:
            tenant: Instancia de Tenant o UUID del tenant
        """
        queryset = super().get_queryset()
        if hasattr(tenant, 'id'):
            return queryset.filter(tenant=tenant)
        return queryset.filter(tenant_id=tenant)


class TenantModel(models.Model):
    """
    Modelo base abstracto para entidades que pertenecen a un tenant.
    Todos los modelos de negocio deben heredar de este.
    
    Características:
    - Campo tenant obligatorio (ForeignKey a Tenant)
    - Manager personalizado con filtro automático
    - Asignación automática de tenant en save()
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        verbose_name="Parqueadero"
    )
    
    # Usar el manager personalizado
    objects = TenantManager()
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """
        Override de save para asignar automáticamente el tenant.
        Si no hay tenant asignado, usa el tenant del contexto actual.
        """
        if not self.tenant_id:
            tenant = get_current_tenant()
            if tenant:
                self.tenant = tenant
            else:
                raise ValueError(
                    "No se puede guardar sin un tenant. "
                    "Asegúrese de que hay un tenant en el contexto actual."
                )
        super().save(*args, **kwargs)


class TenantAwareQuerySet(models.QuerySet):
    """
    QuerySet personalizado con métodos adicionales para operaciones multitenant.
    """
    
    def for_current_tenant(self):
        """Filtra por el tenant actual"""
        tenant = get_current_tenant()
        if tenant:
            return self.filter(tenant=tenant)
        return self.none()
    
    def for_tenant(self, tenant):
        """Filtra por un tenant específico"""
        if hasattr(tenant, 'id'):
            return self.filter(tenant=tenant)
        return self.filter(tenant_id=tenant)
