"""
Vistas de autenticación para usuarios.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone


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


@login_required
def force_change_password(request):
    """Vista para forzar cambio de contraseña"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        # Validaciones
        if not request.user.check_password(current_password):
            messages.error(request, 'La contraseña actual es incorrecta')
            return render(request, 'users/force_change_password.html')
        
        if len(new_password) < 8:
            messages.error(request, 'La nueva contraseña debe tener al menos 8 caracteres')
            return render(request, 'users/force_change_password.html')
        
        if new_password != confirm_password:
            messages.error(request, 'Las contraseñas no coinciden')
            return render(request, 'users/force_change_password.html')
        
        if current_password == new_password:
            messages.error(request, 'La nueva contraseña debe ser diferente a la actual')
            return render(request, 'users/force_change_password.html')
        
        # Cambiar contraseña
        request.user.set_password(new_password)
        request.user.must_change_password = False
        request.user.password_changed_at = timezone.now()
        request.user.save()
        
        # Mantener sesión activa
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Contraseña cambiada exitosamente')
        return redirect_after_login(request.user)
    
    return render(request, 'users/force_change_password.html')
