"""
Template tags para verificación de permisos en templates.
"""
from django import template
from permissions.services import PermissionService

register = template.Library()


@register.simple_tag(takes_context=True)
def get_menu_modules(context):
    """
    Obtiene los módulos del menú para el usuario actual.
    
    Usage:
        {% load permission_tags %}
        {% get_menu_modules as menu_items %}
        {% for item in menu_items %}
            <a href="{{ item.module.url_name }}">{{ item.module.name }}</a>
        {% endfor %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return []
    
    return PermissionService.get_menu_modules(request.user)


@register.simple_tag(takes_context=True)
def has_module_permission(context, module_code, permission='view'):
    """
    Verifica si el usuario tiene permiso sobre un módulo.
    
    Usage:
        {% load permission_tags %}
        {% has_module_permission 'parking' 'edit' as can_edit %}
        {% if can_edit %}
            <button>Editar</button>
        {% endif %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False
    
    return PermissionService.has_module_access(
        request.user, 
        module_code, 
        permission
    )


@register.filter
def can_view(user, module_code):
    """
    Filtro para verificar permiso de visualización.
    
    Usage:
        {% if user|can_view:'parking' %}
            ...
        {% endif %}
    """
    if not user.is_authenticated:
        return False
    return PermissionService.has_module_access(user, module_code, 'view')


@register.filter
def can_create(user, module_code):
    """Filtro para verificar permiso de creación."""
    if not user.is_authenticated:
        return False
    return PermissionService.has_module_access(user, module_code, 'create')


@register.filter
def can_edit(user, module_code):
    """Filtro para verificar permiso de edición."""
    if not user.is_authenticated:
        return False
    return PermissionService.has_module_access(user, module_code, 'edit')


@register.filter
def can_delete(user, module_code):
    """Filtro para verificar permiso de eliminación."""
    if not user.is_authenticated:
        return False
    return PermissionService.has_module_access(user, module_code, 'delete')


@register.inclusion_tag('permissions/menu.html', takes_context=True)
def render_menu(context):
    """
    Renderiza el menú de navegación basado en permisos.
    
    Usage:
        {% load permission_tags %}
        {% render_menu %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return {'menu_items': []}
    
    return {
        'menu_items': PermissionService.get_menu_modules(request.user),
        'request': request
    }
