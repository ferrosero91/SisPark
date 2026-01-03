from django import forms
from django.forms import inlineformset_factory
from .models import MonthlyContract, ContractVehicle, ContractPayment
from third_parties.models import ThirdParty, ThirdPartyVehicle
from parking.models import VehicleCategory
from parking.models_config import PaymentMethod

INPUT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
SELECT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500'


class MonthlyContractForm(forms.ModelForm):
    """Formulario para crear/editar contratos"""
    
    class Meta:
        model = MonthlyContract
        fields = ['third_party', 'start_date', 'end_date', 'use_combo_rate', 'combo_name', 'combo_rate', 'auto_renew', 'notes']
        widgets = {
            'third_party': forms.Select(attrs={'class': SELECT_CLASS, 'id': 'id_third_party'}),
            'start_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'use_combo_rate': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500',
                'id': 'id_use_combo_rate',
                'onchange': 'toggleComboFields()'
            }),
            'combo_name': forms.TextInput(attrs={
                'class': INPUT_CLASS, 
                'placeholder': 'Ej: Combo Familiar, Plan Empresarial',
                'id': 'id_combo_name'
            }),
            'combo_rate': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 
                'step': '1000', 
                'placeholder': '200000',
                'id': 'id_combo_rate'
            }),
            'auto_renew': forms.CheckboxInput(attrs={'class': 'w-5 h-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500'}),
            'notes': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3, 'placeholder': 'Notas adicionales...'}),
        }
    
    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        
        if tenant:
            self.fields['third_party'].queryset = ThirdParty.objects.all_tenants().filter(
                tenant=tenant, is_active=True
            )
        else:
            self.fields['third_party'].queryset = ThirdParty.objects.none()
        
        # Campos de combo son opcionales
        self.fields['combo_name'].required = False
        self.fields['combo_rate'].required = False


class ContractVehicleForm(forms.ModelForm):
    """Formulario para agregar vehículos al contrato"""
    
    class Meta:
        model = ContractVehicle
        fields = ['vehicle', 'category', 'monthly_rate', 'notes']
        widgets = {
            'vehicle': forms.Select(attrs={'class': SELECT_CLASS}),
            'category': forms.Select(attrs={'class': SELECT_CLASS}),
            'monthly_rate': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 
                'step': '1000', 
                'placeholder': '150000',
                'min': '0'
            }),
            'notes': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 2, 'placeholder': 'Notas...'}),
        }
    
    def __init__(self, *args, tenant=None, third_party=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        
        if third_party:
            self.fields['vehicle'].queryset = ThirdPartyVehicle.objects.filter(
                third_party=third_party, is_active=True
            )
        elif tenant:
            self.fields['vehicle'].queryset = ThirdPartyVehicle.objects.filter(
                third_party__tenant=tenant, is_active=True
            )
        else:
            self.fields['vehicle'].queryset = ThirdPartyVehicle.objects.none()
        
        if tenant:
            self.fields['category'].queryset = VehicleCategory.objects.all_tenants().filter(tenant=tenant)
        else:
            self.fields['category'].queryset = VehicleCategory.objects.none()


# Formset para múltiples vehículos
ContractVehicleFormSet = inlineformset_factory(
    MonthlyContract,
    ContractVehicle,
    form=ContractVehicleForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class ContractPaymentForm(forms.ModelForm):
    """Formulario para registrar pagos"""
    
    class Meta:
        model = ContractPayment
        fields = ['amount', 'payment_method', 'payment_month', 'payment_year', 'amount_received', 'reference', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 
                'step': '1000',
                'id': 'id_amount'
            }),
            'payment_method': forms.Select(attrs={
                'class': SELECT_CLASS,
                'id': 'id_payment_method'
            }),
            'payment_month': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'min': '1',
                'max': '12',
                'id': 'id_payment_month'
            }),
            'payment_year': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'min': '2020',
                'max': '2030',
                'id': 'id_payment_year'
            }),
            'amount_received': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'step': '1000',
                'id': 'id_amount_received',
                'placeholder': 'Solo para efectivo'
            }),
            'reference': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Número de transacción, referencia, etc.'
            }),
            'notes': forms.Textarea(attrs={
                'class': INPUT_CLASS,
                'rows': 2,
                'placeholder': 'Notas adicionales...'
            }),
        }
    
    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        
        if tenant:
            self.fields['payment_method'].queryset = PaymentMethod.objects.all_tenants().filter(
                tenant=tenant,
                is_active=True,
                allow_for_contracts=True
            ).order_by('order', 'name')
        else:
            self.fields['payment_method'].queryset = PaymentMethod.objects.none()
        
        self.fields['amount_received'].required = False
        self.fields['reference'].required = False
        self.fields['notes'].required = False
