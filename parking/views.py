# Python standard library
from datetime import datetime, timedelta

# Django core
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.timezone import now

# Django database
from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import TruncDate

# Django views
from django.views.generic import CreateView, ListView, TemplateView
from django.views.generic.edit import DeleteView

# Local imports
from .forms import CategoryForm, ParkingTicketForm
from .models import ParkingTicket, VehicleCategory, Caja

# Tenant imports
from tenants.context import get_current_tenant, set_current_tenant
from third_parties.models import ThirdPartyVehicle
from monthly_contracts.models import MonthlyContract


def get_tenant_from_user(user):
    if hasattr(user, 'tenant') and user.tenant:
        return user.tenant
    return None


@login_required
def pagina_inicial(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'registration/login.html')


class CategoryListView(ListView):
    model = VehicleCategory
    template_name = 'parking/category_list.html'
    
    def get_queryset(self):
        tenant = get_tenant_from_user(self.request.user)
        if tenant:
            return VehicleCategory.objects.all_tenants().filter(tenant=tenant)
        return VehicleCategory.objects.none()


class CategoryCreateView(CreateView):
    model = VehicleCategory
    form_class = CategoryForm
    template_name = 'parking/category_form.html'
    success_url = reverse_lazy('category-list')

    def form_valid(self, form):
        tenant = get_tenant_from_user(self.request.user)
        if tenant:
            set_current_tenant(tenant)
            form.instance.tenant = tenant
            messages.success(self.request, "Categoría creada con éxito.")
            return super().form_valid(form)
        else:
            messages.error(self.request, "No tiene un parqueadero asignado.")
            return self.form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, error)
                else:
                    field_name = form.fields.get(field).label if field in form.fields else field
                    messages.error(self.request, f"{field_name}: {error}")
        return super().form_invalid(form)


class VehicleEntryView(CreateView):
    model = ParkingTicket
    form_class = ParkingTicketForm
    template_name = 'parking/vehicle_entry.html'
    success_url = reverse_lazy('print-ticket')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = get_tenant_from_user(self.request.user)
        return kwargs

    def form_valid(self, form):
        try:
            tenant = get_tenant_from_user(self.request.user)
            if tenant:
                set_current_tenant(tenant)
                form.instance.tenant = tenant
            
            category = form.cleaned_data['category']
            placa = form.cleaned_data['placa'].upper()
            
            if tenant:
                # Usar el servicio de detección de contratos
                from monthly_contracts.services import ContractDetectionService, RateType
                
                detection_service = ContractDetectionService(tenant)
                rate_result = detection_service.detect_rate(placa, category)
                
                # Asignar tercero y contrato si existe
                if rate_result.third_party:
                    form.instance.third_party = rate_result.third_party
                
                if rate_result.vehicle:
                    # Guardar referencia al vehículo registrado
                    pass
                
                if rate_result.contract:
                    form.instance.monthly_contract = rate_result.contract
                    form.instance.is_monthly_entry = True
                
                # Guardar info de tarifa especial en sesión para mostrar en ticket
                if rate_result.rate_type != RateType.REGULAR:
                    self.request.session['rate_info'] = {
                        'type': rate_result.rate_type.value,
                        'message': rate_result.message,
                        'days_remaining': rate_result.days_remaining
                    }
            
            if category.name.upper() in ['MOTOS', 'MOTO']:
                cascos = self.request.POST.get('cascos', 0)
                form.instance.cascos = int(cascos) if cascos else 0
            
            response = super().form_valid(form)
            self.request.session['ticket_id'] = str(self.object.id)
            return response
        except IntegrityError:
            messages.error(self.request, 'Este vehículo ya se encuentra en el estacionamiento.')
            return self.form_invalid(form)


@login_required
def vehicle_exit(request):
    tenant = get_tenant_from_user(request.user)
    
    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        action = request.POST.get('action', 'search')
        
        ticket_query = ParkingTicket.objects.all_tenants().filter(
            placa__iexact=identifier,
            exit_time=None
        )
        
        if tenant:
            ticket_query = ticket_query.filter(tenant=tenant)
        
        ticket = ticket_query.first()

        if ticket:
            # Solo buscar - no procesar salida aún
            if action == 'search':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    # Usar servicio de cálculo de tarifas
                    from monthly_contracts.services import RateCalculationService
                    
                    rate_service = RateCalculationService(tenant)
                    rate_info = rate_service.calculate_exit_fee(ticket)
                    
                    duration = ticket.get_current_duration()
                    duration_str = f"{duration['hours']}h {duration['minutes']}m"
                    
                    return JsonResponse({
                        'amount': float(rate_info['amount']),
                        'original_amount': float(rate_info.get('original_amount', rate_info['amount'])),
                        'discount': float(rate_info.get('discount', 0)),
                        'duration': duration_str,
                        'placa': ticket.placa,
                        'entry_time': ticket.entry_time.strftime('%d/%m/%Y %H:%M'),
                        'ticket_id': str(ticket.id),
                        'is_monthly': ticket.is_monthly_entry or rate_info['is_contract'],
                        'rate_type': rate_info['rate_type'],
                        'rate_message': rate_info['message'],
                        'days_remaining': rate_info.get('days_remaining', 0),
                        'category': ticket.category.name if ticket.category else '',
                        'marca': ticket.marca or '',
                        'color': ticket.color or '',
                        'third_party': ticket.third_party.full_name if ticket.third_party else None,
                    })
            
            # Confirmar salida - ahora sí procesar
            elif action == 'confirm':
                try:
                    ticket.exit_time = timezone.now()
                    ticket.amount_paid = ticket.calculate_fee()
                    ticket.save()
                    
                    return JsonResponse({
                        'success': True,
                        'ticket_id': str(ticket.id),
                        'amount': float(ticket.amount_paid)
                    })
                except Exception as e:
                    return JsonResponse({'error': str(e)}, status=500)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Vehículo no encontrado'}, status=404)
        messages.error(request, 'Vehículo no encontrado')
        return redirect('vehicle-exit')

    placa = request.GET.get('placa', '')
    
    return render(request, 'parking/vehicle_exit.html', {
        'placa': placa
    })


