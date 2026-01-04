from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Sum
from datetime import timedelta
from decimal import Decimal
from .models import MonthlyContract, ContractVehicle, ContractPayment
from .forms import MonthlyContractForm, ContractVehicleForm, ContractPaymentForm
from third_parties.models import ThirdParty, ThirdPartyVehicle
from parking.models import VehicleCategory
from parking.models_config import PaymentMethod


def get_tenant(request):
    """Obtiene el tenant del usuario autenticado"""
    if hasattr(request, 'user') and request.user.is_authenticated:
        return getattr(request.user, 'tenant', None)
    return getattr(request, 'tenant', None)


@login_required
def contract_list(request):
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, 'No tiene un parqueadero asignado')
        return redirect('dashboard')
    
    status_filter = request.GET.get('status', '')
    contracts = MonthlyContract.objects.all_tenants().filter(tenant=tenant).select_related(
        'third_party'
    ).prefetch_related('vehicles__vehicle').order_by('-start_date')
    
    if status_filter:
        contracts = contracts.filter(status=status_filter)
    
    # Contratos por vencer (próximos 5 días)
    today = timezone.now().date()
    expiring_soon = contracts.filter(
        status='active',
        end_date__lte=today + timedelta(days=5),
        end_date__gte=today
    )
    
    # Estadísticas
    stats = {
        'total': contracts.count(),
        'active': contracts.filter(status='active').count(),
        'expired': contracts.filter(status='expired').count(),
        'pending': contracts.filter(status='pending').count(),
    }
    
    return render(request, 'monthly_contracts/list.html', {
        'contracts': contracts,
        'expiring_soon': expiring_soon,
        'status_filter': status_filter,
        'stats': stats
    })


@login_required
def contract_create(request):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    # Obtener categorías para el formulario de vehículos
    categories = VehicleCategory.objects.all_tenants().filter(tenant=tenant)
    
    if request.method == 'POST':
        form = MonthlyContractForm(request.POST, tenant=tenant)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.tenant = tenant
            contract.created_by = request.user
            contract.save()
            
            # Procesar vehículos del formulario
            vehicle_ids = request.POST.getlist('vehicle_id')
            category_ids = request.POST.getlist('vehicle_category')
            rates = request.POST.getlist('vehicle_rate')
            
            total_rate = Decimal('0')
            vehicles_added = 0
            
            for i, vehicle_id in enumerate(vehicle_ids):
                if vehicle_id:
                    try:
                        vehicle = ThirdPartyVehicle.objects.get(pk=vehicle_id)
                        category = VehicleCategory.objects.all_tenants().get(pk=category_ids[i], tenant=tenant) if i < len(category_ids) and category_ids[i] else None
                        rate = Decimal(rates[i]) if i < len(rates) and rates[i] else Decimal('0')
                        
                        ContractVehicle.objects.create(
                            contract=contract,
                            vehicle=vehicle,
                            category=category,
                            monthly_rate=rate
                        )
                        total_rate += rate
                        vehicles_added += 1
                    except (ThirdPartyVehicle.DoesNotExist, VehicleCategory.DoesNotExist, ValueError) as e:
                        print(f"Error procesando vehículo: {e}")
                        continue
            
            # El monthly_rate se calcula automáticamente como property
            # basado en use_combo_rate/combo_rate o suma de vehículos
            
            if vehicles_added == 0:
                messages.warning(request, 'Contrato creado pero sin vehículos. Agregue vehículos desde el detalle.')
            else:
                messages.success(request, f'Contrato creado con {vehicles_added} vehículo(s)')
            return redirect('contract_detail', pk=contract.pk)
    else:
        # Valores iniciales
        today = timezone.now().date()
        initial = {
            'start_date': today,
            'end_date': today + timedelta(days=30)
        }
        form = MonthlyContractForm(tenant=tenant, initial=initial)
    
    return render(request, 'monthly_contracts/form.html', {
        'form': form,
        'categories': categories,
        'title': 'Nuevo Contrato'
    })


