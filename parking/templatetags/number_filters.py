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
    Ejemplos:
    - 1500 → $1.500
    - 150000 → $150.000
    - 1500000 → $1.5M
    - 1500000000 → $1.500M (millones)
    - 1500000000000 → $1.5B (billones)
    """
    try:
        if value is None:
            return "$0"
        
        num = float(value)
        
        if num >= 1_000_000_000_000:  # Billones
            formatted = num / 1_000_000_000_000
            if formatted >= 100:
                return f"${formatted:,.0f}B"
            elif formatted >= 10:
                return f"${formatted:,.1f}B"
            else:
                return f"${formatted:,.2f}B"
        
        elif num >= 1_000_000_000:  # Miles de millones
            formatted = num / 1_000_000
            return f"${formatted:,.0f}M"
        
        elif num >= 100_000_000:  # Cientos de millones
            formatted = num / 1_000_000
            return f"${formatted:,.0f}M"
        
        elif num >= 10_000_000:  # Decenas de millones
            formatted = num / 1_000_000
            return f"${formatted:,.1f}M"
        
        elif num >= 1_000_000:  # Millones
            formatted = num / 1_000_000
            return f"${formatted:,.2f}M"
        
        else:
            # Formato normal con separador de miles
            return f"${num:,.0f}".replace(",", ".")
    
    except (ValueError, TypeError):
        return "$0"


@register.filter
def format_number(value):
    """
    Formatea un número con ajuste automático para números grandes (sin símbolo de moneda).
    """
    try:
        if value is None:
            return "0"
        
        num = float(value)
        
        if num >= 1_000_000_000:
            formatted = num / 1_000_000_000
            return f"{formatted:,.1f}B"
        
        elif num >= 1_000_000:
            formatted = num / 1_000_000
            return f"{formatted:,.1f}M"
        
        elif num >= 10_000:
            formatted = num / 1_000
            return f"{formatted:,.1f}K"
        
        else:
            return f"{num:,.0f}".replace(",", ".")
    
    except (ValueError, TypeError):
        return "0"


@register.filter
def format_currency_full(value):
    """
    Formatea un número como moneda colombiana completa (sin abreviar).
    """
    try:
        if value is None:
            return "$0"
        
        num = float(value)
        return f"${num:,.0f}".replace(",", ".")
    
    except (ValueError, TypeError):
        return "$0"