@login_required
def vehicle_payment(request):
    """Vista para procesar el pago de un vehículo"""
    tenant = get_tenant_from_user(request.user)
    ticket_id = request.GET.get('ticket_id')
    
    if not ticket_id:
        messages.error(request, 'No se especificó un ticket')
        return redirect('vehicle-exit')
    
    ticket_query = ParkingTicket.objects.all_tenants().filter(id=ticket_id, exit_time=None)
    if tenant:
        ticket_query = ticket_query.filter(tenant=tenant)
    ticket = ticket_query.first()
    
    if not ticket:
        messages.error(request, 'Ticket no encontrado o ya procesado')
        return redirect('vehicle-exit')
    
    # Calcular duración y monto
    duration = ticket.get_current_duration()
    duration_str = f"{duration['hours']}h {duration['minutes']}m"
    amount = ticket.calculate_fee()
    
    # Obtener métodos de pago
    from parking.models_config import PaymentMethod
    payment_methods = []
    first_is_cash = False
    if tenant:
        payment_methods = list(PaymentMethod.objects.all_tenants().filter(
            tenant=tenant, 
            is_active=True, 
            allow_for_exit=True,
            is_credit=False
        ).order_by('order', 'name'))
        if payment_methods:
            first_is_cash = payment_methods[0].payment_type == 'cash'
    
    return render(request, 'parking/vehicle_payment.html', {
        'ticket': ticket,
        'duration': duration_str,
        'amount': amount,
        'payment_methods': payment_methods,
        'first_is_cash': first_is_cash
    })


@login_required
def print_exit_ticket(request):
    tenant = get_tenant_from_user(request.user)
    
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        amount_received = request.POST.get('amount_received')
        payment_method_id = request.POST.get('payment_method')
        is_cash = request.POST.get('is_cash') == '1'

        if ticket_id and amount_received:
            try:
                from parking.models_config import PaymentMethod
                
                ticket_query = ParkingTicket.objects.all_tenants().filter(id=ticket_id)
                if tenant:
                    ticket_query = ticket_query.filter(tenant=tenant)
                ticket = ticket_query.first()
                
                if not ticket:
                    messages.error(request, 'Ticket no encontrado')
                    return redirect('dashboard')
                
                # Obtener método de pago
                payment_method = None
                if payment_method_id:
                    payment_method = PaymentMethod.objects.all_tenants().filter(
                        id=payment_method_id, tenant=tenant
                    ).first()
                
                # Si el ticket no tiene exit_time, procesar la salida ahora
                if not ticket.exit_time:
                    ticket.exit_time = timezone.now()
                    ticket.amount_paid = ticket.calculate_fee()
                    ticket.payment_method = payment_method
                    ticket.save()
                
                amount_received = float(amount_received)
                amount_paid = float(ticket.amount_paid or 0)
                change = amount_received - amount_paid if is_cash else 0

                return render(request, 'parking/print_exit_ticket.html', {
                    'ticket': ticket,
                    'parking_lot': tenant,
                    'amount_received': amount_received,
                    'change': change,
                    'is_cash': is_cash,
                    'current_time': timezone.now(),
                })
            except ValueError:
                messages.error(request, 'El monto recibido no es válido')
                return redirect('vehicle-exit')
            except Exception as e:
                messages.error(request, f'Error al imprimir ticket: {str(e)}')
                return redirect('dashboard')

    messages.warning(request, 'No se especificó un ticket para imprimir')
    return redirect('dashboard')


