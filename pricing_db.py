import sqlite3
from pathlib import Path
import unicodedata, re

DB_PATH = Path(__file__).parent / "pricing.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _norm(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()

def init_db():
    with get_conn() as conn:
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

def get_shops():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM shops ORDER BY name")]

def add_price(shop_id, raw_name, price, unit):
    norm_name = _norm(raw_name)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO prices (shop_id, ingredient_norm, ingredient_raw, price, ref_unit)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(shop_id, ingredient_norm) 
            DO UPDATE SET price=excluded.price, ref_unit=excluded.ref_unit, ingredient_raw=excluded.ingredient_raw, updated_at=CURRENT_TIMESTAMP
        """, (shop_id, norm_name, raw_name, price, unit.strip().lower()))

def get_all_prices():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT p.*, s.name as shop_name 
            FROM prices p JOIN shops s ON p.shop_id = s.id 
            ORDER BY p.ingredient_raw, s.name
        """)]

def delete_price(price_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM prices WHERE id = ?", (price_id,))

def get_best_prices(ingredient_names):
    norms = [_norm(n) for n in ingredient_names]
    if not norms: return {}
    
    placeholders = ",".join("?" * len(norms))
    with get_conn() as conn:
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

def calculate_cost(buy_qty, buy_unit, ref_price, ref_unit):
    """Convertit l'unité de la recette vers l'unité du magasin pour calculer le prix."""
    b_u = (buy_unit or "").lower().strip()
    r_u = (ref_unit or "").lower().strip()
    if b_u == r_u: return buy_qty * ref_price
    
    # Grammes -> Kilo
    if b_u in ['g', 'gr', 'gram'] and r_u in ['kg', 'kilo']: return (buy_qty / 1000.0) * ref_price
    # Ml/Cl -> Litre
    if b_u in ['ml'] and r_u in ['l', 'litre']: return (buy_qty / 1000.0) * ref_price
    if b_u in ['cl'] and r_u in ['l', 'litre']: return (buy_qty / 100.0) * ref_price
    if b_u in ['dl'] and r_u in ['l', 'litre']: return (buy_qty / 10.0) * ref_price
    
    return buy_qty * ref_price