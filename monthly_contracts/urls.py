from django.urls import path
from . import views

urlpatterns = [
    path('', views.contract_list, name='contract_list'),
    path('crear/', views.contract_create, name='contract_create'),
    path('pendientes/', views.pending_payments, name='pending_payments'),
    path('historial-pagos/', views.payment_history, name='payment_history'),
    path('<uuid:pk>/', views.contract_detail, name='contract_detail'),
    path('<uuid:pk>/pago/', views.contract_payment, name='contract_payment'),
    path('<uuid:pk>/renovar/', views.contract_renew, name='contract_renew'),
    path('recibo/<uuid:payment_id>/', views.print_payment_receipt, name='print_payment_receipt'),
    path('api/vehiculos/', views.get_vehicle_info, name='get_vehicle_info'),
]