@login_required
def dashboard(request):
    tenant = get_tenant_from_user(request.user)
    today = timezone.now().date()
    start_date = today - timedelta(days=7)
    
    if tenant:
        base_query = ParkingTicket.objects.all_tenants().filter(tenant=tenant)
    else:
        base_query = ParkingTicket.objects.none()
    
    recent_tickets = base_query.filter(
        entry_time__date__gte=start_date,
        entry_time__date__lte=today
    )

    recent_revenue = base_query.filter(
        exit_time__date__gte=start_date,
        exit_time__date__lte=today,
        exit_time__isnull=False,
        amount_paid__isnull=False
    )

    active_vehicles = base_query.filter(
        exit_time__isnull=True
    ).select_related('category')

    daily_stats = base_query.filter(
        exit_time__date__gte=start_date,
        exit_time__date__lte=today,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).values('exit_time__date').annotate(
        revenue=Sum('amount_paid'),
        count=Count('id')
    ).order_by('exit_time__date')

    category_stats = base_query.filter(
        exit_time__date__gte=start_date,
        exit_time__date__lte=today,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).values('category__name').annotate(
        count=Count('id'),
        revenue=Sum('amount_paid')
    )

    # Usar servicio de contratos para obtener resumen
    contracts_expiring = []
    contract_summary = {}
    if tenant:
        from monthly_contracts.services import ContractDetectionService, get_contract_summary
        
        detection_service = ContractDetectionService(tenant)
        contracts_expiring = detection_service.check_expiring_contracts(days=5)
        contract_summary = get_contract_summary(tenant)

    stats = {
        'daily': {
            'total_vehicles': recent_tickets.count(),
            'total_revenue': recent_revenue.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        },
        'category': category_stats,
        'active_vehicles': active_vehicles.count(),
        'active_vehicles_list': active_vehicles
    }

    context = {
        'stats': stats,
        'daily_stats': [
            {
                'date': stat['exit_time__date'].strftime('%d/%m/%Y'),
                'revenue': stat['revenue'] or 0,
                'count': stat['count'] or 0,
            }
            for stat in daily_stats
        ],
        'current_time': timezone.now(),
        'tenant': tenant,
        'contracts_expiring': contracts_expiring,
        'contract_summary': contract_summary
    }

    return render(request, 'parking/dashboard.html', context)


@login_required
def print_ticket(request):
    tenant = get_tenant_from_user(request.user)
    ticket_id = request.GET.get('ticket_id') or request.session.get('ticket_id')
    
    if ticket_id:
        try:
            ticket_query = ParkingTicket.objects.all_tenants().filter(id=ticket_id)
            if tenant:
                ticket_query = ticket_query.filter(tenant=tenant)
            ticket = ticket_query.first()
            
            if not ticket:
                messages.error(request, 'Ticket no encontrado')
                return redirect('dashboard')
            
            if 'ticket_id' in request.session:
                del request.session['ticket_id']
            
            return render(request, 'parking/print_ticket.html', {
                'ticket': ticket,
                'parking_lot': tenant,
                'is_reprint': bool(request.GET.get('ticket_id')),
                'current_time': timezone.now(),
                'duration': ticket.get_duration() if ticket.exit_time else ticket.get_current_duration(),
                'current_fee': ticket.amount_paid if ticket.exit_time else ticket.calculate_current_fee()
            })
        except Exception as e:
            messages.error(request, f'Error al imprimir ticket: {str(e)}')
            return redirect('dashboard')
    
    messages.warning(request, 'No se especificó un ticket para imprimir')
    return redirect('vehicle-entry')


