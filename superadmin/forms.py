"""
Formularios del panel SuperAdmin.
"""
from django import forms
from django.utils import timezone
from tenants.models import Tenant
from users.models import User
from .models import SystemAnnouncement

INPUT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
SELECT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
TEXTAREA_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
CHECKBOX_CLASS = 'w-5 h-5 text-primary-600 border-slate-300 rounded focus:ring-primary-500'


class TenantForm(forms.ModelForm):
    """Formulario para crear/editar parqueaderos"""
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'business_name', 'nit',
            'phone', 'address', 'email', 'city', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nombre del parqueadero'}),
            'business_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Razón social'}),
            'nit': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'NIT'}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Teléfono'}),
            'address': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Dirección'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Email'}),
            'city': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ciudad'}),
            'status': forms.Select(attrs={'class': SELECT_CLASS}),
        }


class TenantCreateForm(TenantForm):
    """Formulario para crear parqueadero con admin"""
    
    admin_email = forms.EmailField(
        label="Email del administrador",
        widget=forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'admin@ejemplo.com'})
    )
    admin_password = forms.CharField(
        label="Contraseña del administrador",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Contraseña'})
    )
    admin_first_name = forms.CharField(
        label="Nombre del administrador",
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nombre'})
    )
    admin_last_name = forms.CharField(
        label="Apellido del administrador",
        widget=forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Apellido'})
    )


class AdminPasswordChangeForm(forms.Form):
    """Formulario para cambiar contraseña de admin de tenant"""
    
    new_password = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS})
    )
    confirm_password = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={'class': INPUT_CLASS})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('new_password')
        confirm = cleaned_data.get('confirm_password')
        
        if password and confirm and password != confirm:
            raise forms.ValidationError("Las contraseñas no coinciden")
        
        return cleaned_data


class SystemAnnouncementForm(forms.ModelForm):
    """Formulario para crear/editar anuncios del sistema."""
    
    class Meta:
        model = SystemAnnouncement
        fields = [
            'title', 'message', 'announcement_type',
            'starts_at', 'ends_at',
            'is_global', 'target_tenants',
            'is_active', 'is_dismissible',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Ej: Mantenimiento programado'
            }),
            'message': forms.Textarea(attrs={
                'class': TEXTAREA_CLASS,
                'rows': 3,
                'placeholder': 'Ej: El sistema estará en mantenimiento el sábado de 2am a 4am'
            }),
            'announcement_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'starts_at': forms.DateTimeInput(attrs={
                'class': INPUT_CLASS,
                'type': 'datetime-local'
            }),
            'ends_at': forms.DateTimeInput(attrs={
                'class': INPUT_CLASS,
                'type': 'datetime-local'
            }),
            'is_global': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'target_tenants': forms.SelectMultiple(attrs={
                'class': SELECT_CLASS,
                'size': 5
            }),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'is_dismissible': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get('starts_at')
        ends_at = cleaned_data.get('ends_at')
        
        if starts_at and ends_at:
            if ends_at <= starts_at:
                raise forms.ValidationError("La fecha de fin debe ser posterior a la de inicio.")
        
        return cleaned_data
