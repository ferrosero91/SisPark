"""
Formularios para la configuración del parqueadero.
"""
import re
from django import forms
from django.core.validators import EmailValidator


class ParkingInfoForm(forms.Form):
    """
    Formulario para editar la información del parqueadero (tenant).
    Valida email, teléfono y longitudes máximas.
    """
    name = forms.CharField(
        max_length=255,
        required=True,
        label="Nombre del Parqueadero"
    )
    business_name = forms.CharField(
        max_length=255,
        required=True,
        label="Razón Social"
    )
    nit = forms.CharField(
        max_length=20,
        required=True,
        label="NIT"
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        label="Teléfono"
    )
    email = forms.EmailField(
        required=True,
        label="Email de contacto",
        validators=[EmailValidator(message="Ingrese un email válido.")]
    )
    address = forms.CharField(
        max_length=200,
        required=True,
        label="Dirección"
    )
    city = forms.CharField(
        max_length=100,
        required=False,
        label="Ciudad"
    )

    def clean_phone(self):
        """Validate phone contains only digits, +, -, and spaces."""
        phone = self.cleaned_data.get('phone', '')
        if not re.match(r'^[\d\s+\-]+$', phone):
            raise forms.ValidationError(
                "El teléfono solo puede contener dígitos, +, - y espacios."
            )
        return phone
