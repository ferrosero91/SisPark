from django import forms
from .models import ThirdParty, ThirdPartyVehicle

INPUT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
SELECT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500'


class ThirdPartyForm(forms.ModelForm):
    class Meta:
        model = ThirdParty
        fields = ['document_type', 'document_number', 'first_name', 'last_name', 
                  'email', 'phone', 'address', 'notes', 'is_active']
        widgets = {
            'document_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'document_number': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Número de documento'}),
            'first_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Nombres'}),
            'last_name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Apellidos'}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS, 'placeholder': 'correo@ejemplo.com'}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': '300 123 4567'}),
            'address': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Dirección'}),
            'notes': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3, 'placeholder': 'Notas adicionales...'}),
        }


class ThirdPartyVehicleForm(forms.ModelForm):
    class Meta:
        model = ThirdPartyVehicle
        fields = ['plate', 'brand', 'model', 'color', 'vehicle_type', 'is_primary']
        widgets = {
            'plate': forms.TextInput(attrs={'class': INPUT_CLASS + ' uppercase font-mono', 'placeholder': 'ABC123'}),
            'brand': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Chevrolet'}),
            'model': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Spark'}),
            'color': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Rojo'}),
            'vehicle_type': forms.Select(attrs={'class': SELECT_CLASS}),
        }