class ReportView(TemplateView):
    template_name = 'parking/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_tenant_from_user(self.request.user)
        report_type = self.request.GET.get('type', 'general')
        period = self.request.GET.get('period', 'today')

        # Usar hora local de Colombia
        today = timezone.localtime(timezone.now())
        
        # Manejar períodos predefinidos
        if period == 'yesterday':
            yesterday = today - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            start_date = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'month':
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'year':
            start_date = today.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == 'custom':
            start_str = self.request.GET.get('start_date')
            end_str = self.request.GET.get('end_date')
            if start_str and end_str:
                start_date = timezone.make_aware(datetime.strptime(f"{start_str} 00:00:00", '%Y-%m-%d %H:%M:%S'))
                end_date = timezone.make_aware(datetime.strptime(f"{end_str} 23:59:59", '%Y-%m-%d %H:%M:%S'))
            else:
                start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:  # today (default)
            period = 'today'
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)

        if tenant:
            tickets = ParkingTicket.objects.all_tenants().filter(
                tenant=tenant,
                exit_time__isnull=False,
                exit_time__range=(start_date, end_date)
            ).exclude(amount_paid__isnull=True).select_related('category', 'payment_method')
        else:
            tickets = ParkingTicket.objects.none()

        # Resumen general
        summary = tickets.aggregate(
            total_vehicles=Count('id'),
            total_revenue=Sum('amount_paid'),
            avg_duration=Avg(F('exit_time') - F('entry_time')),
            avg_revenue=Avg('amount_paid')
        )

        if summary['avg_duration'] is not None:
            summary['avg_duration'] = summary['avg_duration'].total_seconds() / 3600

        # Por categoría
        category_stats = list(tickets.values('category__name').annotate(
            count=Count('id'),
            revenue=Sum('amount_paid'),
        ).order_by('-revenue'))

        # Por método de pago
        from collections import defaultdict
        from decimal import Decimal
        
        payment_stats = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
        for ticket in tickets:
            method_name = ticket.payment_method.name if ticket.payment_method else 'Efectivo'
            payment_stats[method_name]['count'] += 1
            payment_stats[method_name]['total'] += ticket.amount_paid or Decimal('0')
            if ticket.payment_method:
                payment_stats[method_name]['icon'] = ticket.payment_method.icon
                payment_stats[method_name]['is_cash'] = ticket.payment_method.payment_type == 'cash'
            else:
                payment_stats[method_name]['icon'] = 'fa-money-bill'
                payment_stats[method_name]['is_cash'] = True
        
        payment_stats_list = [{'name': k, **v} for k, v in payment_stats.items()]
        payment_stats_list.sort(key=lambda x: -x['total'])

        # Ingresos diarios
        daily_stats = list(tickets.annotate(
            date=TruncDate('exit_time')
        ).values('date').annotate(
            count=Count('id'),
            revenue=Sum('amount_paid')
        ).order_by('date'))

        # Vehículos frecuentes
        frequent_vehicles = list(tickets.values('placa').annotate(
            visits=Count('id'),
            total_spent=Sum('amount_paid')
        ).order_by('-visits')[:10])

        # Mensualidades
        from monthly_contracts.models import MonthlyContract, ContractPayment
        
        contract_payments = ContractPayment.objects.filter(
            tenant=tenant,
            payment_date__range=(start_date, end_date),
            is_confirmed=True
        ).select_related('payment_method', 'contract__third_party', 'contract__vehicle') if tenant else []
        
        contracts_revenue = sum(p.amount for p in contract_payments)
        
        # Cuentas por cobrar
        today_date = now().date()
        pending_contracts = MonthlyContract.objects.all_tenants().filter(
            tenant=tenant,
            is_active=True,
            end_date__lt=today_date
        ).select_related('third_party', 'vehicle') if tenant else []
        
        pending_total = sum(c.monthly_rate for c in pending_contracts)

        # Historial de salidas (últimas 50)
        recent_exits = tickets.order_by('-exit_time')[:50]

        context.update({
            'start_date': start_date,
            'end_date': end_date,
            'period': period,
            'report_type': report_type,
            'summary': summary,
            'category_stats': category_stats,
            'payment_stats': payment_stats_list,
            'daily_stats': daily_stats,
            'frequent_vehicles': frequent_vehicles,
            'contract_payments': contract_payments,
            'contracts_revenue': contracts_revenue,
            'pending_contracts': pending_contracts,
            'pending_total': pending_total,
            'recent_exits': recent_exits,
            'parking_lot': tenant,
            'total_general': float(summary['total_revenue'] or 0) + float(contracts_revenue),
        })
        return context


