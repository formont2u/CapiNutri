"""
pricing_db.py — Configuration et accès aux données pour la base des prix (pricing.db).
Strictement réservé au SQL.
"""
import sqlite3
from pathlib import Path
from utils import normalize_string

DB_PATH = Path(__file__).parent / "pricing.db"

def get_pricing_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_pricing_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS shops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
                ingredient_norm TEXT NOT NULL,
                ingredient_raw TEXT NOT NULL,
                price REAL NOT NULL,
                ref_unit TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(shop_id, ingredient_norm)
            );
        """)
        # Injection par défaut des supermarchés norvégiens 🇳🇴
        conn.executescript("""
            INSERT OR IGNORE INTO shops (name) VALUES ('REMA 1000'), ('Kiwi'), ('Extra'), ('Meny'), ('Oda'), ('Bunnpris');
        """)

def get_shops() -> list[dict]:
    with get_pricing_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM shops ORDER BY name")]

def add_price(shop_id: int, raw_name: str, price: float, unit: str) -> None:
    norm_name = normalize_string(raw_name)
    with get_pricing_conn() as conn:
        conn.execute("""
            INSERT INTO prices (shop_id, ingredient_norm, ingredient_raw, price, ref_unit)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(shop_id, ingredient_norm) 
            DO UPDATE SET price=excluded.price, ref_unit=excluded.ref_unit, ingredient_raw=excluded.ingredient_raw, updated_at=CURRENT_TIMESTAMP
        """, (shop_id, norm_name, raw_name, price, unit.strip().lower()))

def get_all_prices() -> list[dict]:
    with get_pricing_conn() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT p.*, s.name as shop_name 
            FROM prices p JOIN shops s ON p.shop_id = s.id 
            ORDER BY p.ingredient_raw, s.name
        """)]

def delete_price(price_id: int) -> None:
    with get_pricing_conn() as conn:
        conn.execute("DELETE FROM prices WHERE id = ?", (price_id,))

def get_best_prices(ingredient_names: list[str]) -> dict:
    norms = [normalize_string(n) for n in ingredient_names]
    if not norms: return {}
    
    placeholders = ",".join("?" * len(norms))
    with get_pricing_conn() as conn:
        rows = conn.execute(f"""
            SELECT p.ingredient_norm, p.price, p.ref_unit, s.name as shop_name
            FROM prices p JOIN shops s ON p.shop_id = s.id
            WHERE p.ingredient_norm IN ({placeholders})
            ORDER BY p.price ASC
        """, norms).fetchall()
        
    best = {}
    for r in rows:
        norm = r["ingredient_norm"]
        if norm not in best: best[norm] = []
        best[norm].append(dict(r))
    return best