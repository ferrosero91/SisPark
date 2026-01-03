from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from parking.models_config import PaymentMethod
from parking.models import VehicleCategory
from users.models import User
from tenants.models import Tenant


def get_tenant(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        return getattr(request.user, 'tenant', None)
    return None


@login_required
def config_dashboard(request):
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, 'No tiene un parqueadero asignado')
        return redirect('dashboard')
    
    # Estadísticas
    stats = {
        'categories': VehicleCategory.objects.all_tenants().filter(tenant=tenant).count(),
        'payment_methods': PaymentMethod.objects.all_tenants().filter(tenant=tenant).count(),
        'users': User.objects.filter(tenant=tenant).count(),
    }
    
    return render(request, 'config/dashboard.html', {
        'tenant': tenant,
        'stats': stats
    })


@login_required
def parking_info(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    if request.method == 'POST':
        tenant.name = request.POST.get('name', tenant.name)
        tenant.business_name = request.POST.get('business_name', tenant.business_name)
        tenant.nit = request.POST.get('nit', tenant.nit)
        tenant.phone = request.POST.get('phone', tenant.phone)
        tenant.email = request.POST.get('email', tenant.email)
        tenant.address = request.POST.get('address', tenant.address)
        tenant.city = request.POST.get('city', tenant.city)
        tenant.save()
        messages.success(request, 'Información actualizada correctamente')
        return redirect('config_parking_info')
    
    return render(request, 'config/parking_info.html', {'tenant': tenant})


# ============ MÉTODOS DE PAGO ============

@login_required
def payment_method_list(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    methods = PaymentMethod.objects.all_tenants().filter(tenant=tenant).order_by('order', 'name')
    return render(request, 'config/payment_methods/list.html', {'methods': methods})


@login_required
def payment_method_create(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            PaymentMethod.objects.create(
                tenant=tenant,
                name=request.POST.get('name'),
                payment_type=request.POST.get('payment_type', 'cash'),
                description=request.POST.get('description', ''),
                allow_for_exit=request.POST.get('allow_for_exit') == 'on',
                allow_for_contracts=request.POST.get('allow_for_contracts') == 'on',
                is_credit=request.POST.get('is_credit') == 'on',
                icon=request.POST.get('icon', 'fa-money-bill'),
            )
            messages.success(request, 'Método de pago creado')
            return redirect('payment_method_list')
        except IntegrityError:
            messages.error(request, 'Ya existe un método de pago con ese nombre')
    
    return render(request, 'config/payment_methods/form.html', {
        'title': 'Nuevo Método de Pago',
        'payment_types': PaymentMethod.PaymentType.choices
    })


@login_required
def payment_method_edit(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    method = get_object_or_404(PaymentMethod.objects.all_tenants(), pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        method.name = request.POST.get('name')
        method.payment_type = request.POST.get('payment_type', 'cash')
        method.description = request.POST.get('description', '')
        method.allow_for_exit = request.POST.get('allow_for_exit') == 'on'
        method.allow_for_contracts = request.POST.get('allow_for_contracts') == 'on'
        method.is_credit = request.POST.get('is_credit') == 'on'
        method.is_active = request.POST.get('is_active') == 'on'
        method.icon = request.POST.get('icon', 'fa-money-bill')
        method.save()
        messages.success(request, 'Método de pago actualizado')
        return redirect('payment_method_list')
    
    return render(request, 'config/payment_methods/form.html', {
        'title': 'Editar Método de Pago',
        'method': method,
        'payment_types': PaymentMethod.PaymentType.choices
    })


@login_required
def payment_method_delete(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    method = get_object_or_404(PaymentMethod.objects.all_tenants(), pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        method.delete()
        messages.success(request, 'Método de pago eliminado')
        return redirect('payment_method_list')
    
    return render(request, 'config/payment_methods/confirm_delete.html', {'method': method})


# ============ CATEGORÍAS ============

@login_required
def category_list_config(request):
    return redirect('category-list')


# ============ USUARIOS ============

@login_required  
def user_list(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    users = User.objects.filter(tenant=tenant).order_by('first_name')
    return render(request, 'config/users/list.html', {'users': users})


@login_required
def user_create(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    from permissions.models import Module, UserModulePermission
    modules = Module.objects.filter(is_active=True, parent__isnull=True).order_by('order')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Ya existe un usuario con ese email')
        else:
            user = User.objects.create_user(
                email=email,
                password=request.POST.get('password'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                phone=request.POST.get('phone', ''),
                tenant=tenant,
                is_tenant_admin=request.POST.get('is_admin') == 'on'
            )
            
            # Guardar permisos de módulos
            if not user.is_tenant_admin:
                selected_modules = request.POST.getlist('modules')
                for module in modules:
                    if str(module.id) in selected_modules:
                        UserModulePermission.objects.create(
                            user=user,
                            module=module,
                            can_view=True,
                            can_create=True,
                            can_edit=True,
                            can_delete=True
                        )
            
            messages.success(request, f'Usuario {user.get_full_name()} creado')
            return redirect('config_users')
    
    return render(request, 'config/users/form.html', {
        'title': 'Nuevo Usuario',
        'modules': modules
    })


@login_required
def user_edit(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    user = get_object_or_404(User, pk=pk, tenant=tenant)
    
    from permissions.models import Module, UserModulePermission
    from permissions.services import PermissionService
    
    modules = Module.objects.filter(is_active=True, parent__isnull=True).order_by('order')
    user_module_ids = list(user.module_permissions.values_list('module_id', flat=True))
    
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.phone = request.POST.get('phone', '')
        user.is_tenant_admin = request.POST.get('is_admin') == 'on'
        user.is_active = request.POST.get('is_active') == 'on'
        
        new_password = request.POST.get('password')
        if new_password:
            user.set_password(new_password)
        
        user.save()
        
        # Actualizar permisos de módulos
        if not user.is_tenant_admin:
            # Eliminar permisos anteriores
            user.module_permissions.all().delete()
            
            # Crear nuevos permisos
            selected_modules = request.POST.getlist('modules')
            for module in modules:
                if str(module.id) in selected_modules:
                    UserModulePermission.objects.create(
                        user=user,
                        module=module,
                        can_view=True,
                        can_create=True,
                        can_edit=True,
                        can_delete=True
                    )
        else:
            # Si es admin, eliminar permisos específicos (tiene acceso total)
            user.module_permissions.all().delete()
        
        # Invalidar caché de permisos
        PermissionService.invalidate_user_cache(user.id)
        
        messages.success(request, 'Usuario actualizado')
        return redirect('config_users')
    
    return render(request, 'config/users/form.html', {
        'title': 'Editar Usuario',
        'edit_user': user,
        'modules': modules,
        'user_module_ids': user_module_ids
    })


@login_required
def user_delete(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    user = get_object_or_404(User, pk=pk, tenant=tenant)
    
    if user == request.user:
        messages.error(request, 'No puede eliminarse a sí mismo')
        return redirect('config_users')
    
    if request.method == 'POST':
        name = user.get_full_name()
        user.delete()
        messages.success(request, f'Usuario {name} eliminado')
        return redirect('config_users')
    
    return render(request, 'config/users/confirm_delete.html', {'del_user': user})
