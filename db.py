"""
db.py — Database connection and schema initialization.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "recipes.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            -- ── Module 1: Core ───────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS categories (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS recipes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                servings     REAL    NOT NULL DEFAULT 1,
                instructions TEXT,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ingredients (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id        INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                name             TEXT    NOT NULL,
                quantity         REAL    NOT NULL,
                unit             TEXT    NOT NULL DEFAULT '',
                -- Macros
                kcal             REAL, protein_g   REAL, carbs_g      REAL, fat_g        REAL,
                -- Carb detail
                sugars_g         REAL, fiber_g      REAL,
                -- Fat detail
                saturated_g      REAL, monounsat_g  REAL, polyunsat_g  REAL,
                -- Micronutrients
                sodium_mg        REAL, calcium_mg   REAL, iron_mg      REAL,
                potassium_mg     REAL, magnesium_mg REAL, zinc_mg      REAL,
                -- Vitamins
                vit_a_mcg        REAL, vit_c_mg     REAL, vit_d_mcg   REAL,
                vit_b1_mg        REAL, vit_b2_mg    REAL, vit_b3_mg   REAL,
                vit_b6_mg        REAL, vit_b9_mcg   REAL, vit_b12_mcg REAL
            );
            -- ── Module 6: Pantry stub ─────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS pantry (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT NOT NULL UNIQUE,
                quantity REAL, unit TEXT NOT NULL DEFAULT ''
            );
            -- ── Module 2+: Nutrition tracking ────────────────────────────────
            CREATE TABLE IF NOT EXISTS user_profile (
                id             INTEGER PRIMARY KEY DEFAULT 1,
                name           TEXT,
                weight_kg      REAL, height_cm    REAL, age         INTEGER,
                sex            TEXT,   -- 'M' or 'F'
                activity_level TEXT DEFAULT 'moderate',
                goal           TEXT DEFAULT 'maintain',  -- maintain / cut / bulk
                -- Manual overrides (NULL = use calculated)
                goal_kcal      REAL, goal_protein_g REAL,
                goal_carbs_g   REAL, goal_fat_g     REAL,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS food_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date     DATE      NOT NULL,
                meal_type    TEXT      DEFAULT 'other',
                recipe_id    INTEGER   REFERENCES recipes(id) ON DELETE SET NULL,
                label        TEXT      NOT NULL,   -- recipe name or custom ingredient
                servings     REAL      NOT NULL DEFAULT 1,
                -- Cached nutrition snapshot (so edits to recipes don't alter history)
                kcal         REAL, protein_g   REAL, carbs_g      REAL, fat_g        REAL,
                sugars_g     REAL, fiber_g      REAL,
                saturated_g  REAL, monounsat_g  REAL, polyunsat_g  REAL,
                sodium_mg    REAL, calcium_mg   REAL, iron_mg      REAL,
                potassium_mg REAL, magnesium_mg REAL, zinc_mg      REAL,
                vit_a_mcg    REAL, vit_c_mg     REAL, vit_d_mcg   REAL,
                vit_b1_mg    REAL, vit_b2_mg    REAL, vit_b3_mg   REAL,
                vit_b6_mg    REAL, vit_b9_mcg   REAL, vit_b12_mcg REAL,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS exercise_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date     DATE    NOT NULL,
                name         TEXT    NOT NULL,
                kcal_burned  REAL    NOT NULL DEFAULT 0,
                duration_min INTEGER,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS daily_goals (
                log_date      DATE PRIMARY KEY,
                goal_kcal     REAL, goal_protein_g REAL,
                goal_carbs_g  REAL, goal_fat_g     REAL
            );
        """)
    _run_migrations()


# Nutrition field names in order (used everywhere for consistency)
NUTRIENT_FIELDS = [
    "kcal", "protein_g", "carbs_g", "fat_g",
    "sugars_g", "fiber_g",
    "saturated_g", "monounsat_g", "polyunsat_g",
    "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "magnesium_mg", "zinc_mg",
    "vit_a_mcg", "vit_c_mg", "vit_d_mcg",
    "vit_b1_mg", "vit_b2_mg", "vit_b3_mg", "vit_b6_mg", "vit_b9_mcg", "vit_b12_mcg",
]