@login_required
def contract_detail(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(
        MonthlyContract.objects.all_tenants().prefetch_related('vehicles__vehicle', 'vehicles__category'), 
        pk=pk, tenant=tenant
    )
    payments = contract.payments.all().order_by('-payment_year', '-payment_month')
    
    # Calcular totales
    total_paid = payments.filter(is_confirmed=True).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Generar historial de meses desde el inicio del contrato
    today = timezone.now().date()
    contract_start = contract.start_date
    
    # Encontrar el último mes pagado
    last_payment = payments.filter(is_confirmed=True).order_by('-payment_year', '-payment_month').first()
    
    # Determinar hasta qué mes mostrar (el mayor entre: mes actual, último pago, o fin de contrato)
    end_month = today.month
    end_year = today.year
    
    if last_payment:
        if (last_payment.payment_year > end_year) or \
           (last_payment.payment_year == end_year and last_payment.payment_month > end_month):
            end_month = last_payment.payment_month
            end_year = last_payment.payment_year
    
    # Generar lista de meses desde inicio hasta el mes final
    months_history = []
    
    current_month = contract_start.month
    current_year = contract_start.year
    
    # Máximo 12 meses
    for _ in range(12):
        # No pasar del mes final
        if (current_year > end_year) or \
           (current_year == end_year and current_month > end_month):
            break
        
        payment = payments.filter(payment_month=current_month, payment_year=current_year).first()
        months_history.append({
            'month': current_month,
            'year': current_year,
            'month_name': ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][current_month],
            'paid': payment is not None and payment.is_confirmed,
            'payment': payment
        })
        
        # Avanzar al siguiente mes
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
    
    return render(request, 'monthly_contracts/detail.html', {
        'contract': contract,
        'payments': payments,
        'total_paid': total_paid,
        'months_history': months_history,
    })


@login_required
def contract_edit(request, pk):
    """Editar un contrato"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(MonthlyContract.objects.all_tenants(), pk=pk, tenant=tenant)
    categories = VehicleCategory.objects.all_tenants().filter(tenant=tenant)
    
    if request.method == 'POST':
        form = MonthlyContractForm(request.POST, instance=contract, tenant=tenant)
        if form.is_valid():
            form.save()
            
            # Eliminar vehículos existentes y recrear
            contract.vehicles.all().delete()
            
            vehicle_ids = request.POST.getlist('vehicle_id')
            category_ids = request.POST.getlist('vehicle_category')
            rates = request.POST.getlist('vehicle_rate')
            
            for i, vehicle_id in enumerate(vehicle_ids):
                if vehicle_id:
                    try:
                        vehicle = ThirdPartyVehicle.objects.get(pk=vehicle_id)
                        category = VehicleCategory.objects.all_tenants().get(pk=category_ids[i], tenant=tenant) if i < len(category_ids) and category_ids[i] else None
                        rate = Decimal(rates[i]) if i < len(rates) and rates[i] else Decimal('0')
                        
                        ContractVehicle.objects.create(
                            contract=contract,
                            vehicle=vehicle,
                            category=category,
                            monthly_rate=rate
                        )
                    except (ThirdPartyVehicle.DoesNotExist, VehicleCategory.DoesNotExist, ValueError):
                        continue
            
            messages.success(request, 'Contrato actualizado exitosamente')
            return redirect('contract_detail', pk=pk)
    else:
        form = MonthlyContractForm(instance=contract, tenant=tenant)
    
    return render(request, 'monthly_contracts/form.html', {
        'form': form,
        'contract': contract,
        'categories': categories,
        'title': 'Editar Contrato'
    })


@login_required
def contract_delete(request, pk):
    """Eliminar un contrato"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(MonthlyContract.objects.all_tenants(), pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        client_name = contract.third_party.full_name
        contract.delete()
        messages.success(request, f'Contrato de {client_name} eliminado')
        return redirect('contract_list')
    
    return render(request, 'monthly_contracts/confirm_delete.html', {
        'contract': contract
    })


