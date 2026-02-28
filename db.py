"""
db.py — Database connection and schema.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "recipes.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── All nutrient field names (order matters — used everywhere) ────────────────
NUTRIENT_FIELDS = [
    # Macros
    "kcal", "protein_g", "carbs_g", "fat_g",
    # Carb detail
    "sugars_g", "fiber_g",
    # Fat detail
    "saturated_g", "monounsat_g", "polyunsat_g",
    # Minerals
    "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "magnesium_mg", "zinc_mg",
    # Core vitamins
    "vit_a_mcg", "vit_c_mg", "vit_d_mcg",
    "vit_b1_mg", "vit_b2_mg", "vit_b3_mg", "vit_b6_mg", "vit_b9_mcg", "vit_b12_mcg",
    # USDA-enhanced
    "cholesterol_mg", "trans_fat_g", "omega3_g", "omega6_g",
    "phosphorus_mg", "selenium_mcg", "copper_mg", "manganese_mg",
    "vit_e_mg", "vit_k_mcg",
]

MACRO_FIELDS   = ["kcal", "protein_g", "carbs_g", "fat_g"]
CARB_FIELDS    = ["sugars_g", "fiber_g"]
FAT_FIELDS     = ["saturated_g", "monounsat_g", "polyunsat_g"]
MICRO_FIELDS   = ["sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "magnesium_mg", "zinc_mg"]
VITAMIN_FIELDS = ["vit_a_mcg", "vit_c_mg", "vit_d_mcg", "vit_e_mg", "vit_k_mcg",
                  "vit_b1_mg", "vit_b2_mg", "vit_b3_mg", "vit_b6_mg", "vit_b9_mcg", "vit_b12_mcg"]
USDA_FIELDS    = ["cholesterol_mg", "trans_fat_g", "omega3_g", "omega6_g",
                  "phosphorus_mg", "selenium_mcg", "copper_mg", "manganese_mg"]

NUTRIENT_LABELS = {
    "kcal":          ("Calories",          "kcal"),
    "protein_g":     ("Protéines",         "g"),
    "carbs_g":       ("Glucides",          "g"),
    "fat_g":         ("Lipides",           "g"),
    "sugars_g":      ("Sucres",            "g"),
    "fiber_g":       ("Fibres",            "g"),
    "saturated_g":   ("Saturés",           "g"),
    "monounsat_g":   ("Mono-insaturés",    "g"),
    "polyunsat_g":   ("Poly-insaturés",    "g"),
    "sodium_mg":     ("Sodium",            "mg"),
    "calcium_mg":    ("Calcium",           "mg"),
    "iron_mg":       ("Fer",               "mg"),
    "potassium_mg":  ("Potassium",         "mg"),
    "magnesium_mg":  ("Magnésium",         "mg"),
    "zinc_mg":       ("Zinc",              "mg"),
    "vit_a_mcg":     ("Vit. A",            "µg"),
    "vit_c_mg":      ("Vit. C",            "mg"),
    "vit_d_mcg":     ("Vit. D",            "µg"),
    "vit_e_mg":      ("Vit. E",            "mg"),
    "vit_k_mcg":     ("Vit. K",            "µg"),
    "vit_b1_mg":     ("Vit. B1",           "mg"),
    "vit_b2_mg":     ("Vit. B2",           "mg"),
    "vit_b3_mg":     ("Vit. B3",           "mg"),
    "vit_b6_mg":     ("Vit. B6",           "mg"),
    "vit_b9_mcg":    ("Vit. B9 (Folate)",  "µg"),
    "vit_b12_mcg":   ("Vit. B12",          "µg"),
    # USDA-enhanced
    "cholesterol_mg": ("Cholestérol",      "mg"),
    "trans_fat_g":    ("Acides gras trans","g"),
    "omega3_g":       ("Oméga-3",          "g"),
    "omega6_g":       ("Oméga-6",          "g"),
    "phosphorus_mg":  ("Phosphore",        "mg"),
    "selenium_mcg":   ("Sélénium",         "µg"),
    "copper_mg":      ("Cuivre",           "mg"),
    "manganese_mg":   ("Manganèse",        "mg"),
}

# Reference Daily Intakes (EU/US guidelines)
RDI = {
    "kcal": 2000, "protein_g": 50, "carbs_g": 260, "fat_g": 70,
    "sugars_g": 50, "fiber_g": 30,
    "saturated_g": 20, "sodium_mg": 2300, "calcium_mg": 1000,
    "iron_mg": 14, "potassium_mg": 3500, "magnesium_mg": 375, "zinc_mg": 11,
    "vit_a_mcg": 800, "vit_c_mg": 80, "vit_d_mcg": 15,
    "vit_e_mg": 15, "vit_k_mcg": 120,
    "vit_b1_mg": 1.1, "vit_b2_mg": 1.4, "vit_b3_mg": 16,
    "vit_b6_mg": 1.4, "vit_b9_mcg": 200, "vit_b12_mcg": 2.4,
    "cholesterol_mg": 300, "trans_fat_g": 2,
    "omega3_g": 1.6, "omega6_g": 17,
    "phosphorus_mg": 700, "selenium_mcg": 55,
    "copper_mg": 0.9, "manganese_mg": 2.3,
}


def _nutr_cols(prefix="", suffix=""):
    """Generate SQL column definitions for all nutrient fields."""
    return "\n".join(f"    {prefix}{f}{suffix}  REAL," for f in NUTRIENT_FIELDS)


def init_db() -> None:
    nutr_ing = _nutr_cols()
    nutr_log = _nutr_cols()
    nutr_lib = _nutr_cols(suffix="_100g")

    with get_connection() as conn:
        conn.executescript(f"""
            -- Core tables
            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS recipes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                servings     REAL NOT NULL DEFAULT 1,
                instructions TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ingredients (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                name      TEXT NOT NULL,
                quantity  REAL NOT NULL,
                unit      TEXT NOT NULL DEFAULT '',
{nutr_ing}
                _placeholder INTEGER
            );
            CREATE TABLE IF NOT EXISTS pantry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                quantity REAL, unit TEXT NOT NULL DEFAULT ''
            );
            -- Nutrition tracking
            CREATE TABLE IF NOT EXISTS user_profile (
                id             INTEGER PRIMARY KEY DEFAULT 1,
                name           TEXT,
                weight_kg      REAL, height_cm REAL, age INTEGER,
                sex            TEXT,
                activity_level TEXT DEFAULT 'moderate',
                goal           TEXT DEFAULT 'maintain',
                goal_kcal      REAL, goal_protein_g REAL,
                goal_carbs_g   REAL, goal_fat_g     REAL,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS food_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date   DATE NOT NULL,
                meal_type  TEXT DEFAULT 'other',
                recipe_id  INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
                label      TEXT NOT NULL,
                servings   REAL NOT NULL DEFAULT 1,
{nutr_log}
                _placeholder INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS exercise_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date     DATE NOT NULL,
                name         TEXT NOT NULL,
                kcal_burned  REAL NOT NULL DEFAULT 0,
                duration_min INTEGER,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS daily_goals (
                log_date     DATE PRIMARY KEY,
                goal_kcal    REAL, goal_protein_g REAL,
                goal_carbs_g REAL, goal_fat_g     REAL
            );
            -- Ingredient library (local cache of validated nutrition data)
            CREATE TABLE IF NOT EXISTS ingredient_library (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                search_key TEXT NOT NULL,
                brand      TEXT DEFAULT '',
                barcode    TEXT DEFAULT '',
{nutr_lib}
                _placeholder INTEGER,
                used_count INTEGER NOT NULL DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_lib_search ON ingredient_library(search_key);
        """)
    _run_migrations()


def _run_migrations() -> None:
    """Safely add any missing columns to existing databases."""
    with get_connection() as conn:
        ing_cols = {row[1] for row in conn.execute("PRAGMA table_info(ingredients)")}
        log_cols = {row[1] for row in conn.execute("PRAGMA table_info(food_log)")}
        lib_cols = {row[1] for row in conn.execute("PRAGMA table_info(ingredient_library)")}

        for field in NUTRIENT_FIELDS:
            if field not in ing_cols:
                conn.execute(f"ALTER TABLE ingredients ADD COLUMN {field} REAL")
            if field not in log_cols:
                conn.execute(f"ALTER TABLE food_log ADD COLUMN {field} REAL")
            lib_col = field + "_100g"
            if lib_col not in lib_cols:
                conn.execute(f"ALTER TABLE ingredient_library ADD COLUMN {lib_col} REAL")