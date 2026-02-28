"""
nutrition_api.py — Dual-source nutrition lookup.

Sources:
  - USDA FoodData Central : fast (~200ms), raw/simple foods, very complete nutrients
  - Open Food Facts        : slower (~1-3s), branded/packaged products, all languages
  - ingredient_library     : local DB, instant, always checked first

The caller chooses the source via the `source` param ('usda' or 'off').
Library layer always runs first regardless of source.

USDA key: read from usda_key.txt in the project root (not committed to git).
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from db import get_connection, NUTRIENT_FIELDS


# ─────────────────────────────────────────────────────────────────────────────
# USDA API key — read from file, never hardcoded
# ─────────────────────────────────────────────────────────────────────────────

def _load_usda_key() -> str:
    """Read USDA key from usda_key.txt (project root or any parent dir)."""
    here = Path(__file__).parent
    for directory in [here, here.parent, Path.home()]:
        candidate = directory / "usda_key.txt"
        if candidate.exists():
            key = candidate.read_text().strip()
            if key:
                return key
    # Fallback: env var
    key = os.environ.get("USDA_API_KEY", "").strip()
    if key:
        return key
    # DEMO_KEY: 1000 req/day — fine for testing
    print("⚠️  usda_key.txt not found. Using DEMO_KEY (1000 req/day).")
    return "DEMO_KEY"


USDA_API_KEY    = _load_usda_key()
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
OFF_SEARCH_URL  = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}"
OFF_FIELDS      = "product_name,product_name_no,product_name_fr,product_name_en,brands,nutriments"

CONNECT_TIMEOUT = 3
READ_TIMEOUT    = 6


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Session
# ─────────────────────────────────────────────────────────────────────────────

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.headers.update({"User-Agent": "RecipeBookApp/1.0 (personal-use)"})
                retry = Retry(total=2, connect=2, read=1, backoff_factor=0.3,
                              status_forcelist=[502, 503, 504])
                s.mount("https://", HTTPAdapter(max_retries=retry))
                _session = s
    return _session


# ─────────────────────────────────────────────────────────────────────────────
# In-memory TTL cache
# ─────────────────────────────────────────────────────────────────────────────

_cache: dict[str, tuple[float, list]] = {}
_CACHE_TTL = 300  # 5 min


def _cache_get(key: str) -> Optional[list]:
    e = _cache.get(key)
    return e[1] if e and (time.time() - e[0]) < _CACHE_TTL else None


def _cache_set(key: str, value: list) -> None:
    _cache[key] = (time.time(), value)
    if len(_cache) > 200:
        cutoff = time.time() - _CACHE_TTL
        for k in [k for k, (ts, _) in list(_cache.items()) if ts < cutoff]:
            _cache.pop(k, None)


# ─────────────────────────────────────────────────────────────────────────────
# USDA FoodData Central
# ─────────────────────────────────────────────────────────────────────────────
#
# dataType priority: Foundation (best quality, raw foods) → SR Legacy (comprehensive)
#
# USDA nutrient IDs → our field names:
USDA_NUTRIENT_MAP = {
    # Macros
    1008: "kcal",
    1003: "protein_g",
    1005: "carbs_g",
    1004: "fat_g",
    # Carb detail
    2000: "sugars_g",
    1079: "fiber_g",
    # Fat detail
    1258: "saturated_g",
    1292: "polyunsat_g",
    1293: "monounsat_g",
    1257: "trans_fat_g",
    # Sterols
    1253: "cholesterol_mg",
    # Special fats
    1404: "omega3_g",   # Total omega-3
    1269: "omega6_g",   # Linoleic acid (main omega-6)
    # Minerals (USDA already in mg, µg)
    1093: "sodium_mg",
    1087: "calcium_mg",
    1089: "iron_mg",
    1092: "potassium_mg",
    1090: "magnesium_mg",
    1095: "zinc_mg",
    1091: "phosphorus_mg",
    1103: "selenium_mcg",
    1098: "copper_mg",
    1101: "manganese_mg",
    # Vitamins
    1106: "vit_a_mcg",    # RAE
    1162: "vit_c_mg",
    1110: "vit_d_mcg",
    1109: "vit_e_mg",
    1185: "vit_k_mcg",
    1165: "vit_b1_mg",
    1166: "vit_b2_mg",
    1167: "vit_b3_mg",
    1175: "vit_b6_mg",
    1177: "vit_b9_mcg",   # Folate DFE
    1178: "vit_b12_mcg",
}


def _parse_usda_food(food: dict) -> Optional[dict]:
    """Convert a USDA food entry to our standard per-100g dict."""
    name = (food.get("description") or "").strip()
    if not name:
        return None

    per_100g: dict[str, float] = {}
    for nutrient in food.get("foodNutrients", []):
        nid   = nutrient.get("nutrientId")
        value = nutrient.get("value")
        field = USDA_NUTRIENT_MAP.get(nid)
        if field and value is not None:
            try:
                per_100g[field] = round(float(value), 4)
            except (ValueError, TypeError):
                pass

    if not per_100g:
        return None

    brand     = (food.get("brandOwner") or food.get("brandName") or "").strip()
    data_type = food.get("dataType", "")
    return {
        "source":    "usda",
        "usda_id":   food.get("fdcId"),
        "name":      name,
        "label":     f"{name} — {brand}" if brand else name,
        "brand":     brand,
        "barcode":   "",
        "data_type": data_type,   # "Foundation", "SR Legacy", etc.
        "per_100g":  per_100g,
        "kcal_100g": per_100g.get("kcal"),
    }


def _usda_search_raw(query: str, fetch_size: int) -> list[dict]:
    """Search USDA FoodData Central. Foundation + SR Legacy data types."""
    try:
        resp = _get_session().get(
            USDA_SEARCH_URL,
            params={
                "query":    query,
                "api_key":  USDA_API_KEY,
                "dataType": "Foundation,SR Legacy",
                "pageSize": fetch_size,
            },
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"USDA search error: {e}")
        return []

    results = []
    for food in data.get("foods", []):
        parsed = _parse_usda_food(food)
        if parsed:
            results.append(parsed)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Open Food Facts
# ─────────────────────────────────────────────────────────────────────────────

OFF_FIELD_MAP = {
    "energy-kcal":         ("kcal",          1.0),
    "proteins":            ("protein_g",     1.0),
    "carbohydrates":       ("carbs_g",       1.0),
    "fat":                 ("fat_g",         1.0),
    "sugars":              ("sugars_g",      1.0),
    "fiber":               ("fiber_g",       1.0),
    "saturated-fat":       ("saturated_g",   1.0),
    "monounsaturated-fat": ("monounsat_g",   1.0),
    "polyunsaturated-fat": ("polyunsat_g",   1.0),
    "trans-fat":           ("trans_fat_g",   1.0),
    "cholesterol":         ("cholesterol_mg", 1000.0),   # g → mg
    "sodium":              ("sodium_mg",     1_000.0),
    "calcium":             ("calcium_mg",    1_000.0),
    "iron":                ("iron_mg",       1_000.0),
    "potassium":           ("potassium_mg",  1_000.0),
    "magnesium":           ("magnesium_mg",  1_000.0),
    "zinc":                ("zinc_mg",       1_000.0),
    "phosphorus":          ("phosphorus_mg", 1_000.0),
    "vitamin-a":           ("vit_a_mcg",     1_000_000.0),
    "vitamin-c":           ("vit_c_mg",      1_000.0),
    "vitamin-d":           ("vit_d_mcg",     1_000_000.0),
    "vitamin-e":           ("vit_e_mg",      1_000.0),
    "vitamin-k":           ("vit_k_mcg",     1_000_000.0),
    "vitamin-b1":          ("vit_b1_mg",     1_000.0),
    "vitamin-b2":          ("vit_b2_mg",     1_000.0),
    "vitamin-pp":          ("vit_b3_mg",     1_000.0),
    "vitamin-b6":          ("vit_b6_mg",     1_000.0),
    "folates":             ("vit_b9_mcg",    1_000_000.0),
    "vitamin-b12":         ("vit_b12_mcg",   1_000_000.0),
}


def nutriments_per_100g(nutriments: dict) -> dict:
    result = {}
    for off_key, (field, mult) in OFF_FIELD_MAP.items():
        val = nutriments.get(f"{off_key}_100g") or nutriments.get(off_key)
        if val is not None:
            try:
                result[field] = round(float(val) * mult, 4)
            except (ValueError, TypeError):
                pass
    if "kcal" not in result:
        kj = nutriments.get("energy_100g") or nutriments.get("energy")
        if kj:
            try:
                result["kcal"] = round(float(kj) / 4.184, 1)
            except (ValueError, TypeError):
                pass
    return result


def _parse_off_product(product: dict) -> dict:
    per_100g = nutriments_per_100g(product.get("nutriments") or {})
    name = (
        product.get("product_name") or
        product.get("product_name_en") or
        product.get("product_name_no") or
        product.get("product_name_fr") or ""
    ).strip()
    brand = (product.get("brands") or "").split(",")[0].strip()
    label = f"{name} — {brand}" if brand and brand.lower() not in name.lower() else name
    return {
        "source":    "off",
        "barcode":   product.get("code") or product.get("id", ""),
        "name":      name,
        "label":     label,
        "brand":     brand,
        "per_100g":  per_100g,
        "kcal_100g": per_100g.get("kcal"),
    }


def _off_search_raw(query: str, fetch_size: int) -> list[dict]:
    """Search OFF — optimised for all languages including Norwegian."""
    try:
        resp = _get_session().get(
            OFF_SEARCH_URL,
            params={
                "search_terms":  query,
                "search_simple": "1",
                "action":        "process",
                "json":          "1",
                "page_size":     fetch_size,
                "fields":        OFF_FIELDS,
                "sort_by":       "unique_scans_n",
            },
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"OFF search error: {e}")
        return []

    products = []
    for p in data.get("products", []):
        name = (p.get("product_name") or "").strip()
        if not name:
            continue
        parsed = _parse_off_product(p)
        if parsed.get("per_100g"):
            products.append(parsed)
    return products


# ─────────────────────────────────────────────────────────────────────────────
# Relevance scoring
# ─────────────────────────────────────────────────────────────────────────────

def _relevance(query: str, name: str) -> float:
    q, n = query.lower().strip(), name.lower().strip()
    qw = q.split()
    if n == q:
        return 100.0
    score = 0.0
    if n.startswith(q + " "):
        score += 60
    first = n.split()[0] if n.split() else ""
    if first == qw[0]:
        score += 30
    elif qw[0] in first:
        score += 15
    score += 10 if all(w in n for w in qw) else sum(4 for w in qw if w in n)
    score -= max(0, len(n.split()) - len(qw)) * 3
    return score


# ─────────────────────────────────────────────────────────────────────────────
# Ingredient Library (local DB cache)
# ─────────────────────────────────────────────────────────────────────────────

_LIB_FIELDS = ["id", "name", "brand", "barcode"] + [f + "_100g" for f in NUTRIENT_FIELDS]


def _normalise(s: str) -> str:
    return " ".join(s.lower().strip().split())


def library_search(query: str, limit: int = 5) -> list[dict]:
    key = _normalise(query)
    if not key:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT {', '.join(_LIB_FIELDS)}, used_count
                FROM ingredient_library
                WHERE search_key LIKE ?
                ORDER BY
                    CASE WHEN search_key = ?    THEN 0
                         WHEN search_key LIKE ? THEN 1
                         ELSE 2 END,
                    used_count DESC
                LIMIT ?""",
            (f"%{key}%", key, f"{key}%", limit)
        ).fetchall()
    return [_lib_row_to_product(r) for r in rows]


