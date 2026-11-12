"""Centralized Indian Rupee (INR - ₹) Currency Module.

Provides deterministic financial arithmetic, integer paise precision,
and standard Indian numbering system formatting (lakhs/crores).
Strictly eliminates binary floating-point rounding errors.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Optional

# Global Currency Constants
CURRENCY_CODE = "INR"
CURRENCY_SYMBOL = "₹"
LOCALE = "en_IN"
MINOR_UNIT = "paise"
DECIMAL_PLACES = 2
GROUPING = "Indian"
DEFAULT_TIMEZONE = "Asia/Kolkata"

PAISE_IN_RUPEE = Decimal("100")
ROUNDING_POLICY = ROUND_HALF_UP


def round_money(amount: Union[Decimal, float, int, str]) -> Decimal:
    """Quantize monetary amount to exactly 2 decimal places using ROUND_HALF_UP."""
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return amount.quantize(Decimal("0.01"), rounding=ROUNDING_POLICY)


def to_paise(amount: Union[Decimal, float, int, str]) -> int:
    """Convert Rupee amount to integer paise using Decimal and ROUND_HALF_UP.
    
    Examples:
        to_paise(1) -> 100
        to_paise(100.00) -> 10000
        to_paise("1250.50") -> 125050
        to_paise(10000) -> 1000000
    """
    if isinstance(amount, int):
        # Already an integer, verify if it represents rupees
        d = Decimal(str(amount)) * PAISE_IN_RUPEE
        return int(d.quantize(Decimal("1"), rounding=ROUNDING_POLICY))
    
    if not isinstance(amount, Decimal):
        d = Decimal(str(amount))
    else:
        d = amount
    paise_dec = (d * PAISE_IN_RUPEE).quantize(Decimal("1"), rounding=ROUNDING_POLICY)
    return int(paise_dec)


def from_paise(paise: Union[int, Decimal, str]) -> Decimal:
    """Convert integer paise to exact Decimal Rupees (2 decimal places).
    
    Examples:
        from_paise(100) -> Decimal('1.00')
        from_paise(125050) -> Decimal('1250.50')
    """
    if not isinstance(paise, Decimal):
        paise_dec = Decimal(str(int(paise)))
    else:
        paise_dec = paise
    return (paise_dec / PAISE_IN_RUPEE).quantize(Decimal("0.01"), rounding=ROUNDING_POLICY)


def _format_indian_integer(num_str: str) -> str:
    """Group digits according to Indian numbering system (3 digits, then groups of 2)."""
    if len(num_str) <= 3:
        return num_str
    
    last3 = num_str[-3:]
    remaining = num_str[:-3]
    groups = []
    while len(remaining) > 2:
        groups.insert(0, remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        groups.insert(0, remaining)
    return ",".join(groups) + "," + last3


def format_inr(
    amount: Union[Decimal, float, int, str],
    include_symbol: bool = True,
    compact: bool = False,
) -> str:
    """Format an amount in Rupees using Indian numbering formatting (en-IN).
    
    Examples:
        format_inr(100) -> "₹100.00"
        format_inr(1000) -> "₹1,000.00"
        format_inr(10000) -> "₹10,000.00"
        format_inr(100000) -> "₹1,00,000.00"
        format_inr(1000000) -> "₹10,00,000.00"
        format_inr(10000000) -> "₹1,00,00,000.00"
        format_inr(10386130.23, compact=True) -> "₹1.04 Cr"
    """
    d = round_money(amount)
    
    if compact:
        abs_val = abs(float(d))
        sym = f"{CURRENCY_SYMBOL}" if include_symbol else ""
        neg = "-" if d < 0 else ""
        if abs_val >= 10000000:  # 1 Crore
            return f"{neg}{sym}{abs_val / 10000000:.2f} Cr"
        elif abs_val >= 100000:  # 1 Lakh
            return f"{neg}{sym}{abs_val / 100000:.2f} L"
        elif abs_val >= 1000:
            return f"{neg}{sym}{abs_val / 1000:.2f} K"
    
    # Standard Indian full rupee-paise formatting
    str_val = f"{d:.2f}"
    is_negative = str_val.startswith("-")
    if is_negative:
        str_val = str_val[1:]
    
    int_part, dec_part = str_val.split(".", 1)
    formatted_int = _format_indian_integer(int_part)
    
    prefix = f"-{CURRENCY_SYMBOL}" if (is_negative and include_symbol) else ("-" if is_negative else (f"{CURRENCY_SYMBOL}" if include_symbol else ""))
    return f"{prefix}{formatted_int}.{dec_part}"


def format_inr_paise(
    paise: Union[int, Decimal, str],
    include_symbol: bool = True,
    compact: bool = False,
) -> str:
    """Format an amount stored in integer paise as INR string.
    
    Examples:
        format_inr_paise(10000) -> "₹100.00"
        format_inr_paise(125050) -> "₹1,250.50"
        format_inr_paise(1000000000, compact=True) -> "₹1.00 Cr"
    """
    rupees = from_paise(paise)
    return format_inr(rupees, include_symbol=include_symbol, compact=compact)


def calculate_percentage(
    amount_paise: int,
    rate_basis_points: int,
) -> int:
    """Calculate percentage fee in integer paise from basis points (1 bp = 0.01%).
    
    Uses Decimal arithmetic and ROUND_HALF_UP.
    """
    amt = Decimal(str(amount_paise))
    bps = Decimal(str(rate_basis_points))
    fee = (amt * bps / Decimal("10000")).quantize(Decimal("1"), rounding=ROUNDING_POLICY)
    return int(fee)