@login_required
def export_report_excel(request):
    """Exportar reporte a Excel"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from django.http import HttpResponse
    
    tenant = get_tenant_from_user(request.user)
    start_str = request.GET.get('start_date', timezone.now().date().isoformat())
    end_str = request.GET.get('end_date', timezone.now().date().isoformat())
    
    try:
        start_date = datetime.strptime(f"{start_str} 00:00:00", '%Y-%m-%d %H:%M:%S')
        end_date = datetime.strptime(f"{end_str} 23:59:59", '%Y-%m-%d %H:%M:%S')
    except ValueError:
        start_date = end_date = timezone.now()
    
    # Obtener datos
    tickets = ParkingTicket.objects.all_tenants().filter(
        tenant=tenant,
        exit_time__isnull=False,
        exit_time__range=(start_date, end_date)
    ).exclude(amount_paid__isnull=True).select_related('category', 'payment_method').order_by('-exit_time')
    
    from monthly_contracts.models import ContractPayment
    contract_payments = ContractPayment.objects.filter(
        tenant=tenant,
        payment_date__range=(start_date, end_date),
        is_confirmed=True
    ).select_related('payment_method', 'contract__third_party', 'contract__vehicle')
    
    # Crear workbook
    wb = openpyxl.Workbook()
    
    # Estilos
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )
    
    # Hoja 1: Tickets de parqueadero
    ws1 = wb.active
    ws1.title = "Parqueadero"
    
    headers = ['Fecha', 'Placa', 'Categoría', 'Entrada', 'Salida', 'Duración', 'Método Pago', 'Monto']
    for col, header in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    
    for row, ticket in enumerate(tickets, 2):
        duration = (ticket.exit_time - ticket.entry_time).total_seconds() / 3600
        ws1.cell(row=row, column=1, value=ticket.exit_time.strftime('%d/%m/%Y'))
        ws1.cell(row=row, column=2, value=ticket.placa)
        ws1.cell(row=row, column=3, value=ticket.category.name if ticket.category else '')
        ws1.cell(row=row, column=4, value=ticket.entry_time.strftime('%H:%M'))
        ws1.cell(row=row, column=5, value=ticket.exit_time.strftime('%H:%M'))
        ws1.cell(row=row, column=6, value=f"{duration:.1f}h")
        ws1.cell(row=row, column=7, value=ticket.payment_method.name if ticket.payment_method else 'Efectivo')
        ws1.cell(row=row, column=8, value=float(ticket.amount_paid or 0))
    
    # Ajustar anchos
    for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
        ws1.column_dimensions[col].width = 14
    
    # Hoja 2: Mensualidades
    ws2 = wb.create_sheet("Mensualidades")
    headers2 = ['Fecha', 'Vehículo', 'Cliente', 'Método Pago', 'Monto']
    for col, header in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
    
    for row, payment in enumerate(contract_payments, 2):
        ws2.cell(row=row, column=1, value=payment.payment_date.strftime('%d/%m/%Y %H:%M'))
        ws2.cell(row=row, column=2, value=payment.contract.vehicle.plate if payment.contract and payment.contract.vehicle else '')
        ws2.cell(row=row, column=3, value=str(payment.contract.third_party) if payment.contract else '')
        ws2.cell(row=row, column=4, value=payment.payment_method.name if payment.payment_method else '')
        ws2.cell(row=row, column=5, value=float(payment.amount or 0))
    
    for col in ['A', 'B', 'C', 'D', 'E']:
        ws2.column_dimensions[col].width = 18
    
    # Respuesta
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=reporte_{start_str}_a_{end_str}.xlsx'
    wb.save(response)
    return response


@login_required
def export_report_pdf(request):
    """Exportar reporte a PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from django.http import HttpResponse
    from io import BytesIO
    
    tenant = get_tenant_from_user(request.user)
    start_str = request.GET.get('start_date', timezone.now().date().isoformat())
    end_str = request.GET.get('end_date', timezone.now().date().isoformat())
    
    try:
        start_date = datetime.strptime(f"{start_str} 00:00:00", '%Y-%m-%d %H:%M:%S')
        end_date = datetime.strptime(f"{end_str} 23:59:59", '%Y-%m-%d %H:%M:%S')
    except ValueError:
        start_date = end_date = timezone.now()
    
    # Obtener datos
    tickets = ParkingTicket.objects.all_tenants().filter(
        tenant=tenant,
        exit_time__isnull=False,
        exit_time__range=(start_date, end_date)
    ).exclude(amount_paid__isnull=True).select_related('category', 'payment_method')
    
    total_tickets = sum(t.amount_paid or 0 for t in tickets)
    
    from monthly_contracts.models import ContractPayment
    contract_payments = ContractPayment.objects.filter(
        tenant=tenant,
        payment_date__range=(start_date, end_date),
        is_confirmed=True
    )
    total_contracts = sum(p.amount for p in contract_payments)
    
    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=1, spaceAfter=20)
    elements.append(Paragraph(f"REPORTE DE OPERACIONES", title_style))
    elements.append(Paragraph(f"{tenant.name if tenant else 'SoluPark'}", styles['Heading2']))
    elements.append(Paragraph(f"Período: {start_str} al {end_str}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Resumen
    summary_data = [
        ['Concepto', 'Cantidad', 'Total'],
        ['Tickets Parqueadero', str(tickets.count()), f"${total_tickets:,.0f}"],
        ['Pagos Mensualidades', str(contract_payments.count()), f"${float(total_contracts):,.0f}"],
        ['TOTAL GENERAL', '', f"${float(total_tickets) + float(total_contracts):,.0f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Detalle por método de pago
    elements.append(Paragraph("Ingresos por Método de Pago", styles['Heading3']))
    
    from collections import defaultdict
    payment_summary = defaultdict(float)
    for t in tickets:
        method = t.payment_method.name if t.payment_method else 'Efectivo'
        payment_summary[method] += float(t.amount_paid or 0)
    for p in contract_payments:
        method = p.payment_method.name if p.payment_method else 'Sin especificar'
        payment_summary[method] += float(p.amount or 0)
    
    payment_data = [['Método de Pago', 'Total']]
    for method, total in sorted(payment_summary.items(), key=lambda x: -x[1]):
        payment_data.append([method, f"${total:,.0f}"])
    
    payment_table = Table(payment_data, colWidths=[3*inch, 2*inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0EA5E9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(payment_table)
    
    doc.build(elements)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=reporte_{start_str}_a_{end_str}.pdf'
    response.write(buffer.getvalue())
    return response


def custom_logout(request):
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('login')


@login_required
def category_edit(request, pk):
    tenant = get_tenant_from_user(request.user)
    
    category_query = VehicleCategory.objects.all_tenants().filter(pk=pk)
    if tenant:
        category_query = category_query.filter(tenant=tenant)
    category = get_object_or_404(category_query)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría actualizada correctamente.")
            return redirect('category-list')
        else:
            messages.error(request, "Hubo un error al actualizar la categoría.")
    else:
        form = CategoryForm(instance=category)

    return render(request, 'parking/category_edit.html', {'form': form})


@login_required
def validate_plate(request, plate):
    tenant = get_tenant_from_user(request.user)
    
    query = ParkingTicket.objects.all_tenants().filter(
        placa__iexact=plate,
        exit_time__isnull=True
    )
    if tenant:
        query = query.filter(tenant=tenant)
    
    exists = query.exists()
    return JsonResponse({'exists': exists})


class CategoryDeleteView(DeleteView):
    model = VehicleCategory
    success_url = reverse_lazy('category-list')
    template_name = 'parking/category_confirm_delete.html'

    def get_queryset(self):
        tenant = get_tenant_from_user(self.request.user)
        if tenant:
            return VehicleCategory.objects.all_tenants().filter(tenant=tenant)
        return VehicleCategory.objects.none()

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Categoría eliminada exitosamente')
        return super().delete(request, *args, **kwargs)


@login_required
def cash_register(request):
    tenant = get_tenant_from_user(request.user)
    is_vendedor = request.user.groups.filter(name='Vendedor').exists()
    today = timezone.now().date()

    if is_vendedor:
        start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_date = start_date + timedelta(days=1)
    else:
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        if start_date_str and end_date_str:
            try:
                start_date = timezone.make_aware(datetime.strptime(f"{start_date_str} 00:00:00", '%Y-%m-%d %H:%M:%S'))
                end_date = timezone.make_aware(datetime.strptime(f"{end_date_str} 23:59:59", '%Y-%m-%d %H:%M:%S'))
            except ValueError:
                start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
                end_date = start_date + timedelta(days=1)
        else:
            start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
            end_date = start_date + timedelta(days=1)

    # Tickets de parqueadero
    if tenant:
        tickets = ParkingTicket.objects.all_tenants().filter(
            tenant=tenant,
            exit_time__gte=start_date,
            exit_time__lt=end_date,
            exit_time__isnull=False,
            amount_paid__isnull=False
        ).select_related('payment_method', 'category')
    else:
        tickets = ParkingTicket.objects.none()
    
    # Pagos de mensualidades
    from monthly_contracts.models import ContractPayment
    if tenant:
        contract_payments = ContractPayment.objects.filter(
            tenant=tenant,
            payment_date__gte=start_date,
            payment_date__lt=end_date,
            is_confirmed=True
        ).select_related('payment_method', 'contract', 'contract__vehicle')
    else:
        contract_payments = ContractPayment.objects.none()
    
    # Calcular resumen por método de pago
    from parking.models_config import PaymentMethod
    from collections import defaultdict
    from decimal import Decimal
    
    payment_summary = defaultdict(lambda: {'count': 0, 'total': Decimal('0'), 'is_cash': False})
    
    # Sumar tickets de parqueadero
    for ticket in tickets:
        if ticket.payment_method:
            method_name = ticket.payment_method.name
            payment_summary[method_name]['count'] += 1
            payment_summary[method_name]['total'] += ticket.amount_paid or Decimal('0')
            payment_summary[method_name]['is_cash'] = ticket.payment_method.payment_type == 'cash'
            payment_summary[method_name]['icon'] = ticket.payment_method.icon
        else:
            # Sin método de pago asignado, asumir efectivo
            payment_summary['Efectivo (sin especificar)']['count'] += 1
            payment_summary['Efectivo (sin especificar)']['total'] += ticket.amount_paid or Decimal('0')
            payment_summary['Efectivo (sin especificar)']['is_cash'] = True
            payment_summary['Efectivo (sin especificar)']['icon'] = 'fa-money-bill'
    
    # Sumar pagos de mensualidades
    for payment in contract_payments:
        if payment.payment_method:
            method_name = payment.payment_method.name
            payment_summary[method_name]['count'] += 1
            payment_summary[method_name]['total'] += payment.amount or Decimal('0')
            payment_summary[method_name]['is_cash'] = payment.payment_method.payment_type == 'cash'
            payment_summary[method_name]['icon'] = payment.payment_method.icon
            payment_summary[method_name]['has_contracts'] = True
    
    # Convertir a lista ordenada
    payment_summary_list = [
        {'name': name, **data} 
        for name, data in payment_summary.items()
    ]
    payment_summary_list.sort(key=lambda x: (-x['total'], x['name']))
    
    # Calcular totales
    total_income = sum(ticket.amount_paid or 0 for ticket in tickets)
    total_contracts_cash = sum(
        p.amount for p in contract_payments 
        if p.payment_method and p.payment_method.payment_type == 'cash'
    )
    total_contracts = sum(p.amount for p in contract_payments)
    
    # Solo efectivo para caja física
    cash_from_tickets = sum(
        ticket.amount_paid or 0 for ticket in tickets 
        if ticket.payment_method and ticket.payment_method.payment_type == 'cash'
    ) + sum(
        ticket.amount_paid or 0 for ticket in tickets 
        if not ticket.payment_method  # Sin método = efectivo
    )
    
    total_cash = float(cash_from_tickets) + float(total_contracts_cash)
    total_all = float(total_income) + float(total_contracts)

    caja_date = start_date.date()
    if tenant:
        caja_query = Caja.objects.all_tenants().filter(tenant=tenant, fecha=caja_date, tipo='Ingreso')
    else:
        caja_query = Caja.objects.none()

    if caja_query.exists():
        caja = caja_query.first()
        caja.monto = Decimal(str(total_cash))
        caja.save()
    else:
        caja = Caja(
            fecha=caja_date,
            tipo='Ingreso',
            monto=Decimal(str(total_cash)),
            descripcion=f'Ingresos del {start_date.date()}',
            dinero_inicial=0.00
        )
        if tenant:
            caja.tenant = tenant
        caja.save()

    dinero_esperado = float(caja.dinero_inicial) + total_cash

    if request.method == 'POST' and 'set_dinero_inicial' in request.POST:
        try:
            dinero_inicial = float(request.POST.get('dinero_inicial', 0))
            if dinero_inicial < 0:
                messages.error(request, 'El dinero inicial no puede ser negativo.')
            else:
                caja.dinero_inicial = dinero_inicial
                caja.save()
                messages.success(request, 'Dinero inicial establecido correctamente.')
            return redirect('cash_register')
        except ValueError:
            messages.error(request, 'Por favor, ingrese un valor numérico válido.')

    if request.method == 'POST' and 'realizar_cuadre' in request.POST:
        if caja.cuadre_realizado:
            messages.error(request, 'El cuadre de caja ya fue realizado.')
            return redirect('cash_register')

        try:
            dinero_final = float(request.POST.get('dinero_final', 0))
            if dinero_final < 0:
                messages.error(request, 'El dinero final no puede ser negativo.')
                return redirect('cash_register')

            caja.dinero_final = dinero_final
            caja.monto = Decimal(str(total_cash))
            caja.cuadre_realizado = True
            caja.save()

            messages.success(request, 'Cuadre de caja realizado con éxito.')
            return redirect('cash_register')
        except ValueError:
            messages.error(request, 'Por favor, ingrese un valor numérico válido.')

    diferencia = None
    diferencia_abs = None
    if caja.cuadre_realizado:
        diferencia = float(caja.dinero_final) - float(caja.dinero_inicial) - total_cash
        diferencia_abs = abs(diferencia)

    context = {
        'today': today,
        'start_date': start_date.date(),
        'end_date': (end_date - timedelta(days=1)).date(),
        'tickets': tickets,
        'contract_payments': contract_payments,
        'payment_summary': payment_summary_list,
        'total_income': total_income,
        'total_contracts': total_contracts,
        'total_cash': total_cash,
        'total_all': total_all,
        'caja': caja,
        'dinero_esperado': dinero_esperado,
        'diferencia': diferencia,
        'diferencia_abs': diferencia_abs,
        'is_vendedor': is_vendedor,
        'tenant': tenant,
    }
    return render(request, 'parking/cash_register.html', context)


@login_required
def export_cash_register_excel(request):
    """Exportar cuadre de caja a Excel"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from django.http import HttpResponse
    
    tenant = get_tenant_from_user(request.user)
    date_str = request.GET.get('date', timezone.now().date().isoformat())
    
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        report_date = timezone.now().date()
    
    start_date = timezone.make_aware(datetime.combine(report_date, datetime.min.time()))
    end_date = start_date + timedelta(days=1)
    
    # Obtener datos
    tickets = ParkingTicket.objects.all_tenants().filter(
        tenant=tenant,
        exit_time__gte=start_date,
        exit_time__lt=end_date,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).select_related('payment_method', 'category')
    
    from monthly_contracts.models import ContractPayment
    contract_payments = ContractPayment.objects.filter(
        tenant=tenant,
        payment_date__gte=start_date,
        payment_date__lt=end_date,
        is_confirmed=True
    ).select_related('payment_method', 'contract', 'contract__vehicle')
    
    # Crear workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cuadre de Caja"
    
    # Estilos
    header_font = Font(bold=True, size=14)
    subheader_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="0EA5E9", end_color="0EA5E9", fill_type="solid")
    header_font_white = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Título
    ws.merge_cells('A1:E1')
    ws['A1'] = f"CUADRE DE CAJA - {tenant.name if tenant else 'SoluPark'}"
    ws['A1'].font = header_font
    ws['A1'].alignment = Alignment(horizontal='center')
    
    ws.merge_cells('A2:E2')
    ws['A2'] = f"Fecha: {report_date.strftime('%d/%m/%Y')}"
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Tickets de parqueadero
    row = 4
    ws[f'A{row}'] = "TICKETS DE PARQUEADERO"
    ws[f'A{row}'].font = subheader_font
    
    row += 1
    headers = ['Placa', 'Categoría', 'Entrada', 'Salida', 'Método Pago', 'Monto']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.border = border
    
    for ticket in tickets:
        row += 1
        ws.cell(row=row, column=1, value=ticket.placa).border = border
        ws.cell(row=row, column=2, value=ticket.category.name if ticket.category else '').border = border
        ws.cell(row=row, column=3, value=ticket.entry_time.strftime('%H:%M')).border = border
        ws.cell(row=row, column=4, value=ticket.exit_time.strftime('%H:%M') if ticket.exit_time else '').border = border
        ws.cell(row=row, column=5, value=ticket.payment_method.name if ticket.payment_method else 'Efectivo').border = border
        ws.cell(row=row, column=6, value=float(ticket.amount_paid or 0)).border = border
    
    # Pagos de mensualidades
    row += 2
    ws[f'A{row}'] = "PAGOS DE MENSUALIDADES"
    ws[f'A{row}'].font = subheader_font
    
    row += 1
    headers = ['Vehículo', 'Cliente', 'Método Pago', 'Monto']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.border = border
    
    for payment in contract_payments:
        row += 1
        ws.cell(row=row, column=1, value=payment.contract.vehicle.plate if payment.contract and payment.contract.vehicle else '').border = border
        ws.cell(row=row, column=2, value=str(payment.contract.third_party) if payment.contract and payment.contract.third_party else '').border = border
        ws.cell(row=row, column=3, value=payment.payment_method.name if payment.payment_method else '').border = border
        ws.cell(row=row, column=4, value=float(payment.amount or 0)).border = border
    
    # Ajustar anchos
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 12
    
    # Respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=cuadre_caja_{report_date}.xlsx'
    wb.save(response)
    return response


@login_required
def export_cash_register_pdf(request):
    """Exportar cuadre de caja a PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from django.http import HttpResponse
    from io import BytesIO
    
    tenant = get_tenant_from_user(request.user)
    date_str = request.GET.get('date', timezone.now().date().isoformat())
    
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        report_date = timezone.now().date()
    
    start_date = timezone.make_aware(datetime.combine(report_date, datetime.min.time()))
    end_date = start_date + timedelta(days=1)
    
    # Obtener datos
    tickets = ParkingTicket.objects.all_tenants().filter(
        tenant=tenant,
        exit_time__gte=start_date,
        exit_time__lt=end_date,
        exit_time__isnull=False,
        amount_paid__isnull=False
    ).select_related('payment_method', 'category')
    
    from monthly_contracts.models import ContractPayment
    contract_payments = ContractPayment.objects.filter(
        tenant=tenant,
        payment_date__gte=start_date,
        payment_date__lt=end_date,
        is_confirmed=True
    ).select_related('payment_method', 'contract', 'contract__vehicle')
    
    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,
        spaceAfter=12
    )
    elements.append(Paragraph(f"CUADRE DE CAJA", title_style))
    elements.append(Paragraph(f"{tenant.name if tenant else 'SoluPark'}", styles['Heading2']))
    elements.append(Paragraph(f"Fecha: {report_date.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Tabla de tickets
    elements.append(Paragraph("Tickets de Parqueadero", styles['Heading3']))
    
    ticket_data = [['Placa', 'Categoría', 'Entrada', 'Salida', 'Método', 'Monto']]
    total_tickets = 0
    for ticket in tickets:
        ticket_data.append([
            ticket.placa,
            ticket.category.name if ticket.category else '',
            ticket.entry_time.strftime('%H:%M'),
            ticket.exit_time.strftime('%H:%M') if ticket.exit_time else '',
            ticket.payment_method.name if ticket.payment_method else 'Efectivo',
            f"${float(ticket.amount_paid or 0):,.0f}"
        ])
        total_tickets += float(ticket.amount_paid or 0)
    
    ticket_data.append(['', '', '', '', 'TOTAL:', f"${total_tickets:,.0f}"])
    
    ticket_table = Table(ticket_data, colWidths=[1*inch, 1.2*inch, 0.8*inch, 0.8*inch, 1*inch, 1*inch])
    ticket_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0EA5E9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(ticket_table)
    elements.append(Spacer(1, 20))
    
    # Tabla de mensualidades
    elements.append(Paragraph("Pagos de Mensualidades", styles['Heading3']))
    
    contract_data = [['Vehículo', 'Cliente', 'Método', 'Monto']]
    total_contracts = 0
    for payment in contract_payments:
        contract_data.append([
            payment.contract.vehicle.plate if payment.contract and payment.contract.vehicle else '',
            str(payment.contract.third_party)[:20] if payment.contract and payment.contract.third_party else '',
            payment.payment_method.name if payment.payment_method else '',
            f"${float(payment.amount or 0):,.0f}"
        ])
        total_contracts += float(payment.amount or 0)
    
    contract_data.append(['', '', 'TOTAL:', f"${total_contracts:,.0f}"])
    
    contract_table = Table(contract_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 1*inch])
    contract_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10B981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(contract_table)
    elements.append(Spacer(1, 20))
    
    # Total general
    elements.append(Paragraph(f"TOTAL GENERAL: ${total_tickets + total_contracts:,.0f}", styles['Heading2']))
    
    doc.build(elements)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=cuadre_caja_{report_date}.pdf'
    response.write(buffer.getvalue())
    return response