def _lib_row_to_product(row) -> dict:
    per_100g = {f: row[f + "_100g"] for f in NUTRIENT_FIELDS if row[f + "_100g"] is not None}
    name  = row["name"]
    brand = row["brand"] or ""
    label = f"{name} — {brand}" if brand and brand.lower() not in name.lower() else name
    return {
        "source":    "library",
        "id":        row["id"],
        "barcode":   row["barcode"] or "",
        "name":      name,
        "label":     label,
        "brand":     brand,
        "per_100g":  per_100g,
        "kcal_100g": per_100g.get("kcal"),
    }


def library_save(name: str, brand: str, barcode: str, per_100g: dict) -> int:
    key       = _normalise(name)
    nutr_vals = {f + "_100g": per_100g.get(f) for f in NUTRIENT_FIELDS}
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, used_count FROM ingredient_library WHERE search_key = ?", (key,)
        ).fetchone()
        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in nutr_vals)
            conn.execute(
                f"UPDATE ingredient_library SET {set_clause}, brand=?, barcode=?, "
                f"used_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [*nutr_vals.values(), brand, barcode, existing["used_count"] + 1, existing["id"]]
            )
            return existing["id"]
        cols = ["name", "search_key", "brand", "barcode"] + list(nutr_vals.keys())
        vals = [name, key, brand, barcode] + list(nutr_vals.values())
        return conn.execute(
            f"INSERT INTO ingredient_library ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})",
            vals
        ).lastrowid


