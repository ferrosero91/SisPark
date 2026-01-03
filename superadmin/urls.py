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
    
    # Backup y Restauración
    path('backup/', views.backup_dashboard, name='backup_dashboard'),
    path('backup/sistema/crear/', views.backup_create_system, name='backup_create_system'),
    path('backup/sistema/descargar/<str:filename>/', views.backup_download_system, name='backup_download_system'),
    path('backup/sistema/eliminar/<str:filename>/', views.backup_delete_system, name='backup_delete_system'),
    path('backup/sistema/info/<str:filename>/', views.backup_info_system, name='backup_info_system'),
    path('backup/tenant/<uuid:pk>/crear/', views.backup_create_tenant, name='backup_create_tenant'),
    path('backup/tenant/<uuid:pk>/descargar/<str:filename>/', views.backup_download_tenant, name='backup_download_tenant'),
    path('backup/tenant/<uuid:pk>/eliminar/<str:filename>/', views.backup_delete_tenant, name='backup_delete_tenant'),
    path('backup/tenant/<uuid:pk>/restaurar/', views.backup_restore_tenant, name='backup_restore_tenant'),
    
    # Backup SQL
    path('backup/sql/crear/', views.backup_create_sql, name='backup_create_sql'),
    path('backup/sql/descargar/<str:filename>/', views.backup_download_sql, name='backup_download_sql'),
    path('backup/sql/eliminar/<str:filename>/', views.backup_delete_sql, name='backup_delete_sql'),
    path('backup/sql/restaurar/', views.backup_restore_sql, name='backup_restore_sql'),
]
