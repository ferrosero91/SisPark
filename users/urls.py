"""
URLs de autenticación.
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'users'

urlpatterns = [
    path('', RedirectView.as_view(url='/login/', permanent=False), name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cambiar-password/', views.force_change_password, name='force_change_password'),
]
