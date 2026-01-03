from django import forms
from .models import MonthlyContract, ContractPayment
from third_parties.models import ThirdParty, ThirdPartyVehicle
from parking.models import VehicleCategory
from parking.models_config import PaymentMethod

INPUT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
SELECT_CLASS = 'w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500'


class MonthlyContractForm(forms.ModelForm):
    register_payment = forms.BooleanField(
        required=False, 
        initial=True,
        label='Registrar pago después de crear',
        widget=forms.CheckboxInput(attrs={'class': 'w-5 h-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500'})
    )
    
    class Meta:
        model = MonthlyContract
        fields = ['third_party', 'vehicle', 'category', 'contract_type', 'monthly_rate', 
                  'start_date', 'end_date', 'auto_renew', 'notes']
        widgets = {
            'third_party': forms.Select(attrs={'class': SELECT_CLASS, 'id': 'id_third_party'}),
            'vehicle': forms.Select(attrs={'class': SELECT_CLASS, 'id': 'id_vehicle'}),
            'category': forms.Select(attrs={'class': SELECT_CLASS}),
            'contract_type': forms.Select(attrs={'class': SELECT_CLASS, 'id': 'id_contract_type'}),
            'monthly_rate': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '1000', 'placeholder': '150000'}),
            'start_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'auto_renew': forms.CheckboxInput(attrs={'class': 'w-5 h-5 rounded border-slate-300 text-primary-600 focus:ring-primary-500'}),
            'notes': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3, 'placeholder': 'Notas adicionales...'}),
        }
    
    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        
        if tenant:
            self.fields['third_party'].queryset = ThirdParty.objects.all_tenants().filter(tenant=tenant, is_active=True)
            self.fields['vehicle'].queryset = ThirdPartyVehicle.objects.filter(
                third_party__tenant=tenant, is_active=True
            )
            self.fields['category'].queryset = VehicleCategory.objects.all_tenants().filter(tenant=tenant)
        else:
            self.fields['third_party'].queryset = ThirdParty.objects.none()
            self.fields['vehicle'].queryset = ThirdPartyVehicle.objects.none()
            self.fields['category'].queryset = VehicleCategory.objects.none()


class ContractPaymentForm(forms.ModelForm):
    class Meta:
        model = ContractPayment
        fields = ['amount', 'payment_method', 'months_paid', 'amount_received', 'reference', 'notes']
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
            'months_paid': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'min': '1',
                'max': '12',
                'id': 'id_months_paid'
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
