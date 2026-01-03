from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Sum, Count
from datetime import timedelta
from decimal import Decimal
from .models import MonthlyContract, ContractPayment
from .forms import MonthlyContractForm, ContractPaymentForm
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
        'third_party', 'vehicle', 'category'
    ).order_by('-start_date')
    
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
    
    if request.method == 'POST':
        form = MonthlyContractForm(request.POST, tenant=tenant)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.tenant = tenant
            contract.created_by = request.user
            contract.save()
            
            messages.success(request, 'Contrato creado exitosamente')
            
            # Redirigir a registrar pago si se marcó
            if form.cleaned_data.get('register_payment'):
                return redirect('contract_payment', pk=contract.pk)
            
            return redirect('contract_detail', pk=contract.pk)
    else:
        form = MonthlyContractForm(tenant=tenant)
    
    return render(request, 'monthly_contracts/form.html', {
        'form': form,
        'title': 'Nuevo Contrato'
    })


@login_required
def contract_detail(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(MonthlyContract.objects.all_tenants(), pk=pk, tenant=tenant)
    payments = contract.payments.all().order_by('-payment_date')
    
    # Calcular totales
    total_paid = payments.filter(is_confirmed=True).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    return render(request, 'monthly_contracts/detail.html', {
        'contract': contract,
        'payments': payments,
        'total_paid': total_paid
    })


@login_required
def contract_payment(request, pk):
    """Vista para registrar un pago de contrato"""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    contract = get_object_or_404(MonthlyContract.objects.all_tenants(), pk=pk, tenant=tenant)
    
    # Obtener métodos de pago
    payment_methods = PaymentMethod.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        allow_for_contracts=True
    ).order_by('order', 'name')
    
    if request.method == 'POST':
        form = ContractPaymentForm(request.POST, tenant=tenant)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.contract = contract
            payment.tenant = tenant
            payment.received_by = request.user
            
            # Calcular período
            today = timezone.now().date()
            payment.period_start = contract.end_date if contract.end_date >= today else today
            payment.period_end = payment.period_start + timedelta(days=30 * payment.months_paid)
            
            payment.save()
            
            # Renovar contrato
            contract.renew(months=payment.months_paid)
            
            messages.success(request, f'Pago de ${payment.amount:,.0f} registrado exitosamente')
            return redirect('contract_detail', pk=pk)
    else:
        form = ContractPaymentForm(tenant=tenant, initial={
            'amount': contract.monthly_rate,
            'months_paid': 1
        })
    
    return render(request, 'monthly_contracts/payment.html', {
        'contract': contract,
        'form': form,
        'payment_methods': payment_methods
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
    
    # Contratos vencidos
    expired = MonthlyContract.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        end_date__lt=today
    ).select_related('third_party', 'vehicle', 'category').order_by('end_date')
    
    # Contratos por vencer (próximos 7 días)
    expiring = MonthlyContract.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        status='active',
        end_date__gte=today,
        end_date__lte=today + timedelta(days=7)
    ).select_related('third_party', 'vehicle', 'category').order_by('end_date')
    
    # Contratos pendientes de pago inicial
    pending = MonthlyContract.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True,
        status='pending'
    ).select_related('third_party', 'vehicle', 'category').order_by('-created_at')
    
    # Calcular totales
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
    
    # Filtros
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    
    payments = ContractPayment.objects.filter(
        tenant=tenant,
        is_confirmed=True
    ).select_related('contract', 'contract__third_party', 'contract__vehicle', 'payment_method', 'received_by')
    
    if date_from:
        payments = payments.filter(payment_date__date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__date__lte=date_to)
    
    payments = payments.order_by('-payment_date')
    
    # Totales
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
def get_vehicle_info(request):
    """API para obtener info del vehículo al seleccionar tercero"""
    tenant = get_tenant(request)
    third_party_id = request.GET.get('third_party_id')
    
    if not tenant or not third_party_id:
        return JsonResponse({'vehicles': []})
    
    vehicles = ThirdPartyVehicle.objects.filter(
        third_party_id=third_party_id,
        third_party__tenant=tenant,
        is_active=True
    ).values('id', 'plate', 'brand', 'model', 'color')
    
    return JsonResponse({'vehicles': list(vehicles)})
