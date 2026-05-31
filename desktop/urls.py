"""
URLs para el módulo desktop (sincronización y estado).
"""
from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.sync_status, name='sync_status'),
    path('force/', views.force_sync, name='force_sync'),
    path('queue/', views.sync_queue_info, name='sync_queue_info'),
]
