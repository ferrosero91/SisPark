from django import forms
from .models import ParkingTicket, VehicleCategory
from tenants.models import Tenant

INPUT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
SELECT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500'


class ParkingTicketForm(forms.ModelForm):
    class Meta:
        model = ParkingTicket
        fields = ['category', 'placa', 'color', 'marca', 'cascos']
        labels = {
            'category': 'Categoría',
            'placa': 'Placa',
            'color': 'Color',
            'marca': 'Marca',
            'cascos': 'Número de cascos',
        }
        widgets = {
            'category': forms.Select(attrs={'class': SELECT_CLASS}),
            'placa': forms.TextInput(attrs={'class': INPUT_CLASS + ' uppercase font-mono text-lg tracking-wider', 'placeholder': 'ABC123'}),
            'color': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Rojo'}),
            'marca': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Chevrolet'}),
            'cascos': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': '0', 'max': '2'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['color'].required = False
        self.fields['marca'].required = False
        self.fields['cascos'].required = False
        
        if tenant:
            # Usar all_tenants() para evitar el filtro automático del TenantManager
            self.fields['category'].queryset = VehicleCategory.objects.all_tenants().filter(tenant=tenant)
        else:
            self.fields['category'].queryset = VehicleCategory.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        cascos = cleaned_data.get('cascos')

        if category and category.name.upper() in ['MOTOS', 'MOTO']:
            if cascos is None:
                self.add_error('cascos', 'El número de cascos es obligatorio para motos')
        
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = VehicleCategory
        fields = ['name', 'first_hour_rate', 'additional_hour_rate', 'is_monthly', 'monthly_rate']
        labels = {
            'name': 'Nombre',
            'first_hour_rate': 'Tarifa primera hora',
            'additional_hour_rate': 'Tarifa hora adicional',
            'is_monthly': '¿Es mensual?',
            'monthly_rate': 'Tarifa mensual',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'first_hour_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '100'}),
            'additional_hour_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '100'}),
            'monthly_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '1000'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        is_monthly = cleaned_data.get('is_monthly')
        monthly_rate = cleaned_data.get('monthly_rate')

        if is_monthly and (monthly_rate is None or monthly_rate <= 0):
            self.add_error('monthly_rate', 'Debe especificar una tarifa mensual válida.')
        
        return cleaned_data