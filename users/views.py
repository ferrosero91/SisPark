"""
Vistas de autenticación para usuarios.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.http import require_http_methods


def login_view(request):
    """Vista de login unificada"""
    if request.user.is_authenticated:
        return redirect_after_login(request.user)
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        if not email or not password:
            messages.error(request, 'Por favor ingrese email y contraseña')
            return render(request, 'users/login.html')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenido, {user.get_full_name() or user.email}')
            
            # Redirigir según tipo de usuario
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            
            return redirect_after_login(user)
        else:
            messages.error(request, 'Email o contraseña incorrectos')
    
    return render(request, 'users/login.html')


def redirect_after_login(user):
    """Redirige al usuario según su rol"""
    if user.is_superadmin:
        return redirect('superadmin:dashboard')
    elif user.tenant:
        return redirect('dashboard')
    else:
        return redirect('dashboard')


def logout_view(request):
    """Vista de logout"""
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('login')
