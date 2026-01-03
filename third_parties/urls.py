from django.urls import path
from . import views

urlpatterns = [
    path('', views.third_party_list, name='third_party_list'),
    path('crear/', views.third_party_create, name='third_party_create'),
    path('<uuid:pk>/', views.third_party_detail, name='third_party_detail'),
    path('<uuid:pk>/editar/', views.third_party_edit, name='third_party_edit'),
    path('<uuid:pk>/eliminar/', views.third_party_delete, name='third_party_delete'),
    path('<uuid:pk>/vehiculo/agregar/', views.vehicle_add, name='vehicle_add'),
    path('<uuid:pk>/vehiculo/<uuid:vehicle_pk>/editar/', views.vehicle_edit, name='vehicle_edit'),
    path('<uuid:pk>/vehiculo/<uuid:vehicle_pk>/eliminar/', views.vehicle_delete, name='vehicle_delete'),
]
