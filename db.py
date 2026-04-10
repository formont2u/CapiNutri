"""
db.py — Database connection and schema manager.
Strictly handles SQLite connection and table structures.
"""
import sqlite3
from pathlib import Path
from constants import NUTRIENT_FIELDS

DB_PATH = Path(__file__).parent / "recipes.db"

def get_connection() -> sqlite3.Connection:
    """Returns a connected SQLite database instance with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _nutr_cols(prefix="", suffix=""):
    """Generates SQL string for all nutrient columns."""
    return "\n".join(f"    {prefix}{f}{suffix}  REAL," for f in NUTRIENT_FIELDS)

def init_db() -> None:
    """Initializes all database tables."""
    nutr_ing = _nutr_cols()
    nutr_log = _nutr_cols()
    nutr_lib = _nutr_cols(suffix="_100g")

    with get_connection() as conn:
        conn.executescript(f"""
            -- 0. Table des utilisateurs
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

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
            CREATE TABLE IF NOT EXISTS tags (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#888888',
                icon  TEXT DEFAULT 'bi-tag'
            );
            CREATE TABLE IF NOT EXISTS recipe_tags (
                recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                tag_id    INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (recipe_id, tag_id)
            );
            CREATE TABLE IF NOT EXISTS ingredients (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                name      TEXT NOT NULL,
                quantity  REAL NOT NULL,
                unit      TEXT NOT NULL DEFAULT '',
                library_id INTEGER REFERENCES ingredient_library(id) ON DELETE SET NULL,
{nutr_ing}
                _placeholder INTEGER
            );
            CREATE TABLE IF NOT EXISTS pantry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                name TEXT NOT NULL,
                quantity REAL, 
                unit TEXT NOT NULL DEFAULT '',
                UNIQUE(user_id, name)
            );
            CREATE TABLE IF NOT EXISTS user_profile (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER UNIQUE REFERENCES users(id),
                name           TEXT,
                weight_kg      REAL, height_cm REAL, age INTEGER,
                sex            TEXT,
                activity_level TEXT DEFAULT 'moderate',
                goal           TEXT DEFAULT 'maintain',
                meals_per_day  INTEGER DEFAULT 3,
                current_bf_pct REAL,
                goal_weight_kg REAL,
                goal_bf_pct    REAL,
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS food_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER REFERENCES users(id),
                log_date   DATE NOT NULL,
                meal_type  TEXT DEFAULT 'other',
                recipe_id  INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
                label      TEXT NOT NULL,
                servings   REAL NOT NULL DEFAULT 1,
{nutr_log}
                _placeholder INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS body_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date_str TEXT NOT NULL,
                weight_kg REAL,
                bf_pct REAL,
                UNIQUE(user_id, date_str),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS exercise_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER REFERENCES users(id),
                log_date     DATE NOT NULL,
                name         TEXT NOT NULL,
                kcal_burned  REAL NOT NULL DEFAULT 0,
                duration_min INTEGER,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS daily_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                goal_date TEXT,
                goal_kcal REAL,
                goal_protein_g REAL,
                goal_carbs_g REAL,
                goal_fat_g REAL
            );
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

            CREATE TABLE IF NOT EXISTS ingredient_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER NOT NULL REFERENCES ingredient_library(id) ON DELETE CASCADE,
                unit_name TEXT NOT NULL,
                unit_key TEXT NOT NULL,
                grams_equivalent REAL,
                ml_equivalent REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(library_id, unit_key)
            );

            CREATE TABLE IF NOT EXISTS meal_plan (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER REFERENCES users(id),
                plan_date  DATE    NOT NULL,
                meal_type  TEXT    NOT NULL,
                recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                is_logged  INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, plan_date, meal_type)
            );
            CREATE INDEX IF NOT EXISTS idx_plan_date ON meal_plan(plan_date);
        """)
    _run_migrations()

def _run_migrations() -> None:
    """Safely add any missing columns and fix the user_id migration."""
    with get_connection() as conn:
        # Migration user_id pour les tables existantes
        tables_to_update = [
            "user_profile", "pantry", "meal_plan", 
            "food_log", "exercise_log", "daily_goals"
        ]
        for table in tables_to_update:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà

        # Colonnes extras pour user_profile
        up_cols = {row[1] for row in conn.execute(f"PRAGMA table_info(user_profile)")}
        for col in ["meals_per_day", "current_bf_pct", "goal_weight_kg", "goal_bf_pct"]:
             if col not in up_cols:
                conn.execute(f"ALTER TABLE user_profile ADD COLUMN {col} REAL")

        # Vérification nutriments
        ing_cols = {row[1] for row in conn.execute("PRAGMA table_info(ingredients)")}
        log_cols = {row[1] for row in conn.execute("PRAGMA table_info(food_log)")}
        lib_cols = {row[1] for row in conn.execute("PRAGMA table_info(ingredient_library)")}
        unit_cols = {row[1] for row in conn.execute("PRAGMA table_info(ingredient_units)")}

        if "library_id" not in ing_cols:
            conn.execute("ALTER TABLE ingredients ADD COLUMN library_id INTEGER REFERENCES ingredient_library(id) ON DELETE SET NULL")

        for field in NUTRIENT_FIELDS:
            if field not in ing_cols:
                conn.execute(f"ALTER TABLE ingredients ADD COLUMN {field} REAL")
            if field not in log_cols:
                conn.execute(f"ALTER TABLE food_log ADD COLUMN {field} REAL")
            lib_col = field + "_100g"
            if lib_col not in lib_cols:
                conn.execute(f"ALTER TABLE ingredient_library ADD COLUMN {lib_col} REAL")
        # (Dans db.py, à la fin de la fonction _run_migrations)
        
        # --- Migration pour le Cerveau Sportif (RPE & Type) ---
        ex_cols = {row[1] for row in conn.execute("PRAGMA table_info(exercise_log)")}
        if "rpe" not in ex_cols:
            conn.execute("ALTER TABLE exercise_log ADD COLUMN rpe INTEGER DEFAULT 5")
        if "exercise_type" not in ex_cols:
            conn.execute("ALTER TABLE exercise_log ADD COLUMN exercise_type TEXT DEFAULT 'cardio'")

        for col in ["unit_name", "unit_key", "grams_equivalent", "ml_equivalent"]:
            if unit_cols and col not in unit_cols:
                column_type = "TEXT" if "unit" in col and "equivalent" not in col else "REAL"
                conn.execute(f"ALTER TABLE ingredient_units ADD COLUMN {col} {column_type}")
