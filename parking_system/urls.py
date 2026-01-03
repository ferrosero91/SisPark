from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from parking import views
from parking.views import (
    CategoryListView, CategoryCreateView,
    VehicleEntryView, vehicle_exit, vehicle_payment, print_ticket, print_exit_ticket, ReportView,
    category_edit, cash_register, export_cash_register_excel, export_cash_register_pdf,
    export_report_excel, export_report_pdf
)


def health_check(request):
    """Endpoint para verificar el estado de la aplicación"""
    return JsonResponse({'status': 'ok', 'app': 'solupark'})


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    
    # Autenticación (nuevo sistema)
    path('', include('users.urls')),
    
    # Panel SuperAdmin
    path('superadmin/', include('superadmin.urls')),
    
    # Módulos de gestión
    path('clientes/', include('third_parties.urls')),
    path('mensualidades/', include('monthly_contracts.urls')),
    path('configuracion/', include('config.urls')),
    
    # Sistema de parking
    path('inicio/', views.pagina_inicial, name='pagina_inicial'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('entry/', VehicleEntryView.as_view(), name='vehicle-entry'),
    path('exit/', vehicle_exit, name='vehicle-exit'),
    path('payment/', vehicle_payment, name='vehicle-payment'),
    path('print-ticket/', print_ticket, name='print-ticket'),
    path('print-exit-ticket/', print_exit_ticket, name='print-exit-ticket'),
    path('reprint-ticket/<int:ticket_id>/', print_ticket, name='reprint-ticket'),
    path('categorias/', CategoryListView.as_view(), name='category-list'),
    path('categorias/new/', CategoryCreateView.as_view(), name='category-create'),
    path('categorias/<int:pk>/editar/', category_edit, name='category-edit'),
    path('categorias/<int:pk>/eliminar/', views.CategoryDeleteView.as_view(), name='category-delete'),
    path('reports/', ReportView.as_view(), name='reports'),
    path('reports/export/excel/', export_report_excel, name='report_excel'),
    path('reports/export/pdf/', export_report_pdf, name='report_pdf'),
    path('cash-register/', cash_register, name='cash_register'),
    path('cash-register/export/excel/', export_cash_register_excel, name='cash_register_excel'),
    path('cash-register/export/pdf/', export_cash_register_pdf, name='cash_register_pdf'),
    path('validate-plate/<str:plate>/', views.validate_plate, name='validate-plate'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)