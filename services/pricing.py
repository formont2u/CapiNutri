"""
services/pricing.py - Pricing logic with ingredient-aware unit conversion.
"""

from services.unit_conversion import convert_between_units


def calculate_cost(
    buy_qty: float,
    buy_unit: str,
    ref_price: float,
    ref_unit: str,
    unit_rows: list[dict] | None = None,
    density_g_ml: float | None = None,
) -> float | None:
    """Convert recipe units to the shop reference unit when possible."""
    recipe_unit = (buy_unit or "").lower().strip()
    reference_unit = (ref_unit or "").lower().strip()

    if buy_qty is None or ref_price is None:
        return None

    if recipe_unit == reference_unit:
        return buy_qty * ref_price

    converted_quantity = convert_between_units(buy_qty, recipe_unit, reference_unit, unit_rows, density_g_ml=density_g_ml)
    if converted_quantity is not None:
        return converted_quantity * ref_price

    return None
