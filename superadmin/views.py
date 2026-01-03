"""
Vistas del panel de SuperAdmin.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from tenants.models import Tenant, SubscriptionPlan, SubscriptionPayment
from users.models import User
from .forms import TenantForm, TenantCreateForm, AdminPasswordChangeForm
from permissions.decorators import superadmin_required


def superadmin_logout(request):
    """Cerrar sesión del superadmin"""
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('pagina_inicial')


@login_required
@superadmin_required
def dashboard(request):
    """Dashboard principal del SuperAdmin"""
    today = timezone.now().date()
    expiring_soon = Tenant.objects.filter(
        subscription_end__isnull=False,
        subscription_end__lte=today + timedelta(days=7),
        subscription_end__gt=today
    ).count()
    
    context = {
        'total_tenants': Tenant.objects.count(),
        'active_tenants': Tenant.objects.filter(is_active=True, status='active').count(),
        'suspended_tenants': Tenant.objects.filter(status='suspended').count(),
        'trial_tenants': Tenant.objects.filter(status='trial').count(),
        'expiring_soon': expiring_soon,
        'recent_tenants': Tenant.objects.order_by('-created_at')[:5],
        'total_users': User.objects.filter(is_superadmin=False).count(),
        'recent_payments': SubscriptionPayment.objects.select_related('tenant', 'plan').order_by('-payment_date')[:5],
    }
    return render(request, 'superadmin/dashboard.html', context)


@login_required
@superadmin_required
def tenant_list(request):
    """Lista de todos los parqueaderos"""
    tenants = Tenant.objects.annotate(
        user_count=Count('users')
    ).order_by('-created_at')
    
    # Filtros
    status = request.GET.get('status')
    if status:
        tenants = tenants.filter(status=status)
    
    search = request.GET.get('search')
    if search:
        tenants = tenants.filter(name__icontains=search)
    
    context = {
        'tenants': tenants,
        'status_choices': Tenant.Status.choices,
    }
    return render(request, 'superadmin/tenant_list.html', context)


@login_required
@superadmin_required
def tenant_create(request):
    """Crear nuevo parqueadero con su administrador"""
    if request.method == 'POST':
        form = TenantCreateForm(request.POST)
        if form.is_valid():
            # Crear tenant
            tenant = form.save()
            
            # Crear usuario administrador del tenant
            admin_user = User.objects.create_user(
                email=form.cleaned_data['admin_email'],
                password=form.cleaned_data['admin_password'],
                first_name=form.cleaned_data['admin_first_name'],
                last_name=form.cleaned_data['admin_last_name'],
                tenant=tenant,
                is_tenant_admin=True
            )
            
            messages.success(
                request, 
                f'Parqueadero "{tenant.name}" creado exitosamente con administrador {admin_user.email}'
            )
            return redirect('superadmin:tenant_list')
    else:
        form = TenantCreateForm()
    
    return render(request, 'superadmin/tenant_form.html', {
        'form': form,
        'title': 'Crear Parqueadero',
        'is_create': True
    })


@login_required
@superadmin_required
def tenant_detail(request, pk):
    """Detalle de un parqueadero"""
    from parking.models import VehicleCategory
    
    tenant = get_object_or_404(Tenant, pk=pk)
    users = User.objects.filter(tenant=tenant)
    admin_user = users.filter(is_tenant_admin=True).first()
    categories_count = VehicleCategory.objects.all_tenants().filter(tenant=tenant).count()
    
    context = {
        'tenant': tenant,
        'users': users,
        'admin_user': admin_user,
        'users_count': users.count(),
        'categories_count': categories_count,
    }
    return render(request, 'superadmin/tenant_detail.html', context)


@login_required
@superadmin_required
def tenant_edit(request, pk):
    """Editar parqueadero"""
    tenant = get_object_or_404(Tenant, pk=pk)
    
    if request.method == 'POST':
        form = TenantForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, f'Parqueadero "{tenant.name}" actualizado')
            return redirect('superadmin:tenant_detail', pk=pk)
    else:
        form = TenantForm(instance=tenant)
    
    return render(request, 'superadmin/tenant_form.html', {
        'form': form,
        'tenant': tenant,
        'title': f'Editar: {tenant.name}',
        'is_create': False
    })


@login_required
@superadmin_required
def tenant_toggle_status(request, pk):
    """Activar/Desactivar parqueadero"""
    tenant = get_object_or_404(Tenant, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'suspend':
            tenant.status = Tenant.Status.SUSPENDED
            tenant.save()
            messages.warning(request, f'Parqueadero "{tenant.name}" suspendido')
        elif action == 'activate':
            tenant.status = Tenant.Status.ACTIVE
            tenant.is_active = True
            tenant.save()
            messages.success(request, f'Parqueadero "{tenant.name}" activado')
        elif action == 'deactivate':
            tenant.is_active = False
            tenant.save()
            messages.warning(request, f'Parqueadero "{tenant.name}" desactivado')
    
    return redirect('superadmin:tenant_detail', pk=pk)


@login_required
@superadmin_required
def tenant_delete(request, pk):
    """Eliminar parqueadero"""
    tenant = get_object_or_404(Tenant, pk=pk)
    
    if request.method == 'POST':
        tenant_name = tenant.name
        tenant.delete()
        messages.success(request, f'Parqueadero "{tenant_name}" eliminado permanentemente')
        return redirect('superadmin:tenant_list')
    
    return render(request, 'superadmin/tenant_delete.html', {'tenant': tenant})


@login_required
@superadmin_required
def tenant_change_password(request, pk):
    """Cambiar contraseña del admin de un tenant"""
    tenant = get_object_or_404(Tenant, pk=pk)
    admin_user = User.objects.filter(tenant=tenant, is_tenant_admin=True).first()
    
    if not admin_user:
        messages.error(request, 'Este parqueadero no tiene administrador')
        return redirect('superadmin:tenant_detail', pk=pk)
    
    if request.method == 'POST':
        form = AdminPasswordChangeForm(request.POST)
        if form.is_valid():
            admin_user.set_password(form.cleaned_data['new_password'])
            admin_user.save()
            messages.success(request, f'Contraseña de {admin_user.email} actualizada')
            return redirect('superadmin:tenant_detail', pk=pk)
    else:
        form = AdminPasswordChangeForm()
    
    return render(request, 'superadmin/change_password.html', {
        'form': form,
        'tenant': tenant,
        'admin_user': admin_user
    })


# ==========================================
# GESTIÓN DE SUSCRIPCIONES
# ==========================================

@login_required
@superadmin_required
def subscription_plans(request):
    """Lista de planes de suscripción"""
    from django.db.models import ProtectedError
    
    plans = SubscriptionPlan.objects.all()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            name = request.POST.get('name')
            price = request.POST.get('price')
            billing_cycle = request.POST.get('billing_cycle')
            description = request.POST.get('description', '')
            
            SubscriptionPlan.objects.create(
                name=name,
                price=price,
                billing_cycle=billing_cycle,
                description=description
            )
            messages.success(request, f'Plan "{name}" creado exitosamente')
        
        elif action == 'edit':
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
            plan.name = request.POST.get('name')
            plan.price = request.POST.get('price')
            plan.billing_cycle = request.POST.get('billing_cycle')
            plan.description = request.POST.get('description', '')
            plan.save()
            messages.success(request, f'Plan "{plan.name}" actualizado')
        
        elif action == 'toggle':
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
            plan.is_active = not plan.is_active
            plan.save()
            status = "activado" if plan.is_active else "desactivado"
            messages.success(request, f'Plan "{plan.name}" {status}')
        
        elif action == 'delete':
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
            plan_name = plan.name
            try:
                plan.delete()
                messages.success(request, f'Plan "{plan_name}" eliminado')
            except ProtectedError:
                messages.error(request, f'No se puede eliminar el plan "{plan_name}" porque tiene pagos asociados. Puede desactivarlo en su lugar.')
        
        return redirect('superadmin:subscription_plans')
    
    return render(request, 'superadmin/subscription_plans.html', {'plans': plans})


@login_required
@superadmin_required
def tenant_subscription(request, pk):
    """Gestionar suscripción de un tenant"""
    tenant = get_object_or_404(Tenant, pk=pk)
    plans = SubscriptionPlan.objects.filter(is_active=True)
    payments = SubscriptionPayment.objects.filter(tenant=tenant).order_by('-payment_date')[:10]
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'assign_plan':
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
            
            today = timezone.now().date()
            
            # Calcular fecha de fin según el ciclo
            if plan.billing_cycle == 'monthly':
                end_date = today + relativedelta(months=1)
            else:  # annual
                end_date = today + relativedelta(years=1)
            
            # Crear pago
            payment = SubscriptionPayment.objects.create(
                tenant=tenant,
                plan=plan,
                amount=plan.price,
                status='confirmed',
                confirmed_date=timezone.now(),
                confirmed_by=request.user,
                period_start=today,
                period_end=end_date
            )
            
            # Actualizar tenant
            tenant.subscription_plan = plan
            tenant.subscription_start = today
            tenant.subscription_end = end_date
            tenant.status = Tenant.Status.ACTIVE
            tenant.is_active = True
            tenant.save()
            
            messages.success(request, f'Plan "{plan.name}" asignado a {tenant.name} hasta {end_date}')
        
        elif action == 'extend':
            if not tenant.subscription_plan:
                messages.error(request, 'El tenant no tiene un plan asignado')
                return redirect('superadmin:tenant_subscription', pk=pk)
            
            plan = tenant.subscription_plan
            
            # Extender desde la fecha actual de fin o desde hoy si ya expiró
            base_date = tenant.subscription_end if tenant.subscription_end and tenant.subscription_end > timezone.now().date() else timezone.now().date()
            
            if plan.billing_cycle == 'monthly':
                new_end = base_date + relativedelta(months=1)
            else:
                new_end = base_date + relativedelta(years=1)
            
            # Crear pago
            SubscriptionPayment.objects.create(
                tenant=tenant,
                plan=plan,
                amount=plan.price,
                status='confirmed',
                confirmed_date=timezone.now(),
                confirmed_by=request.user,
                period_start=base_date,
                period_end=new_end
            )
            
            tenant.subscription_end = new_end
            tenant.status = Tenant.Status.ACTIVE
            tenant.is_active = True
            tenant.save()
            
            messages.success(request, f'Suscripción extendida hasta {new_end}')
        
        elif action == 'cancel':
            tenant.subscription_plan = None
            tenant.subscription_end = None
            tenant.status = Tenant.Status.SUSPENDED
            tenant.save()
            messages.warning(request, f'Suscripción de {tenant.name} cancelada')
        
        return redirect('superadmin:tenant_subscription', pk=pk)
    
    context = {
        'tenant': tenant,
        'plans': plans,
        'payments': payments,
    }
    return render(request, 'superadmin/tenant_subscription.html', context)


@login_required
@superadmin_required
def subscription_payments(request):
    """Lista de todos los pagos de suscripción"""
    payments = SubscriptionPayment.objects.select_related('tenant', 'plan', 'confirmed_by').order_by('-payment_date')
    
    # Filtros
    status = request.GET.get('status')
    if status:
        payments = payments.filter(status=status)
    
    tenant_id = request.GET.get('tenant')
    if tenant_id:
        payments = payments.filter(tenant_id=tenant_id)
    
    context = {
        'payments': payments,
        'tenants': Tenant.objects.all(),
        'status_choices': SubscriptionPayment.PaymentStatus.choices,
    }
    return render(request, 'superadmin/subscription_payments.html', context)


# ==========================================
# BACKUP Y RESTAURACIÓN (SUPERADMIN)
# ==========================================

import os
from django.http import FileResponse, JsonResponse
from config.services import SystemBackupService, TenantBackupService


@login_required
@superadmin_required
def backup_dashboard(request):
    """Dashboard de backups del sistema."""
    service = SystemBackupService()
    system_backups = service.list_system_backups()
    sql_backups = service.list_sql_backups()
    
    # Formatear tamaños para system backups
    for backup in system_backups:
        size = backup['size']
        if size < 1024:
            backup['size_formatted'] = f"{size} B"
        elif size < 1024 * 1024:
            backup['size_formatted'] = f"{size / 1024:.1f} KB"
        else:
            backup['size_formatted'] = f"{size / (1024 * 1024):.2f} MB"
    
    # Formatear tamaños para SQL backups
    for backup in sql_backups:
        size = backup['size']
        if size < 1024:
            backup['size_formatted'] = f"{size} B"
        elif size < 1024 * 1024:
            backup['size_formatted'] = f"{size / 1024:.1f} KB"
        else:
            backup['size_formatted'] = f"{size / (1024 * 1024):.2f} MB"
    
    # Listar backups de tenants
    tenant_backups = []
    tenants = Tenant.objects.all()
    for tenant in tenants:
        tenant_service = TenantBackupService(tenant)
        backups = tenant_service.list_backups()
        for backup in backups:
            size = backup['size']
            if size < 1024:
                backup['size_formatted'] = f"{size} B"
            elif size < 1024 * 1024:
                backup['size_formatted'] = f"{size / 1024:.1f} KB"
            else:
                backup['size_formatted'] = f"{size / (1024 * 1024):.2f} MB"
            backup['tenant'] = tenant
            tenant_backups.append(backup)
    
    tenant_backups.sort(key=lambda x: x['created'], reverse=True)
    
    # Detectar tipo de base de datos
    from django.conf import settings as django_settings
    db_engine = django_settings.DATABASES['default'].get('ENGINE', '')
    if 'postgresql' in db_engine:
        db_type = 'PostgreSQL'
    elif 'sqlite' in db_engine:
        db_type = 'SQLite'
    else:
        db_type = 'Desconocido'
    
    return render(request, 'superadmin/backup/dashboard.html', {
        'system_backups': system_backups,
        'sql_backups': sql_backups,
        'tenant_backups': tenant_backups[:20],
        'tenants': tenants,
        'db_type': db_type,
    })


@login_required
@superadmin_required
def backup_create_system(request):
    """Crear backup completo del sistema."""
    if request.method == 'POST':
        try:
            service = SystemBackupService()
            filepath, filename = service.create_full_backup()
            messages.success(request, f'Backup del sistema "{filename}" creado exitosamente')
        except Exception as e:
            messages.error(request, f'Error al crear backup: {str(e)}')
    
    return redirect('superadmin:backup_dashboard')


@login_required
@superadmin_required
def backup_create_tenant(request, pk):
    """Crear backup de un tenant específico."""
    tenant = get_object_or_404(Tenant, pk=pk)
    
    if request.method == 'POST':
        try:
            service = SystemBackupService()
            filepath, filename = service.create_tenant_backup(tenant)
            messages.success(request, f'Backup de "{tenant.name}" creado: {filename}')
        except Exception as e:
            messages.error(request, f'Error al crear backup: {str(e)}')
    
    return redirect('superadmin:backup_dashboard')


@login_required
@superadmin_required
def backup_download_system(request, filename):
    """Descargar backup del sistema."""
    service = SystemBackupService()
    filepath = os.path.join(service.backup_dir, filename)
    
    if not os.path.exists(filepath):
        messages.error(request, 'Archivo no encontrado')
        return redirect('superadmin:backup_dashboard')
    
    return FileResponse(open(filepath, 'rb'), as_attachment=True, filename=filename)


@login_required
@superadmin_required
def backup_download_tenant(request, pk, filename):
    """Descargar backup de un tenant."""
    tenant = get_object_or_404(Tenant, pk=pk)
    service = TenantBackupService(tenant)
    filepath = os.path.join(service.backup_dir, filename)
    
    if not os.path.exists(filepath):
        messages.error(request, 'Archivo no encontrado')
        return redirect('superadmin:backup_dashboard')
    
    return FileResponse(open(filepath, 'rb'), as_attachment=True, filename=filename)


@login_required
@superadmin_required
def backup_delete_system(request, filename):
    """Eliminar backup del sistema."""
    if request.method == 'POST':
        service = SystemBackupService()
        if service.delete_backup(filename):
            messages.success(request, 'Backup eliminado')
        else:
            messages.error(request, 'No se pudo eliminar')
    
    return redirect('superadmin:backup_dashboard')


@login_required
@superadmin_required
def backup_delete_tenant(request, pk, filename):
    """Eliminar backup de un tenant."""
    tenant = get_object_or_404(Tenant, pk=pk)
    
    if request.method == 'POST':
        service = TenantBackupService(tenant)
        if service.delete_backup(filename):
            messages.success(request, 'Backup eliminado')
        else:
            messages.error(request, 'No se pudo eliminar')
    
    return redirect('superadmin:backup_dashboard')


@login_required
@superadmin_required
def backup_info_system(request, filename):
    """Información de backup del sistema."""
    service = SystemBackupService()
    filepath = os.path.join(service.backup_dir, filename)
    info = service.get_backup_info(filepath)
    return JsonResponse(info)


@login_required
@superadmin_required
def backup_restore_tenant(request, pk):
    """Restaurar backup de un tenant."""
    tenant = get_object_or_404(Tenant, pk=pk)
    
    if request.method == 'POST':
        filename = request.POST.get('filename')
        
        if filename:
            service = TenantBackupService(tenant)
            filepath = os.path.join(service.backup_dir, filename)
            
            if not os.path.exists(filepath):
                messages.error(request, 'Archivo no encontrado')
                return redirect('superadmin:backup_dashboard')
            
            clear_existing = request.POST.get('clear_existing') == 'on'
            result = service.restore_backup(filepath, clear_existing)
            
            if result.get('success'):
                total = sum(result.get('restored', {}).values())
                messages.success(request, f'Restauración completada. {total} registros restaurados.')
            else:
                messages.error(request, f'Error: {result.get("error", "Error desconocido")}')
        
        elif 'backup_file' in request.FILES:
            uploaded_file = request.FILES['backup_file']
            
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            try:
                service = TenantBackupService(tenant)
                clear_existing = request.POST.get('clear_existing') == 'on'
                result = service.restore_backup(tmp_path, clear_existing)
                
                if result.get('success'):
                    total = sum(result.get('restored', {}).values())
                    messages.success(request, f'Restauración completada. {total} registros.')
                else:
                    messages.error(request, f'Error: {result.get("error")}')
            finally:
                os.unlink(tmp_path)
    
    return redirect('superadmin:backup_dashboard')


# ==========================================
# BACKUP SQL (SUPERADMIN)
# ==========================================

@login_required
@superadmin_required
def backup_create_sql(request):
    """Crear backup SQL completo de la base de datos."""
    if request.method == 'POST':
        try:
            service = SystemBackupService()
            filepath, filename = service.create_sql_backup()
            messages.success(request, f'Backup SQL "{filename}" creado exitosamente')
        except Exception as e:
            messages.error(request, f'Error al crear backup SQL: {str(e)}')
    
    return redirect('superadmin:backup_dashboard')


@login_required
@superadmin_required
def backup_download_sql(request, filename):
    """Descargar backup SQL."""
    service = SystemBackupService()
    filepath = os.path.join(service.backup_dir, filename)
    
    if not os.path.exists(filepath):
        messages.error(request, 'Archivo no encontrado')
        return redirect('superadmin:backup_dashboard')
    
    return FileResponse(open(filepath, 'rb'), as_attachment=True, filename=filename)


@login_required
@superadmin_required
def backup_delete_sql(request, filename):
    """Eliminar backup SQL."""
    if request.method == 'POST':
        service = SystemBackupService()
        filepath = os.path.join(service.backup_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            messages.success(request, 'Backup SQL eliminado')
        else:
            messages.error(request, 'Archivo no encontrado')
    
    return redirect('superadmin:backup_dashboard')


@login_required
@superadmin_required
def backup_restore_sql(request):
    """Restaurar desde backup SQL."""
    if request.method == 'POST':
        service = SystemBackupService()
        
        filename = request.POST.get('filename')
        if filename:
            filepath = os.path.join(service.backup_dir, filename)
            if not os.path.exists(filepath):
                messages.error(request, 'Archivo no encontrado')
                return redirect('superadmin:backup_dashboard')
            
            result = service.restore_sql_backup(filepath)
            
            if result.get('success'):
                messages.success(request, result.get('message', 'Restauración completada'))
            else:
                messages.error(request, f'Error: {result.get("error", "Error desconocido")}')
        
        elif 'backup_file' in request.FILES:
            uploaded_file = request.FILES['backup_file']
            
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            try:
                result = service.restore_sql_backup(tmp_path)
                
                if result.get('success'):
                    messages.success(request, result.get('message', 'Restauración completada'))
                else:
                    messages.error(request, f'Error: {result.get("error")}')
            finally:
                os.unlink(tmp_path)
    
    return redirect('superadmin:backup_dashboard')
