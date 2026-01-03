"""
URLs del panel de SuperAdmin.
"""
from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('logout/', views.superadmin_logout, name='logout'),
    
    # Gestión de Parqueaderos (Tenants)
    path('parqueaderos/', views.tenant_list, name='tenant_list'),
    path('parqueaderos/crear/', views.tenant_create, name='tenant_create'),
    path('parqueaderos/<uuid:pk>/', views.tenant_detail, name='tenant_detail'),
    path('parqueaderos/<uuid:pk>/editar/', views.tenant_edit, name='tenant_edit'),
    path('parqueaderos/<uuid:pk>/toggle/', views.tenant_toggle_status, name='tenant_toggle'),
    path('parqueaderos/<uuid:pk>/eliminar/', views.tenant_delete, name='tenant_delete'),
    path('parqueaderos/<uuid:pk>/cambiar-password/', views.tenant_change_password, name='tenant_change_password'),
    path('parqueaderos/<uuid:pk>/suscripcion/', views.tenant_subscription, name='tenant_subscription'),
    
    # Suscripciones
    path('planes/', views.subscription_plans, name='subscription_plans'),
    path('pagos/', views.subscription_payments, name='subscription_payments'),
]
