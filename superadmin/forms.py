"""
Formularios del panel SuperAdmin.
"""
from django import forms
from tenants.models import Tenant
from users.models import User

INPUT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-violet-500 focus:border-violet-500'
SELECT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-violet-500 focus:border-violet-500'


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