MACRO_FIELDS    = ["kcal", "protein_g", "carbs_g", "fat_g"]
CARB_FIELDS     = ["sugars_g", "fiber_g"]
FAT_FIELDS      = ["saturated_g", "monounsat_g", "polyunsat_g"]
MICRO_FIELDS    = ["sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "magnesium_mg", "zinc_mg"]
VITAMIN_FIELDS  = ["vit_a_mcg", "vit_c_mg", "vit_d_mcg", "vit_b1_mg", "vit_b2_mg",
                   "vit_b3_mg", "vit_b6_mg", "vit_b9_mcg", "vit_b12_mcg"]

# Human-readable labels
NUTRIENT_LABELS = {
    "kcal": ("Calories", "kcal"),
    "protein_g": ("Protéines", "g"), "carbs_g": ("Glucides", "g"), "fat_g": ("Lipides", "g"),
    "sugars_g": ("Sucres", "g"), "fiber_g": ("Fibres", "g"),
    "saturated_g": ("Saturés", "g"), "monounsat_g": ("Mono-insaturés", "g"), "polyunsat_g": ("Poly-insaturés", "g"),
    "sodium_mg": ("Sodium", "mg"), "calcium_mg": ("Calcium", "mg"), "iron_mg": ("Fer", "mg"),
    "potassium_mg": ("Potassium", "mg"), "magnesium_mg": ("Magnésium", "mg"), "zinc_mg": ("Zinc", "mg"),
    "vit_a_mcg": ("Vit. A", "µg"), "vit_c_mg": ("Vit. C", "mg"), "vit_d_mcg": ("Vit. D", "µg"),
    "vit_b1_mg": ("Vit. B1", "mg"), "vit_b2_mg": ("Vit. B2", "mg"), "vit_b3_mg": ("Vit. B3", "mg"),
    "vit_b6_mg": ("Vit. B6", "mg"), "vit_b9_mcg": ("Vit. B9 (Folate)", "µg"), "vit_b12_mcg": ("Vit. B12", "µg"),
}

# Reference Daily Intakes (used for % progress bars)
RDI = {
    "kcal": 2000, "protein_g": 50, "carbs_g": 260, "fat_g": 70,
    "sugars_g": 50, "fiber_g": 30,
    "saturated_g": 20, "sodium_mg": 2300, "calcium_mg": 1000,
    "iron_mg": 14, "potassium_mg": 3500, "magnesium_mg": 375, "zinc_mg": 11,
    "vit_a_mcg": 800, "vit_c_mg": 80, "vit_d_mcg": 15,
    "vit_b1_mg": 1.1, "vit_b2_mg": 1.4, "vit_b3_mg": 16,
    "vit_b6_mg": 1.4, "vit_b9_mcg": 200, "vit_b12_mcg": 2.4,
}


def _run_migrations() -> None:
    """Safely add new columns to existing databases."""
    with get_connection() as conn:
        existing_ing = {row[1] for row in conn.execute("PRAGMA table_info(ingredients)")}
        existing_log = {row[1] for row in conn.execute("PRAGMA table_info(food_log)")}
        for field in NUTRIENT_FIELDS:
            unit = field.split("_")[-1]
            col_type = "REAL"
            if field not in existing_ing:
                conn.execute(f"ALTER TABLE ingredients ADD COLUMN {field} {col_type}")
            if field not in existing_log and field in [
                "kcal","protein_g","carbs_g","fat_g","sugars_g","fiber_g",
                "saturated_g","monounsat_g","polyunsat_g","sodium_mg","calcium_mg",
                "iron_mg","potassium_mg","magnesium_mg","zinc_mg",
                "vit_a_mcg","vit_c_mg","vit_d_mcg","vit_b1_mg","vit_b2_mg",
                "vit_b3_mg","vit_b6_mg","vit_b9_mcg","vit_b12_mcg"
            ]:
                conn.execute(f"ALTER TABLE food_log ADD COLUMN {field} {col_type}")