@login_required
def contract_payment(request, pk):
    """Vista para registrar un pago de contrato para un mes específico"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(
        MonthlyContract.objects.all_tenants().prefetch_related('vehicles__vehicle'), 
        pk=pk, tenant=tenant
    )
    
    # Obtener métodos de pago
    payment_methods = PaymentMethod.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        allow_for_contracts=True
    ).order_by('order', 'name')
    
    today = timezone.now().date()
    
    # Obtener el mes/año del query string o calcular el próximo
    payment_month = request.GET.get('month')
    payment_year = request.GET.get('year')
    
    if payment_month and payment_year:
        # Limpiar separadores de miles (ej: 2.025 -> 2025)
        payment_month = int(str(payment_month).replace('.', '').replace(',', ''))
        payment_year = int(str(payment_year).replace('.', '').replace(',', ''))
    else:
        last_payment = contract.payments.filter(is_confirmed=True).order_by('-payment_year', '-payment_month').first()
        
        if last_payment:
            payment_month = last_payment.payment_month + 1
            payment_year = last_payment.payment_year
            if payment_month > 12:
                payment_month = 1
                payment_year += 1
        else:
            payment_month = contract.start_date.month
            payment_year = contract.start_date.year
    
    # Verificar si ya existe pago para este mes
    existing_payment = contract.payments.filter(
        payment_month=payment_month,
        payment_year=payment_year,
        is_confirmed=True
    ).exists()
    
    if existing_payment:
        month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        messages.warning(request, f'Ya existe un pago registrado para {month_names[payment_month]} {payment_year}')
        return redirect('contract_detail', pk=pk)
    
    if request.method == 'POST':
        payment_method_id = request.POST.get('payment_method')
        amount = Decimal(request.POST.get('amount', contract.monthly_rate))
        amount_received = request.POST.get('amount_received')
        reference = request.POST.get('reference', '')
        notes = request.POST.get('notes', '')
        
        try:
            payment = ContractPayment(
                contract=contract,
                tenant=tenant,
                payment_method_id=payment_method_id if payment_method_id else None,
                amount=amount,
                payment_month=payment_month,
                payment_year=payment_year,
                reference=reference,
                notes=notes,
                received_by=request.user,
                is_confirmed=True
            )
            
            if amount_received:
                payment.amount_received = Decimal(amount_received)
            
            payment.save()
            
            month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                           "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            messages.success(request, f'Pago de ${amount:,.0f} registrado para {month_names[payment_month]} {payment_year}')
            return redirect('contract_detail', pk=pk)
            
        except Exception as e:
            messages.error(request, f'Error al registrar el pago: {str(e)}')
    
    month_names = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    return render(request, 'monthly_contracts/payment.html', {
        'contract': contract,
        'payment_methods': payment_methods,
        'payment_month': payment_month,
        'payment_year': payment_year,
        'month_name': month_names[payment_month],
        'amount': contract.monthly_rate
    })


@login_required
def contract_renew(request, pk):
    """Vista para renovar un contrato (alias de payment)"""
    return contract_payment(request, pk)


@login_required
def pending_payments(request):
    """Vista de cuentas por cobrar / contratos pendientes"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    today = timezone.now().date()
    
    expired = MonthlyContract.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        end_date__lt=today
    ).select_related('third_party').prefetch_related('vehicles__vehicle').order_by('end_date')
    
    expiring = MonthlyContract.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        status='active',
        end_date__gte=today,
        end_date__lte=today + timedelta(days=7)
    ).select_related('third_party').prefetch_related('vehicles__vehicle').order_by('end_date')
    
    pending = MonthlyContract.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        status='pending'
    ).select_related('third_party').prefetch_related('vehicles__vehicle').order_by('-created_at')
    
    total_expired = sum(c.monthly_rate for c in expired)
    total_expiring = sum(c.monthly_rate for c in expiring)
    total_pending = sum(c.monthly_rate for c in pending)
    
    return render(request, 'monthly_contracts/pending.html', {
        'expired': expired,
        'expiring': expiring,
        'pending': pending,
        'total_expired': total_expired,
        'total_expiring': total_expiring,
        'total_pending': total_pending,
        'total_all': total_expired + total_expiring + total_pending
    })


