"""
Servicio profesional para detección automática de contratos y tarifas especiales.
Maneja diferentes tipos de contratos, auto-renovación y notificaciones.
"""
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class ContractType(Enum):
    """Tipos de contrato disponibles"""
    MONTHLY = 'monthly'      # Mensual
    BIWEEKLY = 'biweekly'    # Quincenal
    WEEKLY = 'weekly'        # Semanal
    DAILY = 'daily'          # Diario (tarifa plana por día)
    HOURLY_PACK = 'hourly'   # Paquete de horas


class RateType(Enum):
    """Tipos de tarifa"""
    REGULAR = 'regular'           # Tarifa normal por hora
    CONTRACT = 'contract'         # Contrato (mensual, semanal, etc.)
    SPECIAL = 'special'           # Tarifa especial (convenio, descuento)
    COURTESY = 'courtesy'         # Cortesía (sin cobro)


@dataclass
class RateResult:
    """Resultado de la detección de tarifa"""
    rate_type: RateType
    contract_type: Optional[ContractType]
    amount: Decimal
    contract: Optional[Any]  # MonthlyContract
    third_party: Optional[Any]  # ThirdParty
    vehicle: Optional[Any]  # ThirdPartyVehicle
    message: str
    is_valid: bool
    days_remaining: int = 0
    auto_renew: bool = False
    discount_percent: Decimal = Decimal('0')


