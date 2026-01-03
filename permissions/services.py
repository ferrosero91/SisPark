"""
Servicio centralizado para gestión de permisos.
"""
from django.core.cache import cache
from .models import Module, UserModulePermission, RoleModulePermission


class PermissionService:
    """
    Servicio para verificar y gestionar permisos de usuarios.
    Implementa caché para optimizar consultas frecuentes.
    """
    
    CACHE_TIMEOUT = 300  # 5 minutos
    CACHE_PREFIX = 'user_perms_'
    
    @classmethod
    def get_cache_key(cls, user_id):
        """Genera la clave de caché para un usuario"""
        return f"{cls.CACHE_PREFIX}{user_id}"
    
    @classmethod
    def get_user_permissions(cls, user):
        """
        Obtiene todos los permisos de un usuario.
        Combina permisos de roles y permisos directos.
        
        Returns:
            dict: {module_code: {can_view, can_create, can_edit, can_delete}}
        """
        if user.is_superadmin:
            # Superadmins tienen acceso total
            return cls._get_all_permissions()
        
        cache_key = cls.get_cache_key(user.id)
        permissions = cache.get(cache_key)
        
        if permissions is not None:
            return permissions
        
        permissions = {}
        
        # Obtener permisos de roles
        for role in user.roles.all():
            for rmp in role.module_permissions.select_related('module').all():
                if rmp.module.is_active:
                    code = rmp.module.code
                    if code not in permissions:
                        permissions[code] = {
                            'can_view': False,
                            'can_create': False,
                            'can_edit': False,
                            'can_delete': False,
                            'module': rmp.module
                        }
                    # Combinar permisos (OR)
                    permissions[code]['can_view'] |= rmp.can_view
                    permissions[code]['can_create'] |= rmp.can_create
                    permissions[code]['can_edit'] |= rmp.can_edit
                    permissions[code]['can_delete'] |= rmp.can_delete
        
        # Sobrescribir con permisos directos del usuario
        for ump in user.module_permissions.select_related('module').all():
            if ump.module.is_active:
                code = ump.module.code
                permissions[code] = {
                    'can_view': ump.can_view,
                    'can_create': ump.can_create,
                    'can_edit': ump.can_edit,
                    'can_delete': ump.can_delete,
                    'module': ump.module
                }
        
        cache.set(cache_key, permissions, cls.CACHE_TIMEOUT)
        return permissions
    
    @classmethod
    def _get_all_permissions(cls):
        """Retorna permisos completos para todos los módulos (superadmin)"""
        permissions = {}
        for module in Module.objects.filter(is_active=True):
            permissions[module.code] = {
                'can_view': True,
                'can_create': True,
                'can_edit': True,
                'can_delete': True,
                'module': module
            }
        return permissions
    
    @classmethod
    def get_user_modules(cls, user):
        """
        Obtiene los módulos accesibles para un usuario.
        
        Returns:
            list: Lista de códigos de módulos con acceso de visualización
        """
        permissions = cls.get_user_permissions(user)
        return [
            code for code, perms in permissions.items() 
            if perms.get('can_view', False)
        ]
    
    @classmethod
    def has_module_access(cls, user, module_code, permission='view'):
        """
        Verifica si un usuario tiene acceso a un módulo específico.
        
        Args:
            user: Usuario a verificar
            module_code: Código del módulo
            permission: Tipo de permiso (view, create, edit, delete)
        
        Returns:
            bool: True si tiene acceso
        """
        if user.is_superadmin:
            return True
        
        if user.is_tenant_admin:
            return True
        
        permissions = cls.get_user_permissions(user)
        module_perms = permissions.get(module_code, {})
        
        perm_key = f'can_{permission}'
        return module_perms.get(perm_key, False)
    
    @classmethod
    def get_menu_modules(cls, user):
        """
        Obtiene los módulos para mostrar en el menú.
        Organiza por módulos padre e hijos.
        
        Returns:
            list: Lista de módulos con sus hijos accesibles
        """
        permissions = cls.get_user_permissions(user)
        accessible_codes = set(
            code for code, perms in permissions.items() 
            if perms.get('can_view', False)
        )
        
        # Obtener módulos raíz
        root_modules = Module.objects.filter(
            parent__isnull=True,
            is_active=True
        ).order_by('order')
        
        menu = []
        for module in root_modules:
            if module.code in accessible_codes:
                children = [
                    child for child in module.get_children()
                    if child.code in accessible_codes
                ]
                menu.append({
                    'module': module,
                    'children': children
                })
        
        return menu
    
    @classmethod
    def invalidate_user_cache(cls, user_id):
        """Invalida la caché de permisos de un usuario"""
        cache_key = cls.get_cache_key(user_id)
        cache.delete(cache_key)
    
    @classmethod
    def invalidate_role_users_cache(cls, role):
        """Invalida la caché de todos los usuarios con un rol"""
        for user in role.users.all():
            cls.invalidate_user_cache(user.id)
