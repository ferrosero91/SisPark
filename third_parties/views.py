from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.db import IntegrityError
from .models import ThirdParty, ThirdPartyVehicle
from .forms import ThirdPartyForm, ThirdPartyVehicleForm


def get_tenant(request):
    """Obtiene el tenant del usuario autenticado"""
    if hasattr(request, 'user') and request.user.is_authenticated:
        return getattr(request.user, 'tenant', None)
    return getattr(request, 'tenant', None)


@login_required
def third_party_list(request):
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, 'No tiene un parqueadero asignado')
        return redirect('dashboard')
    
    search = request.GET.get('search', '')
    third_parties = ThirdParty.objects.all_tenants().filter(tenant=tenant)
    
    if search:
        third_parties = third_parties.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(document_number__icontains=search) |
            Q(vehicles__plate__icontains=search)
        ).distinct()
    
    return render(request, 'third_parties/list.html', {
        'third_parties': third_parties,
        'search': search
    })


@login_required
def third_party_create(request):
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, 'No tiene un parqueadero asignado')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ThirdPartyForm(request.POST)
        if form.is_valid():
            try:
                third_party = form.save(commit=False)
                third_party.tenant = tenant
                third_party.save()
                messages.success(request, f'Cliente {third_party.full_name} creado exitosamente')
                return redirect('third_party_detail', pk=third_party.pk)
            except IntegrityError:
                messages.error(request, 'Ya existe un cliente con ese tipo y número de documento')
    else:
        form = ThirdPartyForm()
    
    return render(request, 'third_parties/form.html', {
        'form': form,
        'title': 'Nuevo Cliente'
    })


@login_required
def third_party_detail(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    third_party = get_object_or_404(ThirdParty.objects.all_tenants(), pk=pk, tenant=tenant)
    vehicles = third_party.vehicles.all()
    contracts = third_party.contracts.all().order_by('-start_date')
    
    return render(request, 'third_parties/detail.html', {
        'third_party': third_party,
        'vehicles': vehicles,
        'contracts': contracts
    })


@login_required
def third_party_edit(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    third_party = get_object_or_404(ThirdParty.objects.all_tenants(), pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        form = ThirdPartyForm(request.POST, instance=third_party)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cliente actualizado exitosamente')
            return redirect('third_party_detail', pk=pk)
    else:
        form = ThirdPartyForm(instance=third_party)
    
    return render(request, 'third_parties/form.html', {
        'form': form,
        'third_party': third_party,
        'title': 'Editar Cliente'
    })


@login_required
def vehicle_add(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    third_party = get_object_or_404(ThirdParty.objects.all_tenants(), pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        form = ThirdPartyVehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.third_party = third_party
            vehicle.save()
            messages.success(request, f'Vehículo {vehicle.plate} agregado')
            return redirect('third_party_detail', pk=pk)
    else:
        form = ThirdPartyVehicleForm()
    
    return render(request, 'third_parties/vehicle_form.html', {
        'form': form,
        'third_party': third_party
    })


@login_required
def third_party_delete(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')
    
    third_party = get_object_or_404(ThirdParty.objects.all_tenants(), pk=pk, tenant=tenant)
    
    if request.method == 'POST':
        name = third_party.full_name
        third_party.delete()
        messages.success(request, f'Cliente {name} eliminado exitosamente')
        return redirect('third_party_list')
    
    return render(request, 'third_parties/confirm_delete.html', {
        'third_party': third_party
    })