class ContractDetectionService:
    """
    Servicio para detectar automáticamente contratos y tarifas especiales.
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
        self._cache = {}
    
    def detect_rate(self, plate: str, category=None) -> RateResult:
        """
        Detecta la tarifa aplicable para un vehículo.
        
        Args:
            plate: Placa del vehículo
            category: Categoría del vehículo (opcional)
        
        Returns:
            RateResult con la información de la tarifa detectada
        """
        plate = plate.upper().strip().replace(' ', '').replace('-', '')
        
        # 1. Buscar vehículo registrado
        vehicle, third_party = self._find_vehicle(plate)
        
        if vehicle and third_party:
            # 2. Buscar contrato activo
            contract = self._find_active_contract(vehicle)
            
            if contract:
                return self._build_contract_result(contract, vehicle, third_party)
            
            # 3. Buscar tarifa especial del tercero
            special_rate = self._find_special_rate(third_party, category)
            if special_rate:
                return special_rate
        
        # 4. Tarifa regular
        return self._build_regular_result(category)
    
    def _find_vehicle(self, plate: str) -> Tuple[Optional[Any], Optional[Any]]:
        """Busca un vehículo registrado por placa"""
        from third_parties.models import ThirdPartyVehicle
        
        vehicle = ThirdPartyVehicle.objects.filter(
            third_party__tenant=self.tenant,
            plate__iexact=plate,
            is_active=True
        ).select_related('third_party').first()
        
        if vehicle:
            return vehicle, vehicle.third_party
        return None, None
    
    def _find_active_contract(self, vehicle) -> Optional[Any]:
        """Busca un contrato activo para el vehículo"""
        from monthly_contracts.models import MonthlyContract, ContractVehicle
        
        today = timezone.now().date()
        
        # Buscar si el vehículo está en algún contrato activo
        contract_vehicle = ContractVehicle.objects.filter(
            vehicle=vehicle,
            is_active=True,
            contract__tenant=self.tenant,
            contract__is_active=True,
            contract__status__in=['active', 'pending'],
            contract__start_date__lte=today,
            contract__end_date__gte=today
        ).select_related('contract', 'category').first()
        
        if contract_vehicle:
            return contract_vehicle.contract
        return None
    
    def _find_special_rate(self, third_party, category) -> Optional[RateResult]:
        """Busca tarifas especiales para el tercero"""
        # Verificar si el tercero tiene descuento especial
        # Esto se puede extender con un modelo SpecialRate
        
        # Por ahora, verificar si tiene notas con descuento
        if third_party.notes and 'descuento' in third_party.notes.lower():
            # Extraer porcentaje de descuento si existe
            import re
            match = re.search(r'(\d+)%', third_party.notes)
            if match:
                discount = Decimal(match.group(1))
                return RateResult(
                    rate_type=RateType.SPECIAL,
                    contract_type=None,
                    amount=Decimal('0'),  # Se calcula al salir
                    contract=None,
                    third_party=third_party,
                    vehicle=None,
                    message=f"Tarifa especial: {discount}% descuento",
                    is_valid=True,
                    discount_percent=discount
                )
        
        return None
    
    def _build_contract_result(self, contract, vehicle, third_party) -> RateResult:
        """Construye el resultado para un contrato activo"""
        today = timezone.now().date()
        days_remaining = (contract.end_date - today).days
        
        # Determinar tipo de contrato por duración
        duration_days = (contract.end_date - contract.start_date).days
        if duration_days >= 25:
            contract_type = ContractType.MONTHLY
        elif duration_days >= 12:
            contract_type = ContractType.BIWEEKLY
        elif duration_days >= 5:
            contract_type = ContractType.WEEKLY
        else:
            contract_type = ContractType.DAILY
        
        # Verificar si tiene auto-renovación
        auto_renew = hasattr(contract, 'auto_renew') and contract.auto_renew
        
        return RateResult(
            rate_type=RateType.CONTRACT,
            contract_type=contract_type,
            amount=Decimal('0'),  # Sin cobro adicional
            contract=contract,
            third_party=third_party,
            vehicle=vehicle,
            message=f"Contrato {contract_type.value} vigente hasta {contract.end_date.strftime('%d/%m/%Y')}",
            is_valid=True,
            days_remaining=days_remaining,
            auto_renew=auto_renew
        )
    
    def _build_regular_result(self, category) -> RateResult:
        """Construye el resultado para tarifa regular"""
        return RateResult(
            rate_type=RateType.REGULAR,
            contract_type=None,
            amount=Decimal('0'),  # Se calcula por hora
            contract=None,
            third_party=None,
            vehicle=None,
            message="Tarifa regular por hora",
            is_valid=True
        )
    
    def check_expiring_contracts(self, days: int = 5) -> list:
        """
        Obtiene contratos que vencen en los próximos días.
        
        Args:
            days: Número de días para considerar como "por vencer"
        
        Returns:
            Lista de contratos por vencer
        """
        from monthly_contracts.models import MonthlyContract
        
        today = timezone.now().date()
        threshold = today + timedelta(days=days)
        
        return list(MonthlyContract.objects.all_tenants().filter(
            tenant=self.tenant,
            is_active=True,
            status='active',
            end_date__gte=today,
            end_date__lte=threshold
        ).select_related('third_party').prefetch_related('vehicles__vehicle').order_by('end_date'))
    
    def get_expired_contracts(self) -> list:
        """Obtiene contratos vencidos que necesitan renovación"""
        from monthly_contracts.models import MonthlyContract
        
        today = timezone.now().date()
        
        return list(MonthlyContract.objects.all_tenants().filter(
            tenant=self.tenant,
            is_active=True,
            end_date__lt=today
        ).select_related('third_party').prefetch_related('vehicles__vehicle').order_by('end_date'))
    
    def process_auto_renewals(self) -> Dict[str, Any]:
        """
        Procesa renovaciones automáticas de contratos.
        
        Returns:
            Diccionario con resultados del proceso
        """
        from monthly_contracts.models import MonthlyContract
        
        today = timezone.now().date()
        results = {
            'renewed': [],
            'failed': [],
            'pending_payment': []
        }
        
        # Buscar contratos con auto-renovación que vencen hoy o ya vencieron
        contracts = MonthlyContract.objects.all_tenants().filter(
            tenant=self.tenant,
            is_active=True,
            end_date__lte=today
        ).select_related('third_party').prefetch_related('vehicles__vehicle')
        
        for contract in contracts:
            # Verificar si tiene auto-renovación habilitada
            if hasattr(contract, 'auto_renew') and contract.auto_renew:
                try:
                    # Renovar automáticamente
                    contract.renew(months=1)
                    results['renewed'].append({
                        'contract': contract,
                        'new_end_date': contract.end_date
                    })
                    
                    # Crear registro de pago pendiente
                    results['pending_payment'].append(contract)
                except Exception as e:
                    results['failed'].append({
                        'contract': contract,
                        'error': str(e)
                    })
        
        return results


class RateCalculationService:
    """
    Servicio para calcular tarifas considerando contratos y descuentos.
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.detection_service = ContractDetectionService(tenant)
    
    def calculate_exit_fee(self, ticket) -> Dict[str, Any]:
        """
        Calcula la tarifa de salida considerando contratos y descuentos.
        
        Args:
            ticket: ParkingTicket
        
        Returns:
            Diccionario con información del cobro
        """
        # Detectar tarifa aplicable
        rate_result = self.detection_service.detect_rate(
            ticket.placa,
            ticket.category
        )
        
        result = {
            'rate_type': rate_result.rate_type.value,
            'contract_type': rate_result.contract_type.value if rate_result.contract_type else None,
            'message': rate_result.message,
            'is_contract': rate_result.rate_type == RateType.CONTRACT,
            'contract': rate_result.contract,
            'third_party': rate_result.third_party,
            'days_remaining': rate_result.days_remaining
        }
        
        if rate_result.rate_type == RateType.CONTRACT:
            # Contrato vigente - sin cobro
            result['amount'] = Decimal('0')
            result['original_amount'] = ticket.calculate_fee()
            result['discount'] = result['original_amount']
        
        elif rate_result.rate_type == RateType.SPECIAL:
            # Tarifa especial con descuento
            original = Decimal(str(ticket.calculate_fee()))
            discount = original * (rate_result.discount_percent / 100)
            result['amount'] = original - discount
            result['original_amount'] = original
            result['discount'] = discount
            result['discount_percent'] = rate_result.discount_percent
        
        elif rate_result.rate_type == RateType.COURTESY:
            # Cortesía
            result['amount'] = Decimal('0')
            result['original_amount'] = ticket.calculate_fee()
            result['discount'] = result['original_amount']
        
        else:
            # Tarifa regular
            result['amount'] = Decimal(str(ticket.calculate_fee()))
            result['original_amount'] = result['amount']
            result['discount'] = Decimal('0')
        
        return result


