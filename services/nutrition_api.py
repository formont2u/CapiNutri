"""
services/nutrition_api.py — Dual-source nutrition lookup.
Gère uniquement les requêtes HTTP externes (USDA & Open Food Facts) et le cache en mémoire.
La sauvegarde locale est déléguée au fichier crud.py.
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── IMPORTS PROPRES ──
from constants import NUTRIENT_FIELDS
import crud 

# ─────────────────────────────────────────────────────────────────────────────
# USDA API key
# ─────────────────────────────────────────────────────────────────────────────

def _load_usda_key() -> str:
    """Cherche la clé USDA dans le dossier racine (un niveau au-dessus de 'services')."""
    # __file__ = services/nutrition_api.py
    # .parent = services/
    # .parent.parent = Capynutri/ (la racine)
    root_dir = Path(__file__).resolve().parent.parent 
    
    for directory in [root_dir, Path.home()]:
        candidate = directory / "usda_key.txt"
        if candidate.exists():
            key = candidate.read_text().strip()
            if key: 
                return key
                
    key = os.environ.get("USDA_API_KEY", "").strip()
    if key: 
        return key
        
    print("⚠️ usda_key.txt not found. Using DEMO_KEY (1000 req/day).")
    return "DEMO_KEY"

USDA_API_KEY    = _load_usda_key()
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
OFF_SEARCH_URL  = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}"
OFF_FIELDS      = "product_name,product_name_no,product_name_fr,product_name_en,brands,nutriments"

CONNECT_TIMEOUT = 10
READ_TIMEOUT    = 20

# ─────────────────────────────────────────────────────────────────────────────
# HTTP Session & Cache
# ─────────────────────────────────────────────────────────────────────────────

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()

def _get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                s.headers.update({"User-Agent": "Capynutri/1.0 (personal-use)"})
                retry = Retry(total=2, connect=2, read=1, backoff_factor=0.3, status_forcelist=[502, 503, 504])
                s.mount("https://", HTTPAdapter(max_retries=retry))
                _session = s
    return _session

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
# Parsers & Utils (USDA / Open Food Facts)
# ─────────────────────────────────────────────────────────────────────────────

USDA_NUTRIENT_MAP = {
    1008: "kcal", 1003: "protein_g", 1005: "carbs_g", 1004: "fat_g",
    2000: "sugars_g", 1079: "fiber_g", 1258: "saturated_g", 1292: "polyunsat_g",
    1293: "monounsat_g", 1257: "trans_fat_g", 1253: "cholesterol_mg", 1404: "omega3_g",
    1269: "omega6_g", 1093: "sodium_mg", 1087: "calcium_mg", 1089: "iron_mg",
    1092: "potassium_mg", 1090: "magnesium_mg", 1095: "zinc_mg", 1091: "phosphorus_mg",
    1103: "selenium_mcg", 1098: "copper_mg", 1101: "manganese_mg", 1106: "vit_a_mcg",
    1162: "vit_c_mg", 1110: "vit_d_mcg", 1109: "vit_e_mg", 1185: "vit_k_mcg",
    1165: "vit_b1_mg", 1166: "vit_b2_mg", 1167: "vit_b3_mg", 1175: "vit_b6_mg",
    1177: "vit_b9_mcg", 1178: "vit_b12_mcg",
}

OFF_FIELD_MAP = {
    "energy-kcal": ("kcal", 1.0), "proteins": ("protein_g", 1.0), "carbohydrates": ("carbs_g", 1.0),
    "fat": ("fat_g", 1.0), "sugars": ("sugars_g", 1.0), "fiber": ("fiber_g", 1.0),
    "saturated-fat": ("saturated_g", 1.0), "monounsaturated-fat": ("monounsat_g", 1.0),
    "polyunsaturated-fat": ("polyunsat_g", 1.0), "trans-fat": ("trans_fat_g", 1.0),
    "cholesterol": ("cholesterol_mg", 1000.0), "sodium": ("sodium_mg", 1000.0),
    "calcium": ("calcium_mg", 1000.0), "iron": ("iron_mg", 1000.0),
    "potassium": ("potassium_mg", 1000.0), "magnesium": ("magnesium_mg", 1000.0),
    "zinc": ("zinc_mg", 1000.0), "phosphorus": ("phosphorus_mg", 1000.0),
    "vitamin-a": ("vit_a_mcg", 1000000.0), "vitamin-c": ("vit_c_mg", 1000.0),
    "vitamin-d": ("vit_d_mcg", 1000000.0), "vitamin-e": ("vit_e_mg", 1000.0),
    "vitamin-k": ("vit_k_mcg", 1000000.0), "vitamin-b1": ("vit_b1_mg", 1000.0),
    "vitamin-b2": ("vit_b2_mg", 1000.0), "vitamin-pp": ("vit_b3_mg", 1000.0),
    "vitamin-b6": ("vit_b6_mg", 1000.0), "folates": ("vit_b9_mcg", 1000000.0),
    "vitamin-b12": ("vit_b12_mcg", 1000000.0),
}

def _parse_usda_food(food: dict) -> Optional[dict]:
    name = (food.get("description") or "").strip()
    if not name: return None
    per_100g = {}
    for nutrient in food.get("foodNutrients", []):
        field = USDA_NUTRIENT_MAP.get(nutrient.get("nutrientId"))
        if field and nutrient.get("value") is not None:
            try: per_100g[field] = round(float(nutrient.get("value")), 4)
            except (ValueError, TypeError): pass
    if not per_100g: return None
    brand = (food.get("brandOwner") or food.get("brandName") or "").strip()
    return {
        "source": "usda", "usda_id": food.get("fdcId"), "name": name,
        "label": f"{name} — {brand}" if brand else name, "brand": brand,
        "barcode": "", "data_type": food.get("dataType", ""),
        "per_100g": per_100g, "kcal_100g": per_100g.get("kcal"),
    }

def _usda_search_raw(query: str, fetch_size: int) -> list[dict]:
    try:
        resp = _get_session().get(USDA_SEARCH_URL, params={"query": query, "api_key": USDA_API_KEY, "dataType": "Foundation,SR Legacy", "pageSize": fetch_size}, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        return [p for p in (_parse_usda_food(f) for f in resp.json().get("foods", [])) if p]
    except Exception as e:
        print(f"USDA search error: {e}")
        return []

def _parse_off_product(product: dict) -> dict:
    nutriments = product.get("nutriments") or {}
    per_100g = {}
    for off_key, (field, mult) in OFF_FIELD_MAP.items():
        val = nutriments.get(f"{off_key}_100g") or nutriments.get(off_key)
        if val is not None:
            try: per_100g[field] = round(float(val) * mult, 4)
            except (ValueError, TypeError): pass
    if "kcal" not in per_100g and (kj := nutriments.get("energy_100g") or nutriments.get("energy")):
        try: per_100g["kcal"] = round(float(kj) / 4.184, 1)
        except (ValueError, TypeError): pass

    name = (product.get("product_name") or product.get("product_name_en") or "").strip()
    brand = (product.get("brands") or "").split(",")[0].strip()
    return {
        "source": "off", "barcode": product.get("code") or product.get("id", ""),
        "name": name, "label": f"{name} — {brand}" if brand and brand.lower() not in name.lower() else name,
        "brand": brand, "per_100g": per_100g, "kcal_100g": per_100g.get("kcal"),
    }

def _off_search_raw(query: str, fetch_size: int) -> list[dict]:
    try:
        resp = _get_session().get(OFF_SEARCH_URL, params={"search_terms": query, "search_simple": "1", "action": "process", "json": "1", "page_size": fetch_size, "fields": OFF_FIELDS, "sort_by": "unique_scans_n"}, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        return [p for p in (_parse_off_product(f) for f in resp.json().get("products", [])) if p.get("per_100g") and p.get("name")]
    except Exception as e:
        print(f"OFF search error: {e}")
        return []

def _relevance(query: str, name: str) -> float:
    q, n = query.lower().strip(), name.lower().strip()
    if n == q: return 100.0
    qw = q.split()
    score = 60 if n.startswith(q + " ") else 0
    first = n.split()[0] if n.split() else ""
    score += 30 if first == qw[0] else (15 if qw[0] in first else 0)
    score += 10 if all(w in n for w in qw) else sum(4 for w in qw if w in n)
    return score - (max(0, len(n.split()) - len(qw)) * 3)

# ─────────────────────────────────────────────────────────────────────────────
# Library Mapping (Délègue les requêtes à CRUD)
# ─────────────────────────────────────────────────────────────────────────────

def _lib_row_to_product(row_dict: dict) -> dict:
    per_100g = {f: row_dict.get(f + "_100g") for f in NUTRIENT_FIELDS if row_dict.get(f + "_100g") is not None}
    name  = row_dict.get("name", "")
    brand = row_dict.get("brand") or ""
    return {
        "source": "library", "id": row_dict.get("id"), "barcode": row_dict.get("barcode") or "",
        "name": name, "label": f"{name} — {brand}" if brand and brand.lower() not in name.lower() else name,
        "brand": brand, "per_100g": per_100g, "kcal_100g": per_100g.get("kcal"),
    }

def library_save(name: str, brand: str, barcode: str, per_100g: dict) -> int:
    return crud.save_ingredient_to_library(name, brand, barcode, per_100g)

def library_increment(library_id: int) -> None:
    crud.increment_library_usage(library_id)

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def search(query: str, source: str = "usda", page_size: int = 8) -> list[dict]:
    query = query.strip()
    if len(query) < 2: return []

    cache_key = f"search:{source}:{query.lower()}"
    cached = _cache_get(cache_key)
    if cached is not None: return cached

    # 1. Requête au CRUD local
    lib_rows = crud.search_ingredient_library(query, limit=page_size)
    lib_results = [_lib_row_to_product(r) for r in lib_rows]

    # 2. Requête API externe
    fetch_size = page_size * 3
    api_results = _usda_search_raw(query, fetch_size) if source == "usda" else _off_search_raw(query, fetch_size)

    # 3. Fusion et score
    seen = {r["name"].lower().strip() for r in lib_results}
    merged = list(lib_results)
    for r in api_results:
        k = r["name"].lower().strip()
        if k not in seen:
            seen.add(k)
            merged.append(r)

    merged.sort(key=lambda r: _relevance(query, r["name"]) + (50 if r["source"] == "library" else 0), reverse=True)
    results = merged[:page_size]
    _cache_set(cache_key, results)
    return results

def get_by_barcode(barcode: str) -> Optional[dict]:
    cache_key = f"barcode:{barcode}"
    cached = _cache_get(cache_key)
    if cached is not None: return cached[0] if cached else None

    # 1. Vérification dans le CRUD local
    row = crud.get_library_entry_by_barcode(barcode)
    if row:
        result = _lib_row_to_product(row)
        _cache_set(cache_key, [result])
        return result

    # 2. Vérification sur Open Food Facts
    try:
        resp = _get_session().get(OFF_PRODUCT_URL.format(barcode=barcode), timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None

    if data.get("status") != 1: return None
    result = _parse_off_product(data.get("product", {}))
    _cache_set(cache_key, [result])
    return result

def scale_to_quantity(per_100g: dict, quantity_g: float) -> dict:
    f = quantity_g / 100.0
    return {field: round(v * f, 3) for field, v in per_100g.items()}