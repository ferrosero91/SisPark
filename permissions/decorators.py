"""
Decoradores para control de acceso a vistas.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from .services import PermissionService


def module_required(module_code, permission='view'):
    """
    Decorador que verifica acceso a un módulo específico.
    
    Args:
        module_code: Código del módulo requerido
        permission: Tipo de permiso (view, create, edit, delete)
    
    Usage:
        @module_required('parking')
        def parking_list(request):
            ...
        
        @module_required('parking', 'create')
        def parking_create(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Debe iniciar sesión para acceder.')
                return redirect('login')
            
            if not PermissionService.has_module_access(
                request.user, 
                module_code, 
                permission
            ):
                messages.error(
                    request, 
                    'No tiene permisos para acceder a esta sección.'
                )
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def superadmin_required(view_func):
    """
    Decorador que restringe acceso solo a superadmins.
    
    Usage:
        @superadmin_required
        def tenant_list(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Debe iniciar sesión para acceder.')
            return redirect('login')
        
        if not request.user.is_superadmin:
            messages.error(
                request, 
                'Acceso restringido a administradores del sistema.'
            )
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def tenant_admin_required(view_func):
    """
    Decorador que restringe acceso a admins del tenant o superadmins.
    
    Usage:
        @tenant_admin_required
        def user_management(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Debe iniciar sesión para acceder.')
            return redirect('login')
        
        if not (request.user.is_superadmin or request.user.is_tenant_admin):
            messages.error(
                request, 
                'Acceso restringido a administradores.'
            )
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def permission_required(permission_type):
    """
    Decorador genérico para verificar un tipo de permiso.
    Útil para vistas que manejan múltiples módulos.
    
    Args:
        permission_type: 'view', 'create', 'edit', 'delete'
    
    Usage:
        @permission_required('edit')
        def generic_edit_view(request, module_code):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Debe iniciar sesión para acceder.')
                return redirect('login')
            
            # El module_code debe venir en kwargs o request
            module_code = kwargs.get('module_code') or request.GET.get('module')
            
            if module_code and not PermissionService.has_module_access(
                request.user, 
                module_code, 
                permission_type
            ):
                messages.error(
                    request, 
                    'No tiene permisos para realizar esta acción.'
                )
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
