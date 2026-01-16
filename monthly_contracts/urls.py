from django.urls import path
from . import views

urlpatterns = [
    path('', views.contract_list, name='contract_list'),
    path('crear/', views.contract_create, name='contract_create'),
    path('pendientes/', views.pending_payments, name='pending_payments'),
    path('historial-pagos/', views.payment_history, name='payment_history'),
    path('<uuid:pk>/', views.contract_detail, name='contract_detail'),
    path('<uuid:pk>/editar/', views.contract_edit, name='contract_edit'),
    path('<uuid:pk>/eliminar/', views.contract_delete, name='contract_delete'),
    path('<uuid:pk>/pago/', views.contract_payment, name='contract_payment'),
    path('<uuid:pk>/renovar/', views.contract_renew, name='contract_renew'),
    path('<uuid:pk>/agregar-vehiculo/', views.add_contract_vehicle, name='add_contract_vehicle'),
    path('<uuid:pk>/vehiculo/<uuid:vehicle_pk>/eliminar/', views.remove_contract_vehicle, name='remove_contract_vehicle'),
    path('recibo/<uuid:payment_id>/', views.print_payment_receipt, name='print_payment_receipt'),
    path('pago/<uuid:payment_id>/editar/', views.payment_edit, name='payment_edit'),
    path('pago/<uuid:payment_id>/eliminar/', views.payment_delete, name='payment_delete'),
    path('api/vehiculos-cliente/', views.get_client_vehicles, name='get_client_vehicles'),
]