def library_increment(library_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE ingredient_library SET used_count = used_count + 1 WHERE id = ?",
            (library_id,)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def search(query: str, source: str = "usda", page_size: int = 8) -> list[dict]:
    """
    Search for an ingredient.

    source: 'usda' (default, fast, raw foods) or 'off' (slower, branded products)

    Layer 0: ingredient_library — always first, instant
    Layer 1: USDA or OFF based on `source`
    Results merged, de-duplicated, re-ranked by relevance.
    Library results get +50 bonus (validated by user).
    """
    query = query.strip()
    if len(query) < 2:
        return []

    cache_key = f"search:{source}:{query.lower()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Layer 0: library
    lib_results = library_search(query, limit=page_size)

    # Layer 1: external API
    fetch_size = page_size * 3
    if source == "usda":
        api_results = _usda_search_raw(query, fetch_size)
    else:
        api_results = _off_search_raw(query, fetch_size)

    # Merge + dedup by normalised name
    seen: set[str] = {_normalise(r["name"]) for r in lib_results}
    merged = list(lib_results)
    for r in api_results:
        k = _normalise(r["name"])
        if k not in seen:
            seen.add(k)
            merged.append(r)

    # Re-rank
    merged.sort(
        key=lambda r: _relevance(query, r["name"]) + (50 if r["source"] == "library" else 0),
        reverse=True
    )
    results = merged[:page_size]

    _cache_set(cache_key, results)
    return results


def get_by_barcode(barcode: str) -> Optional[dict]:
    """Barcode lookup: library first, then OFF (barcodes are always OFF)."""
    cache_key = f"barcode:{barcode}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[0] if cached else None

    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_LIB_FIELDS)}, used_count FROM ingredient_library WHERE barcode = ?",
            (barcode,)
        ).fetchone()
    if row:
        result = _lib_row_to_product(row)
        _cache_set(cache_key, [result])
        return result

    try:
        resp = _get_session().get(
            OFF_PRODUCT_URL.format(barcode=barcode),
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    if data.get("status") != 1:
        return None
    result = _parse_off_product(data.get("product", {}))
    _cache_set(cache_key, [result])
    return result


def scale_to_quantity(per_100g: dict, quantity_g: float) -> dict:
    f = quantity_g / 100.0
    return {field: round(v * f, 3) for field, v in per_100g.items()}


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests (no network)
# ─────────────────────────────────────────────────────────────────────────────

def _test():
    # Conversion
    mock_off = {
        "energy-kcal_100g": 52, "proteins_100g": 0.3, "carbohydrates_100g": 14,
        "fat_100g": 0.2, "sodium_100g": 0.001, "calcium_100g": 0.006,
        "vitamin-e_100g": 0.003, "vitamin-k_100g": 0.0000036,
    }
    r = nutriments_per_100g(mock_off)
    assert r["kcal"] == 52
    assert r["sodium_mg"] == 1.0
    assert r["vit_e_mg"] == 3.0, f"vit_e: {r['vit_e_mg']}"
    assert r["vit_k_mcg"] == 3.6, f"vit_k: {r['vit_k_mcg']}"

    # USDA mock
    mock_usda_food = {
        "fdcId": 12345, "description": "Apples, raw", "dataType": "Foundation",
        "foodNutrients": [
            {"nutrientId": 1008, "value": 52},    # kcal
            {"nutrientId": 1003, "value": 0.26},  # protein
            {"nutrientId": 1005, "value": 13.81}, # carbs
            {"nutrientId": 1253, "value": 0},     # cholesterol
            {"nutrientId": 1404, "value": 0.009}, # omega-3
            {"nutrientId": 1109, "value": 0.18},  # vit E
            {"nutrientId": 1185, "value": 2.2},   # vit K
            {"nutrientId": 1091, "value": 11},    # phosphorus
            {"nutrientId": 1103, "value": 0},     # selenium
        ]
    }
    p = _parse_usda_food(mock_usda_food)
    assert p["name"] == "Apples, raw"
    assert p["per_100g"]["kcal"] == 52
    assert p["per_100g"]["vit_e_mg"] == 0.18
    assert p["per_100g"]["vit_k_mcg"] == 2.2
    assert p["per_100g"]["omega3_g"] == 0.009
    assert p["per_100g"]["phosphorus_mg"] == 11

    # Relevance
    assert _relevance("apple", "Apple") > _relevance("apple", "Apple juice")  # exact beats partial
    assert _relevance("eple", "Eple") == 100

    print("✓ All tests passed")
    print(f"  USDA key loaded: {'DEMO_KEY' if USDA_API_KEY == 'DEMO_KEY' else '*** (custom key)'}")


if __name__ == "__main__":
    _test()