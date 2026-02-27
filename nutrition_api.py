"""
nutrition_api.py — Open Food Facts integration.

Searches the OFF API and converts nutriment values into our internal format.
All our fields store absolute values for the stated quantity (not per 100g),
so every value is scaled by (quantity / 100).

OFF API docs: https://wiki.openfoodfacts.org/API
No API key required. Rate limit: ~100 req/min, be respectful.
"""

import urllib.request
import urllib.parse
import json
from typing import Optional

OFF_SEARCH_URL  = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}"
OFF_FIELDS      = (
    "product_name,brands,product_quantity,serving_size,"
    "nutriments,categories_tags,image_small_url"
)

# ── Unit conversion map ───────────────────────────────────────────────────────
# OFF stores nutriments as X per 100g (mostly in grams, some in mg/µg).
# Format: off_key -> (our_field, multiplier_to_convert_per100g_to_our_unit)
# Our units: g for macros, mg for minerals, µg for fat-soluble vitamins.
#
# Convention: OFF nutriment keys use `_100g` suffix.
# Most are grams per 100g. Exceptions documented below.

OFF_FIELD_MAP = {
    # ── Macros ──────────────────────────────────────────────────────────────
    "energy-kcal":          ("kcal",         1.0),     # kcal / 100g → kcal
    "proteins":             ("protein_g",    1.0),     # g / 100g    → g
    "carbohydrates":        ("carbs_g",      1.0),     # g / 100g    → g
    "fat":                  ("fat_g",        1.0),     # g / 100g    → g
    # ── Carb detail ─────────────────────────────────────────────────────────
    "sugars":               ("sugars_g",     1.0),     # g / 100g    → g
    "fiber":                ("fiber_g",      1.0),     # g / 100g    → g
    # ── Fat detail ──────────────────────────────────────────────────────────
    "saturated-fat":        ("saturated_g",  1.0),     # g / 100g    → g
    "monounsaturated-fat":  ("monounsat_g",  1.0),     # g / 100g    → g
    "polyunsaturated-fat":  ("polyunsat_g",  1.0),     # g / 100g    → g
    # ── Minerals (OFF stores in g/100g → we want mg) ─────────────────────
    "sodium":               ("sodium_mg",    1000.0),  # g/100g × 1000 → mg
    "calcium":              ("calcium_mg",   1000.0),  # g/100g × 1000 → mg
    "iron":                 ("iron_mg",      1000.0),  # g/100g × 1000 → mg
    "potassium":            ("potassium_mg", 1000.0),  # g/100g × 1000 → mg
    "magnesium":            ("magnesium_mg", 1000.0),  # g/100g × 1000 → mg
    "zinc":                 ("zinc_mg",      1000.0),  # g/100g × 1000 → mg
    # ── Vitamins ────────────────────────────────────────────────────────────
    # OFF vitamin-a is in g/100g → we want µg (1g = 1,000,000 µg)
    "vitamin-a":            ("vit_a_mcg",    1_000_000.0),
    # OFF vitamin-c is in g/100g → we want mg (× 1000)
    "vitamin-c":            ("vit_c_mg",     1000.0),
    # OFF vitamin-d is in g/100g → we want µg (× 1,000,000)
    "vitamin-d":            ("vit_d_mcg",    1_000_000.0),
    # B vitamins: OFF stores as g/100g → mg (× 1000)
    "vitamin-b1":           ("vit_b1_mg",    1000.0),
    "vitamin-b2":           ("vit_b2_mg",    1000.0),
    # niacin / B3: stored as g/100g → mg
    "vitamin-pp":           ("vit_b3_mg",    1000.0),  # "PP" = niacin (B3)
    "vitamin-b6":           ("vit_b6_mg",    1000.0),
    # folates / B9: g/100g → µg
    "folates":              ("vit_b9_mcg",   1_000_000.0),
    # vitamin-b12: g/100g → µg
    "vitamin-b12":          ("vit_b12_mcg",  1_000_000.0),
}

# Fallback energy key when energy-kcal is absent
_ENERGY_KJ_KEY = "energy"   # kJ / 100g → kcal: divide by 4.184


# ── Core conversion ───────────────────────────────────────────────────────────

def nutriments_per_100g(nutriments: dict) -> dict:
    """
    Extract and convert OFF nutriments dict to our field names.
    Returns per-100g values in our units.
    """
    result = {}

    for off_key, (our_field, mult) in OFF_FIELD_MAP.items():
        val = nutriments.get(f"{off_key}_100g")
        if val is None:
            val = nutriments.get(off_key)   # some products omit the _100g suffix
        if val is not None:
            try:
                converted = float(val) * mult
                result[our_field] = round(converted, 4)
            except (ValueError, TypeError):
                pass

    # Fallback: kJ → kcal if energy-kcal is absent
    if "kcal" not in result:
        kj = nutriments.get("energy_100g") or nutriments.get("energy")
        if kj:
            try:
                result["kcal"] = round(float(kj) / 4.184, 1)
            except (ValueError, TypeError):
                pass

    return result


