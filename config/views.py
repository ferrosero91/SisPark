# Tenant Access Pattern: Use Model.objects.all_tenants().filter(tenant=tenant) for explicit filtering

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError
from parking.models_config import PaymentMethod
from parking.models import VehicleCategory
from users.models import User
from tenants.models import Tenant
from permissions.decorators import tenant_admin_required
from .forms import ParkingInfoForm
from audit.services import AuditService
from tenants.context import set_current_tenant


def get_tenant(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        return getattr(request.user, 'tenant', None)
    return None


@tenant_admin_required
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


@tenant_admin_required
def parking_info(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ParkingInfoForm(request.POST)
        if form.is_valid():
            tenant.name = form.cleaned_data['name']
            tenant.business_name = form.cleaned_data['business_name']
            tenant.nit = form.cleaned_data['nit']
            tenant.phone = form.cleaned_data['phone']
            tenant.email = form.cleaned_data['email']
            tenant.address = form.cleaned_data['address']
            tenant.city = form.cleaned_data['city']
            tenant.save()
            messages.success(request, 'Información actualizada correctamente')
            return redirect('config_parking_info')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = ParkingInfoForm(initial={
            'name': tenant.name,
            'business_name': tenant.business_name,
            'nit': tenant.nit,
            'phone': tenant.phone,
            'email': tenant.email,
            'address': tenant.address,
            'city': tenant.city,
        })
    
    return render(request, 'config/parking_info.html', {'tenant': tenant, 'form': form})


# ============ MÉTODOS DE PAGO ============

@tenant_admin_required
def payment_method_list(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    methods = PaymentMethod.objects.all_tenants().filter(tenant=tenant).order_by('order', 'name')
    return render(request, 'config/payment_methods/list.html', {'methods': methods})


@tenant_admin_required
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


@tenant_admin_required
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


@tenant_admin_required
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

@tenant_admin_required
def category_list_config(request):
    return redirect('category-list')


# ============ USUARIOS ============

@tenant_admin_required  
def user_list(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    users = User.objects.filter(tenant=tenant).order_by('first_name')
    return render(request, 'config/users/list.html', {'users': users})


@tenant_admin_required
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
            
            # Audit logging
            set_current_tenant(tenant)
            AuditService.log(
                action='create',
                user=request.user,
                obj=user,
                message=f'Usuario creado: {user.get_full_name()} ({user.email})',
                request=request
            )
            
            messages.success(request, f'Usuario {user.get_full_name()} creado')
            return redirect('config_users')
    
    return render(request, 'config/users/form.html', {
        'title': 'Nuevo Usuario',
        'modules': modules
    })


@tenant_admin_required
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
        
        # Audit logging
        set_current_tenant(tenant)
        AuditService.log(
            action='update',
            user=request.user,
            obj=user,
            message=f'Usuario editado: {user.get_full_name()} ({user.email})',
            request=request
        )
        
        messages.success(request, 'Usuario actualizado')
        return redirect('config_users')
    
    return render(request, 'config/users/form.html', {
        'title': 'Editar Usuario',
        'edit_user': user,
        'modules': modules,
        'user_module_ids': user_module_ids
    })


@tenant_admin_required
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
        email = user.email
        user.delete()
        
        # Audit logging
        set_current_tenant(tenant)
        AuditService.log(
            action='delete',
            user=request.user,
            message=f'Usuario eliminado: {name} ({email})',
            request=request
        )
        
        messages.success(request, f'Usuario {name} eliminado')
        return redirect('config_users')
    
    return render(request, 'config/users/confirm_delete.html', {'del_user': user})


# ============ BACKUP Y RESTAURACIÓN ============

import os
from django.http import FileResponse, JsonResponse, HttpResponseBadRequest
from django.core.files.storage import default_storage
from .services import TenantBackupService, sanitize_backup_filename


@tenant_admin_required
def backup_dashboard(request):
    """Dashboard de copias de seguridad del tenant."""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    service = TenantBackupService(tenant)
    backups = service.list_backups()
    
    # Formatear tamaños
    for backup in backups:
        size = backup['size']
        if size < 1024:
            backup['size_formatted'] = f"{size} B"
        elif size < 1024 * 1024:
            backup['size_formatted'] = f"{size / 1024:.1f} KB"
        else:
            backup['size_formatted'] = f"{size / (1024 * 1024):.2f} MB"
    
    return render(request, 'config/backup/dashboard.html', {
        'tenant': tenant,
        'backups': backups
    })


@tenant_admin_required
def backup_create(request):
    """Crear una nueva copia de seguridad."""
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        try:
            service = TenantBackupService(tenant)
            
            # Rate limiting: check if backup can be created
            can_create, error_message = service.can_create_backup()
            if not can_create:
                messages.error(request, error_message)
                return redirect('backup_dashboard')
            
            filepath, filename = service.create_backup()
            
            # Enforce backup limit: clean up old backups
            service.enforce_backup_limit()
            
            # Audit logging
            set_current_tenant(tenant)
            AuditService.log(
                action='create',
                user=request.user,
                message=f'Backup creado: {filename}',
                request=request
            )
            
            messages.success(request, f'Copia de seguridad "{filename}" creada exitosamente')
            return redirect('backup_dashboard')
        except Exception as e:
            messages.error(request, f'Error al crear backup: {str(e)}')
            return redirect('backup_dashboard')
    
    return redirect('backup_dashboard')


@tenant_admin_required
def backup_download(request, filename):
    """Descargar una copia de seguridad."""
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    service = TenantBackupService(tenant)
    
    # Sanitizar y validar el nombre de archivo
    safe_filename = sanitize_backup_filename(filename, tenant.slug, service.backup_dir)
    if safe_filename is None:
        # Determinar si es path traversal (400) o patrón inválido (404)
        if '/' in filename or '\\' in filename or '..' in filename:
            return HttpResponseBadRequest('Nombre de archivo no válido')
        return JsonResponse({'error': 'Archivo no encontrado'}, status=404)
    
    filepath = os.path.join(service.backup_dir, safe_filename)
    
    if not os.path.exists(filepath):
        messages.error(request, 'Archivo no encontrado')
        return redirect('backup_dashboard')
    
    response = FileResponse(open(filepath, 'rb'), as_attachment=True, filename=safe_filename)
    return response


@tenant_admin_required
def backup_delete(request, filename):
    """Eliminar una copia de seguridad."""
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        service = TenantBackupService(tenant)
        
        # Sanitizar y validar el nombre de archivo
        safe_filename = sanitize_backup_filename(filename, tenant.slug, service.backup_dir)
        if safe_filename is None:
            if '/' in filename or '\\' in filename or '..' in filename:
                return HttpResponseBadRequest('Nombre de archivo no válido')
            messages.error(request, 'Archivo no encontrado')
            return redirect('backup_dashboard')
        
        if service.delete_backup(safe_filename):
            # Audit logging
            set_current_tenant(tenant)
            AuditService.log(
                action='delete',
                user=request.user,
                message=f'Backup eliminado: {safe_filename}',
                request=request
            )
            messages.success(request, 'Copia de seguridad eliminada')
        else:
            messages.error(request, 'No se pudo eliminar el archivo')
    
    return redirect('backup_dashboard')


@tenant_admin_required
def backup_info(request, filename):
    """Obtener información de un backup."""
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    service = TenantBackupService(tenant)
    
    # Sanitizar y validar el nombre de archivo
    safe_filename = sanitize_backup_filename(filename, tenant.slug, service.backup_dir)
    if safe_filename is None:
        if '/' in filename or '\\' in filename or '..' in filename:
            return HttpResponseBadRequest('Nombre de archivo no válido')
        return JsonResponse({'error': 'Archivo no encontrado'}, status=404)
    
    filepath = os.path.join(service.backup_dir, safe_filename)
    
    info = service.get_backup_info(filepath)
    return JsonResponse(info)


@tenant_admin_required
def backup_restore(request):
    """Restaurar desde una copia de seguridad."""
    tenant = get_tenant(request)
    if not tenant:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        # Restaurar desde archivo existente
        filename = request.POST.get('filename')
        if filename:
            service = TenantBackupService(tenant)
            
            # Sanitizar y validar el nombre de archivo
            safe_filename = sanitize_backup_filename(filename, tenant.slug, service.backup_dir)
            if safe_filename is None:
                if '/' in filename or '\\' in filename or '..' in filename:
                    messages.error(request, 'Nombre de archivo no válido')
                else:
                    messages.error(request, 'Archivo no válido')
                return redirect('backup_dashboard')
            
            filepath = os.path.join(service.backup_dir, safe_filename)
            
            if not os.path.exists(filepath):
                messages.error(request, 'Archivo no encontrado')
                return redirect('backup_dashboard')
            
            clear_existing = request.POST.get('clear_existing') == 'on'
            result = service.restore_backup(filepath, clear_existing)
            
            if result.get('success'):
                total = sum(result.get('restored', {}).values())
                # Audit logging
                set_current_tenant(tenant)
                AuditService.log(
                    action='update',
                    user=request.user,
                    message=f'Backup restaurado: {safe_filename} ({total} registros)',
                    request=request
                )
                messages.success(request, f'Restauración completada. {total} registros restaurados.')
            else:
                messages.error(request, f'Error en restauración: {result.get("error", "Error desconocido")}')
        
        # Restaurar desde archivo subido
        elif 'backup_file' in request.FILES:
            uploaded_file = request.FILES['backup_file']
            
            if not uploaded_file.name.endswith('.zip'):
                messages.error(request, 'El archivo debe ser un ZIP')
                return redirect('backup_dashboard')
            
            # Guardar temporalmente
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            try:
                service = TenantBackupService(tenant)
                
                # Validate backup structure before restoration
                is_valid, error_message = service._validate_backup_structure(tmp_path)
                if not is_valid:
                    messages.error(request, f'Archivo de backup no válido: {error_message}')
                    os.unlink(tmp_path)
                    return redirect('backup_dashboard')
                
                clear_existing = request.POST.get('clear_existing') == 'on'
                result = service.restore_backup(tmp_path, clear_existing)
                
                if result.get('success'):
                    total = sum(result.get('restored', {}).values())
                    # Audit logging
                    set_current_tenant(tenant)
                    AuditService.log(
                        action='update',
                        user=request.user,
                        message=f'Backup restaurado desde archivo subido ({total} registros)',
                        request=request
                    )
                    messages.success(request, f'Restauración completada. {total} registros restaurados.')
                else:
                    messages.error(request, f'Error: {result.get("error", "Error desconocido")}')
                
            finally:
                os.unlink(tmp_path)
        else:
            messages.error(request, 'No se especificó archivo para restaurar')
    
    return redirect('backup_dashboard')
