"""
routes/form_utils.py - Shared request-form parsing helpers for route modules.
"""

from constants import NUTRIENT_FIELDS
from models import Ingredient
from utils import _f


def _value_at(values: list[str], index: int) -> str:
    return values[index] if index < len(values) else ""


def parse_recipe_ingredients(form) -> list[Ingredient]:
    names = form.getlist("ing_name")
    quantities = form.getlist("ing_qty")
    units = form.getlist("ing_unit")
    library_ids = form.getlist("ing_library_id")
    nutrient_columns = {field: form.getlist(f"ing_{field}") for field in NUTRIENT_FIELDS}
    ingredients = []

    for index, raw_name in enumerate(names):
        name = raw_name.strip()
        if not name:
            continue

        nutrients = {
            field: _f(_value_at(values, index))
            for field, values in nutrient_columns.items()
        }
        ingredients.append(
            Ingredient(
                name=name,
                quantity=_f(_value_at(quantities, index)) or 0,
                unit=_value_at(units, index).strip(),
                library_id=int(_value_at(library_ids, index)) if _value_at(library_ids, index).isdigit() else None,
                **nutrients,
            )
        )

    return ingredients


def parse_library_nutrition(form, prefix: str = "nutr_") -> dict:
    per_100g = {}
    for field in NUTRIENT_FIELDS:
        value = form.get(f"{prefix}{field}", "").strip()
        if not value:
            continue

        try:
            per_100g[field] = float(value)
        except ValueError:
            continue

    return per_100g


def build_empty_library_entry() -> dict:
    entry = {f"{field}_100g": None for field in NUTRIENT_FIELDS}
    entry.update({"id": None, "name": "", "brand": "", "barcode": "", "search_key": "", "density_g_ml": None})
    return entry
