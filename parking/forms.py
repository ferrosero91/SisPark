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
        fields = [
            'name', 
            'rate_by_minute', 'minute_rate', 'minimum_minutes',
            'first_hour_rate', 'additional_hour_rate', 
            'extended_hours', 'extended_rate', 
            'is_monthly', 'monthly_rate'
        ]
        labels = {
            'name': 'Nombre',
            'rate_by_minute': '¿Cobrar por minuto?',
            'minute_rate': 'Tarifa por minuto',
            'minimum_minutes': 'Minutos mínimos (opcional)',
            'first_hour_rate': 'Tarifa primera hora',
            'additional_hour_rate': 'Tarifa hora adicional',
            'extended_hours': 'Horas del bloque (opcional)',
            'extended_rate': 'Tarifa del bloque (opcional)',
            'is_monthly': '¿Es mensual?',
            'monthly_rate': 'Tarifa mensual',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'minute_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '10'}),
            'minimum_minutes': forms.NumberInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: 15'}),
            'first_hour_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '100'}),
            'additional_hour_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '100'}),
            'extended_hours': forms.NumberInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: 12 o 24'}),
            'extended_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '100', 'placeholder': 'Tarifa por el bloque'}),
            'monthly_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '1000'}),
        }
        help_texts = {
            'rate_by_minute': 'Si activa esta opción, se cobrará por minuto en lugar de por hora.',
            'minute_rate': 'Tarifa que se cobra por cada minuto de estacionamiento.',
            'minimum_minutes': 'Tiempo mínimo a cobrar. Ej: si configura 15, siempre se cobrarán mínimo 15 minutos.',
            'extended_hours': 'Si configura este campo, se cobrará la tarifa del bloque por las primeras X horas, y luego hora adicional.',
            'extended_rate': 'Tarifa fija por el bloque de horas. Después se cobra la tarifa de hora adicional.',
        }

    def clean(self):
        cleaned_data = super().clean()
        is_monthly = cleaned_data.get('is_monthly')
        monthly_rate = cleaned_data.get('monthly_rate')
        extended_hours = cleaned_data.get('extended_hours')
        extended_rate = cleaned_data.get('extended_rate')
        rate_by_minute = cleaned_data.get('rate_by_minute')
        minute_rate = cleaned_data.get('minute_rate')
        first_hour_rate = cleaned_data.get('first_hour_rate')
        additional_hour_rate = cleaned_data.get('additional_hour_rate')

        if is_monthly and (monthly_rate is None or monthly_rate <= 0):
            self.add_error('monthly_rate', 'Debe especificar una tarifa mensual válida.')
        
        # Validar tarifa por minuto
        if rate_by_minute:
            if minute_rate is None or minute_rate <= 0:
                self.add_error('minute_rate', 'Debe especificar una tarifa por minuto válida.')
            # Si es por minuto, asegurar que los campos de hora tengan valores por defecto
            if not first_hour_rate or first_hour_rate <= 0:
                cleaned_data['first_hour_rate'] = 0
            if not additional_hour_rate or additional_hour_rate <= 0:
                cleaned_data['additional_hour_rate'] = 0
        else:
            # Si no es por minuto, validar tarifas por hora
            if first_hour_rate is None or first_hour_rate <= 0:
                self.add_error('first_hour_rate', 'Debe especificar una tarifa de primera hora válida.')
            if additional_hour_rate is None or additional_hour_rate <= 0:
                self.add_error('additional_hour_rate', 'Debe especificar una tarifa de hora adicional válida.')
        
        # Validar que si se configura extended_hours, también se configure extended_rate
        if not rate_by_minute:  # Solo validar si no es por minuto
            if extended_hours and not extended_rate:
                self.add_error('extended_rate', 'Debe especificar la tarifa del bloque.')
            if extended_rate and not extended_hours:
                self.add_error('extended_hours', 'Debe especificar las horas del bloque.')
        
        return cleaned_data