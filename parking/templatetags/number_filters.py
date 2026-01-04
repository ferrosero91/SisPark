"""
Filtros de template para formatear números grandes.
"""
from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def format_currency(value):
    """
    Formatea un número como moneda colombiana con ajuste automático para números grandes.
    Hasta 100 millones se muestra completo, después se abrevia.
    Ejemplos:
    - 1500 → $1.500
    - 150000 → $150.000
    - 15000000 → $15.000.000
    - 100000000 → $100.000.000
    - 150000000 → $150M
    - 1500000000 → $1.500M
    """
    try:
        if value is None:
            return "$0"
        
        num = float(value)
        
        if num >= 1_000_000_000_000:  # Billones
            formatted = num / 1_000_000_000_000
            if formatted >= 100:
                return f"${formatted:,.0f}B".replace(",", ".")
            elif formatted >= 10:
                return f"${formatted:,.1f}B".replace(",", ".")
            else:
                return f"${formatted:,.2f}B".replace(",", ".")
        
        elif num >= 100_000_000:  # Más de 100 millones - abreviar
            formatted = num / 1_000_000
            if formatted >= 1000:
                return f"${formatted:,.0f}M".replace(",", ".")
            elif formatted >= 100:
                return f"${formatted:,.0f}M".replace(",", ".")
            else:
                return f"${formatted:,.1f}M".replace(",", ".")
        
        else:
            # Hasta 100 millones - formato completo con separador de miles
            return f"${num:,.0f}".replace(",", ".")
    
    except (ValueError, TypeError):
        return "$0"


@register.filter
def format_number(value):
    """
    Formatea un número con ajuste automático para números grandes (sin símbolo de moneda).
    Hasta 100 millones se muestra completo.
    """
    try:
        if value is None:
            return "0"
        
        num = float(value)
        
        if num >= 1_000_000_000:
            formatted = num / 1_000_000_000
            return f"{formatted:,.1f}B".replace(",", ".")
        
        elif num >= 100_000_000:
            formatted = num / 1_000_000
            return f"{formatted:,.0f}M".replace(",", ".")
        
        else:
            return f"{num:,.0f}".replace(",", ".")
    
    except (ValueError, TypeError):
        return "0"


@register.filter
def format_currency_full(value):
    """
    Formatea un número como moneda colombiana completa (sin abreviar nunca).
    """
    try:
        if value is None:
            return "$0"
        
        num = float(value)
        return f"${num:,.0f}".replace(",", ".")
    
    except (ValueError, TypeError):
        return "$0"
