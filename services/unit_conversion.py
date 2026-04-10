"""
services/unit_conversion.py - Shared quantity normalization helpers.
"""

from utils import normalize_string

STANDARD_UNITS = [
    {"value": "g", "label": "g"},
    {"value": "kg", "label": "kg"},
    {"value": "ml", "label": "ml"},
    {"value": "cl", "label": "cl"},
    {"value": "dl", "label": "dl"},
    {"value": "l", "label": "L"},
]

STANDARD_CONVERSIONS = {
    "g": {"kind": "mass", "amount": 1.0},
    "gr": {"kind": "mass", "amount": 1.0},
    "gram": {"kind": "mass", "amount": 1.0},
    "kg": {"kind": "mass", "amount": 1000.0},
    "kilo": {"kind": "mass", "amount": 1000.0},
    "ml": {"kind": "volume", "amount": 1.0},
    "cl": {"kind": "volume", "amount": 10.0},
    "dl": {"kind": "volume", "amount": 100.0},
    "l": {"kind": "volume", "amount": 1000.0},
    "litre": {"kind": "volume", "amount": 1000.0},
}


def unit_key(unit: str) -> str:
    return normalize_string(unit)


def _coerce_density(density_g_ml: float | None) -> float | None:
    if density_g_ml is None:
        return None
    try:
        density = float(density_g_ml)
    except (TypeError, ValueError):
        return None
    return density if density > 0 else None


def build_conversion_map(unit_rows: list[dict] | None) -> dict:
    conversion_map = {}
    for row in unit_rows or []:
        key = row.get("unit_key") or unit_key(row.get("unit_name", ""))
        if not key:
            continue

        if row.get("grams_equivalent") is not None:
            conversion_map[key] = {"kind": "mass", "amount": float(row["grams_equivalent"])}
        elif row.get("ml_equivalent") is not None:
            conversion_map[key] = {"kind": "volume", "amount": float(row["ml_equivalent"])}
    return conversion_map


def convert_to_base_units(quantity: float, unit: str, unit_rows: list[dict] | None = None) -> tuple[str | None, float | None]:
    key = unit_key(unit)
    conversion_map = STANDARD_CONVERSIONS.copy()
    conversion_map.update(build_conversion_map(unit_rows))
    conversion = conversion_map.get(key)
    if not conversion:
        return None, None
    return conversion["kind"], quantity * conversion["amount"]


def convert_between_units(
    quantity: float,
    from_unit: str,
    to_unit: str,
    unit_rows: list[dict] | None = None,
    density_g_ml: float | None = None,
) -> float | None:
    from_kind, from_amount = convert_to_base_units(quantity, from_unit, unit_rows)
    to_kind, to_amount = convert_to_base_units(1.0, to_unit, unit_rows)
    if not from_kind or not to_kind or not to_amount:
        return None
    if from_kind != to_kind:
        density = _coerce_density(density_g_ml)
        if density is None:
            return None
        if from_kind == "mass" and to_kind == "volume":
            from_amount = from_amount / density
        elif from_kind == "volume" and to_kind == "mass":
            from_amount = from_amount * density
        else:
            return None
    return from_amount / to_amount


def merge_unit_options(unit_rows: list[dict] | None) -> list[dict]:
    seen = set()
    options = []
    for option in STANDARD_UNITS:
        key = unit_key(option["value"])
        seen.add(key)
        options.append(option)

    for row in unit_rows or []:
        key = row.get("unit_key") or unit_key(row.get("unit_name", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        options.append({"value": row["unit_name"], "label": row["unit_name"]})

    return options