def get_contract_summary(tenant) -> Dict[str, Any]:
    """
    Obtiene un resumen de contratos para el dashboard.
    
    Args:
        tenant: Tenant actual
    
    Returns:
        Diccionario con estadísticas de contratos
    """
    from monthly_contracts.models import MonthlyContract, ContractVehicle
    from django.db.models import Sum, Count, Case, When, F, Q, Value, DecimalField

    today = timezone.now().date()
    
    contracts = MonthlyContract.objects.all_tenants().filter(
        tenant=tenant,
        is_active=True
    )
    
    # Use DB aggregation instead of iterating contracts for monthly_revenue
    # Contracts using combo_rate use that value; others sum their vehicles' rates
    active_contracts = contracts.filter(status='active')
    
    # Sum combo rates for contracts that use combo pricing
    combo_revenue = active_contracts.filter(
        use_combo_rate=True,
        combo_rate__isnull=False
    ).aggregate(total=Sum('combo_rate'))['total'] or Decimal('0')
    
    # Sum individual vehicle rates for contracts that don't use combo pricing
    vehicle_revenue = ContractVehicle.objects.filter(
        contract__in=active_contracts.filter(
            Q(use_combo_rate=False) | Q(combo_rate__isnull=True)
        ),
        is_active=True
    ).aggregate(total=Sum('monthly_rate'))['total'] or Decimal('0')
    
    monthly_revenue = combo_revenue + vehicle_revenue
    
    return {
        'total_active': active_contracts.count(),
        'total_pending': contracts.filter(status='pending').count(),
        'total_expired': contracts.filter(end_date__lt=today).count(),
        'expiring_soon': contracts.filter(
            status='active',
            end_date__gte=today,
            end_date__lte=today + timedelta(days=5)
        ).count(),
        'monthly_revenue': monthly_revenue
    }