@login_required
def payment_history(request):
    """Historial de todos los pagos de mensualidades"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    
    payments = ContractPayment.objects.filter(
        tenant=tenant,
        is_confirmed=True
    ).select_related('contract', 'contract__third_party', 'payment_method', 'received_by')
    
    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)
    
    payments = payments.order_by('-payment_date')
    
    total = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    return render(request, 'monthly_contracts/payment_history.html', {
        'payments': payments,
        'total': total,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
def print_payment_receipt(request, payment_id):
    """Imprimir recibo de pago"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    payment = get_object_or_404(ContractPayment, pk=payment_id, tenant=tenant)
    
    return render(request, 'monthly_contracts/receipt.html', {
        'payment': payment,
        'contract': payment.contract,
        'tenant': tenant,
        'current_time': timezone.now()
    })


@login_required
def get_client_vehicles(request):
    """API para obtener vehículos de un cliente"""
    tenant = get_tenant(request)
    third_party_id = request.GET.get('third_party_id')
    
    if not tenant or not third_party_id:
        return JsonResponse({'vehicles': []})
    
    vehicles = ThirdPartyVehicle.objects.filter(
        third_party_id=third_party_id,
        third_party__tenant=tenant,
        is_active=True
    ).values('id', 'plate', 'brand', 'model', 'color', 'vehicle_type')
    
    return JsonResponse({'vehicles': list(vehicles)})


@login_required
def add_contract_vehicle(request, pk):
    """Agregar un vehículo a un contrato existente"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(MonthlyContract.objects.all_tenants(), pk=pk, tenant=tenant)
    categories = VehicleCategory.objects.all_tenants().filter(tenant=tenant)
    
    # Vehículos del cliente que no están en el contrato
    existing_vehicle_ids = contract.vehicles.values_list('vehicle_id', flat=True)
    available_vehicles = ThirdPartyVehicle.objects.filter(
        third_party=contract.third_party,
        is_active=True
    ).exclude(id__in=existing_vehicle_ids)
    
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle')
        category_id = request.POST.get('category')
        rate = request.POST.get('monthly_rate')
        
        try:
            vehicle = ThirdPartyVehicle.objects.get(pk=vehicle_id)
            # Buscar categoría sin filtro de tenant primero para debug
            try:
                category = VehicleCategory.objects.all_tenants().get(pk=category_id)
                # Verificar que pertenece al tenant
                if category.tenant_id != tenant.id:
                    raise VehicleCategory.DoesNotExist(f"Categoría {category_id} no pertenece al tenant {tenant.name}")
            except VehicleCategory.DoesNotExist:
                # Listar categorías disponibles para debug
                available_cats = list(VehicleCategory.objects.all_tenants().filter(tenant=tenant).values_list('id', 'name'))
                raise VehicleCategory.DoesNotExist(f"Categoría ID={category_id} no encontrada. Disponibles: {available_cats}")
            
            ContractVehicle.objects.create(
                contract=contract,
                vehicle=vehicle,
                category=category,
                monthly_rate=Decimal(rate)
            )
            messages.success(request, f'Vehículo {vehicle.plate} agregado al contrato')
        except Exception as e:
            messages.error(request, f'Error al agregar vehículo: {str(e)}')
        
        return redirect('contract_detail', pk=pk)
    
    return render(request, 'monthly_contracts/add_vehicle.html', {
        'contract': contract,
        'available_vehicles': available_vehicles,
        'categories': categories
    })


@login_required
def remove_contract_vehicle(request, pk, vehicle_pk):
    """Eliminar un vehículo de un contrato"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(MonthlyContract.objects.all_tenants(), pk=pk, tenant=tenant)
    contract_vehicle = get_object_or_404(ContractVehicle, pk=vehicle_pk, contract=contract)
    
    if request.method == 'POST':
        plate = contract_vehicle.vehicle.plate
        contract_vehicle.delete()
        messages.success(request, f'Vehículo {plate} eliminado del contrato')
        return redirect('contract_detail', pk=pk)
    
    return render(request, 'monthly_contracts/remove_vehicle.html', {
        'contract': contract,
        'contract_vehicle': contract_vehicle
    })
