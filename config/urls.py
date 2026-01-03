from django.urls import path
from . import views

urlpatterns = [
    # Dashboard de configuración
    path('', views.config_dashboard, name='config_dashboard'),
    
    # Información del parqueadero
    path('parqueadero/', views.parking_info, name='config_parking_info'),
    
    # Métodos de pago
    path('metodos-pago/', views.payment_method_list, name='payment_method_list'),
    path('metodos-pago/crear/', views.payment_method_create, name='payment_method_create'),
    path('metodos-pago/<uuid:pk>/editar/', views.payment_method_edit, name='payment_method_edit'),
    path('metodos-pago/<uuid:pk>/eliminar/', views.payment_method_delete, name='payment_method_delete'),
    
    # Categorías (redirige a las existentes)
    path('categorias/', views.category_list_config, name='config_categories'),
    
    # Usuarios
    path('usuarios/', views.user_list, name='config_users'),
    path('usuarios/crear/', views.user_create, name='config_user_create'),
    path('usuarios/<uuid:pk>/editar/', views.user_edit, name='config_user_edit'),
    path('usuarios/<uuid:pk>/eliminar/', views.user_delete, name='config_user_delete'),
]