def scale_to_quantity(per_100g: dict, quantity_g: float) -> dict:
    """Scale per-100g values to the actual ingredient quantity."""
    factor = quantity_g / 100.0
    return {field: round(val * factor, 3) for field, val in per_100g.items()}


# ── Product parsing ───────────────────────────────────────────────────────────

def parse_product(product: dict) -> dict:
    """
    Convert an OFF product dict to a clean, frontend-friendly dict.
    Returns per-100g nutrition so the client can scale on quantity change.
    """
    nutriments = product.get("nutriments") or {}
    per_100g   = nutriments_per_100g(nutriments)

    # Best display name
    name   = (product.get("product_name") or "").strip()
    brand  = (product.get("brands") or "").split(",")[0].strip()
    label  = f"{name} — {brand}" if brand and brand.lower() not in name.lower() else name

    return {
        "barcode":    product.get("code") or product.get("id", ""),
        "name":       name,
        "label":      label,
        "brand":      brand,
        "per_100g":   per_100g,
        "kcal_100g":  per_100g.get("kcal"),
        "image":      product.get("image_small_url"),
    }


# ── API calls ─────────────────────────────────────────────────────────────────

TIMEOUT = 4   # seconds — fast enough for live search

def _get(url: str, params: dict) -> Optional[dict]:
    full_url = url + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(
            full_url,
            headers={"User-Agent": "RecipeBookApp/1.0 (personal use)"}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def search(query: str, page_size: int = 8) -> list[dict]:
    """
    Search OFF by product name. Returns a list of parsed product dicts.
    """
    if not query or not query.strip():
        return []

    data = _get(OFF_SEARCH_URL, {
        "action":       "process",
        "json":         "true",
        "search_terms": query.strip(),
        "page_size":    page_size,
        "fields":       OFF_FIELDS,
        "sort_by":      "unique_scans_n",   # most popular first
    })

    if not data or "products" not in data:
        return []

    results = []
    for p in data["products"]:
        name = (p.get("product_name") or "").strip()
        if not name:
            continue
        parsed = parse_product(p)
        if parsed["per_100g"]:   # only include products that have some nutrition data
            results.append(parsed)

    return results


def get_by_barcode(barcode: str) -> Optional[dict]:
    """Fetch a single product by barcode (for future barcode scanning feature)."""
    data = _get(OFF_PRODUCT_URL.format(barcode=barcode), {})
    if not data or data.get("status") != 1:
        return None
    return parse_product(data.get("product", {}))


# ── Pure Python unit tests (no network needed) ────────────────────────────────

def _test_conversion():
    mock_nutriments = {
        "energy-kcal_100g": 364,
        "proteins_100g":     10.3,
        "carbohydrates_100g": 76.3,
        "fat_100g":          1.0,
        "sugars_100g":       0.5,
        "fiber_100g":        2.7,
        "saturated-fat_100g": 0.2,
        "sodium_100g":       0.002,   # 2mg per 100g in g → expect 2.0 mg
        "calcium_100g":      0.015,   # 15mg per 100g
        "vitamin-c_100g":    0.0,
        "vitamin-d_100g":    0.0,
    }
    per_100g = nutriments_per_100g(mock_nutriments)
    assert per_100g["kcal"]       == 364,   f"kcal: {per_100g['kcal']}"
    assert per_100g["protein_g"]  == 10.3,  f"protein: {per_100g['protein_g']}"
    assert per_100g["sodium_mg"]  == 2.0,   f"sodium: {per_100g['sodium_mg']}"
    assert per_100g["calcium_mg"] == 15.0,  f"calcium: {per_100g['calcium_mg']}"

    scaled = scale_to_quantity(per_100g, 250)
    assert scaled["kcal"]      == round(364 * 2.5, 3),  f"scaled kcal: {scaled['kcal']}"
    assert scaled["protein_g"] == round(10.3 * 2.5, 3), f"scaled protein: {scaled['protein_g']}"
    assert scaled["sodium_mg"] == round(2.0 * 2.5, 3),  f"scaled sodium: {scaled['sodium_mg']}"

    print("✓ Conversion tests passed")
    print(f"  Example per_100g: kcal={per_100g['kcal']}, protein={per_100g['protein_g']}g, sodium={per_100g['sodium_mg']}mg")
    print(f"  Scaled to 250g:   kcal={scaled['kcal']}, protein={scaled['protein_g']}g, sodium={scaled['sodium_mg']}mg")


if __name__ == "__main__":
    _test_conversion()
