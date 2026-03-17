"""
crud.py — Opérations de base de données.
Couche d'accès aux données (Data Access Layer). Strictement réservé au SQL et à l'instanciation des objets.
"""
from typing import Optional
import unicodedata
import re

from db import get_connection
from models import Recipe, Ingredient, UserProfile, FoodLogEntry, ExerciseEntry, User, BodyTrackingEntry
from constants import NUTRIENT_FIELDS, MEAL_TYPES

from utils import normalize_string

def _norm(name: str) -> str:
    """Normalise un nom d'ingrédient pour faciliter les comparaisons (ASCII, lowercase)."""
    if not name:
        return ""
    s = name.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()

# ── 1. Authentification & Sécurité ────────────────────────────────────────────

def get_user_by_username(username: str) -> Optional[User]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return User(id=row["id"], username=row["username"], password_hash=row["password_hash"]) if row else None

def get_user_by_id(user_id: int) -> Optional[User]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User(id=row["id"], username=row["username"], password_hash=row["password_hash"]) if row else None

def create_user(username: str, password_hash: str) -> int:
    with get_connection() as conn:
        return conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash)).lastrowid

# ── 2. User Profile ───────────────────────────────────────────────────────────

def get_profile(user_id: int) -> UserProfile:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return UserProfile()
        
        # Mapping SQL vers Dataclass dynamique
        d = dict(row)
        valid_kwargs = {k: v for k, v in d.items() if hasattr(UserProfile, k)}
        return UserProfile(**valid_kwargs)

def save_profile(p: UserProfile, user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM user_profile WHERE user_id=?", (user_id,))
        conn.execute("""
            INSERT INTO user_profile (
                user_id, name, weight_kg, height_cm, age, sex, 
                activity_level, goal, meals_per_day,
                current_bf_pct, goal_weight_kg, goal_bf_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, p.name, p.weight_kg, p.height_cm, p.age, p.sex,
            p.activity_level, p.goal, p.meals_per_day,
            p.current_bf_pct, p.goal_weight_kg, p.goal_bf_pct
        ))

# ── 3. Categories & Tags ──────────────────────────────────────────────────────

def get_or_create_category(name: str) -> int:
    name = name.strip().title()
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
        return row["id"] if row else conn.execute("INSERT INTO categories (name) VALUES (?)", (name,)).lastrowid

def list_categories() -> list[str]:
    with get_connection() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM categories ORDER BY name")]

def delete_category(name: str) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM categories WHERE name=?", (name.title(),)).rowcount > 0

def list_tags() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT id, name, color, icon FROM tags ORDER BY name")]

# ── 4. Recipes & Ingredients ──────────────────────────────────────────────────

def add_recipe(recipe: Recipe) -> int:
    category_id = get_or_create_category(recipe.category) if recipe.category else None
    with get_connection() as conn:
        rid = conn.execute(
            "INSERT INTO recipes (name, category_id, servings, instructions) VALUES (?,?,?,?)",
            (recipe.name.strip(), category_id, recipe.servings, recipe.instructions.strip()),
        ).lastrowid
        _insert_ingredients(conn, rid, recipe.ingredients)
        _set_recipe_tags(conn, rid, recipe.tags)
    return rid

def update_recipe(recipe: Recipe) -> bool:
    if recipe.id is None: return False
    category_id = get_or_create_category(recipe.category) if recipe.category else None
    with get_connection() as conn:
        conn.execute(
            "UPDATE recipes SET name=?,category_id=?,servings=?,instructions=? WHERE id=?",
            (recipe.name.strip(), category_id, recipe.servings, recipe.instructions.strip(), recipe.id),
        )
        conn.execute("DELETE FROM ingredients WHERE recipe_id=?", (recipe.id,))
        _insert_ingredients(conn, recipe.id, recipe.ingredients)
        _set_recipe_tags(conn, recipe.id, recipe.tags)
    return True

def delete_recipe(recipe_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM recipes WHERE id=?", (recipe_id,)).rowcount > 0

def get_recipe(recipe_id: int) -> Optional[Recipe]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT r.id, r.name, r.servings, r.instructions, c.name AS category, r.category_id
               FROM recipes r LEFT JOIN categories c ON c.id=r.category_id WHERE r.id=?""",
            (recipe_id,)
        ).fetchone()
        if not row: return None
        
        tags = [r["name"] for r in conn.execute(
            "SELECT t.name FROM tags t JOIN recipe_tags rt ON rt.tag_id=t.id WHERE rt.recipe_id=? ORDER BY t.name", 
            (recipe_id,)
        )]
        
        return Recipe(
            id=row["id"], name=row["name"], servings=row["servings"],
            instructions=row["instructions"] or "", category=row["category"],
            category_id=row["category_id"], tags=tags,
            ingredients=_fetch_ingredients(conn, recipe_id),
        )

def list_recipes(category: Optional[str] = None, search: Optional[str] = None, tag: Optional[str] = None) -> list[dict]:
    query = """
        SELECT r.id, r.name, r.servings, c.name AS category,
               ROUND(SUM(i.kcal),0)        AS total_kcal,
               ROUND(SUM(i.protein_g),1)   AS total_protein,
               ROUND(SUM(i.sugars_g),1)    AS total_sugars,
               ROUND(SUM(i.fiber_g),1)     AS total_fiber,
               ROUND(SUM(i.saturated_g),1) AS total_saturated,
               ROUND(SUM(i.sodium_mg),1)   AS total_sodium
        FROM recipes r
        LEFT JOIN categories c ON c.id=r.category_id
        LEFT JOIN ingredients i ON i.recipe_id=r.id
        WHERE 1=1
    """
    params = []
    if category:
        query += " AND c.name=?"; params.append(category.title())
    if search:
        query += " AND r.name LIKE ?"; params.append(f"%{search}%")
    if tag:
        query += """ AND r.id IN (
            SELECT rt.recipe_id FROM recipe_tags rt
            JOIN tags t ON t.id=rt.tag_id WHERE t.name=?)"""
        params.append(tag)
        
    query += " GROUP BY r.id ORDER BY r.name"
    
    with get_connection() as conn:
        rows = [dict(r) for r in conn.execute(query, params)]
        for r in rows:
            r["tags"] = [t["name"] for t in conn.execute(
                "SELECT t.name FROM tags t JOIN recipe_tags rt ON rt.tag_id=t.id WHERE rt.recipe_id=? ORDER BY t.name", 
                (r["id"],)
            )]
        return rows

def _set_recipe_tags(conn, recipe_id: int, tag_names: list[str]) -> None:
    conn.execute("DELETE FROM recipe_tags WHERE recipe_id=?", (recipe_id,))
    for name in tag_names:
        row = conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
        if row:
            conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)", (recipe_id, row["id"]))

def _insert_ingredients(conn, recipe_id: int, ingredients: list[Ingredient]) -> None:
    fields = ["recipe_id","name","quantity","unit"] + NUTRIENT_FIELDS
    placeholders = ",".join(["?"] * len(fields))
    cols = ",".join(fields)
    rows = []
    for i in ingredients:
        row = [recipe_id, i.name.strip(), i.quantity, i.unit.strip()]
        row += [getattr(i, f, None) for f in NUTRIENT_FIELDS]
        rows.append(row)
    conn.executemany(f"INSERT INTO ingredients ({cols}) VALUES ({placeholders})", rows)

def _fetch_ingredients(conn, recipe_id: int) -> list[Ingredient]:
    fields = ["id","name","quantity","unit"] + NUTRIENT_FIELDS
    rows = conn.execute(f"SELECT {','.join(fields)} FROM ingredients WHERE recipe_id=? ORDER BY id", (recipe_id,)).fetchall()
    
    return [
        Ingredient(
            id=r["id"], recipe_id=recipe_id,
            name=r["name"], quantity=r["quantity"], unit=r["unit"],
            **{f: r[f] for f in NUTRIENT_FIELDS}
        ) for r in rows
    ]

# ── 5. Food Log ───────────────────────────────────────────────────────────────

def create_food_log(user_id: int, label: str, servings: float, kcal: float, meal_type: str, date_str: str, 
                 protein_g=0, carbs_g=0, fat_g=0, sugars_g=0, fiber_g=0, saturated_g=0, sodium_mg=0, recipe_id=None) -> int:
    with get_connection() as conn:
        return conn.execute("""
            INSERT INTO food_log (
                user_id, label, servings, kcal, meal_type, log_date, recipe_id,
                protein_g, carbs_g, fat_g, sugars_g, fiber_g, saturated_g, sodium_mg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, label, servings, kcal, meal_type, date_str, recipe_id,
            protein_g, carbs_g, fat_g, sugars_g, fiber_g, saturated_g, sodium_mg
        )).lastrowid

def get_food_log_day(user_id: int, date_str: str) -> list[FoodLogEntry]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM food_log WHERE user_id = ? AND log_date = ? ORDER BY id ASC", (user_id, date_str)).fetchall()
        entries = []
        for r in rows:
            d = dict(r)
            # Instanciation dynamique propre
            valid_kwargs = {k: v for k, v in d.items() if hasattr(FoodLogEntry, k)}
            entries.append(FoodLogEntry(**valid_kwargs))
        return entries

def delete_food_log(user_id: int, entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM food_log WHERE id = ? AND user_id = ?", (entry_id, user_id)).rowcount > 0
    
def get_food_log_entry(user_id: int, entry_id: int) -> Optional[FoodLogEntry]:
    """Récupère une entrée spécifique du journal pour un utilisateur."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM food_log WHERE id = ? AND user_id = ?", (entry_id, user_id)).fetchone()
        if not row:
            return None
        valid_kwargs = {k: v for k, v in dict(row).items() if hasattr(FoodLogEntry, k)}
        return FoodLogEntry(**valid_kwargs)

# ── 6. Exercise Log ───────────────────────────────────────────────────────────

def add_exercise(user_id: int, entry: ExerciseEntry) -> None:
    """Ajoute un exercice au journal."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO exercise_log (user_id, log_date, name, kcal_burned, duration_min, rpe, exercise_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, entry.log_date, entry.name, entry.kcal_burned, entry.duration_min, entry.rpe, entry.exercise_type))

def get_exercise_day(user_id: int, date_str: str) -> list[ExerciseEntry]:
    """Récupère les exercices d'une journée."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM exercise_log WHERE user_id = ? AND log_date = ?", (user_id, date_str)).fetchall()
        return [ExerciseEntry(
            id=r["id"],
            log_date=r["log_date"],
            name=r["name"],
            kcal_burned=r["kcal_burned"],
            duration_min=r["duration_min"],
            rpe=r["rpe"],                      # NOUVEAU
            exercise_type=r["exercise_type"]   # NOUVEAU
        ) for r in rows]

def delete_exercise(user_id: int, entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM exercise_log WHERE id=? AND user_id=?", (entry_id, user_id)).rowcount > 0

# ── 7. Daily Goals & Summaries ────────────────────────────────────────────────

def get_daily_goal(user_id: int, date_str: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?", (user_id, date_str)).fetchone()
        return dict(row) if row else None

def set_daily_goal(user_id: int, date_str: str, kcal: float, protein: float, carbs: float, fat: float) -> int:
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM daily_goals WHERE user_id=? AND goal_date=?", (user_id, date_str)).fetchone()
        if existing:
            conn.execute("UPDATE daily_goals SET goal_kcal=?, goal_protein_g=?, goal_carbs_g=?, goal_fat_g=? WHERE id=?",
                         (kcal, protein, carbs, fat, existing["id"]))
            return existing["id"]
        return conn.execute(
            "INSERT INTO daily_goals (user_id, goal_date, goal_kcal, goal_protein_g, goal_carbs_g, goal_fat_g) VALUES (?,?,?,?,?,?)",
            (user_id, date_str, kcal, protein, carbs, fat)
        ).lastrowid

def delete_daily_goal(user_id: int, date_str: str) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM daily_goals WHERE user_id=? AND goal_date=?", (user_id, date_str)).rowcount > 0

# ── 8. Ingredient Library ─────────────────────────────────────────────────────

def list_library(search: str = "") -> list[dict]:
    sql = """SELECT id, name, brand, barcode, used_count, updated_at,
             kcal_100g, protein_g_100g, carbs_g_100g, fat_g_100g
             FROM ingredient_library WHERE 1=1"""
    params = []
    if search:
        sql += " AND (name LIKE ? OR brand LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY used_count DESC, name"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params)]

def get_library_entry(entry_id: int) -> Optional[dict]:
    cols = ["id", "name", "search_key", "brand", "barcode", "used_count"] + [f + "_100g" for f in NUTRIENT_FIELDS]
    with get_connection() as conn:
        row = conn.execute(f"SELECT {', '.join(cols)} FROM ingredient_library WHERE id=?", (entry_id,)).fetchone()
        return dict(row) if row else None

def update_library_entry(entry_id: int, name: str, brand: str, barcode: str, per_100g: dict) -> bool:
    nutr_vals = {f + "_100g": per_100g.get(f) for f in NUTRIENT_FIELDS}
    set_clause = ", ".join(f"{k} = ?" for k in nutr_vals)
    with get_connection() as conn:
        return conn.execute(
            f"UPDATE ingredient_library SET name=?, search_key=?, brand=?, barcode=?, {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [name, _norm(name), brand, barcode, *nutr_vals.values(), entry_id]
        ).rowcount > 0

def delete_library_entry(entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM ingredient_library WHERE id=?", (entry_id,)).rowcount > 0

def search_ingredient_library(query: str, limit: int = 5) -> list[dict]:
    """Recherche intelligente dans la librairie locale avec tri par pertinence."""
    key = _norm(query)
    if not key:
        return []
    sql = """SELECT * FROM ingredient_library 
             WHERE search_key LIKE ?
             ORDER BY
                 CASE WHEN search_key = ?    THEN 0
                      WHEN search_key LIKE ? THEN 1
                      ELSE 2 END,
                 used_count DESC LIMIT ?"""
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, (f"%{key}%", key, f"{key}%", limit)).fetchall()]

def get_library_entry_by_barcode(barcode: str) -> Optional[dict]:
    """Cherche un ingrédient localement via son code-barres."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ingredient_library WHERE barcode = ?", (barcode,)).fetchone()
        return dict(row) if row else None

def save_ingredient_to_library(name: str, brand: str, barcode: str, per_100g: dict) -> int:
    """Insère ou met à jour un ingrédient dans le cache local (Library)."""
    key = _norm(name)
    nutr_vals = {f + "_100g": per_100g.get(f) for f in NUTRIENT_FIELDS}
    with get_connection() as conn:
        existing = conn.execute("SELECT id, used_count FROM ingredient_library WHERE search_key = ?", (key,)).fetchone()
        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in nutr_vals)
            conn.execute(
                f"UPDATE ingredient_library SET {set_clause}, brand=?, barcode=?, used_count=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [*nutr_vals.values(), brand, barcode, existing["used_count"] + 1, existing["id"]]
            )
            return existing["id"]
        
        cols = ["name", "search_key", "brand", "barcode"] + list(nutr_vals.keys())
        vals = [name, key, brand, barcode] + list(nutr_vals.values())
        return conn.execute(
            f"INSERT INTO ingredient_library ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})", vals
        ).lastrowid

def increment_library_usage(library_id: int) -> None:
    """Incrémente le compteur d'utilisation d'un ingrédient local."""
    with get_connection() as conn:
        conn.execute("UPDATE ingredient_library SET used_count = used_count + 1 WHERE id = ?", (library_id,))

# ── 9. Meal Plan & Dashboards ─────────────────────────────────────────────────

def get_plan(user_id: int, date_str: str) -> dict:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT mp.meal_type, mp.id AS plan_id, mp.is_logged, r.id AS recipe_id, r.name AS recipe_name, r.servings, ROUND(SUM(i.kcal), 0) AS total_kcal
            FROM meal_plan mp JOIN recipes r ON r.id = mp.recipe_id LEFT JOIN ingredients i ON i.recipe_id = r.id
            WHERE mp.user_id = ? AND mp.plan_date = ? GROUP BY mp.id
        """, (user_id, date_str)).fetchall()
    plan = {t: None for t in MEAL_TYPES}
    for r in rows:
        plan[r["meal_type"]] = dict(r)
    return plan

def set_plan_slot(user_id: int, date_str: str, meal_type: str, recipe_id: int) -> int:
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM meal_plan WHERE user_id=? AND plan_date=? AND meal_type=?", (user_id, date_str, meal_type)).fetchone()
        if existing:
            conn.execute("UPDATE meal_plan SET recipe_id=?, is_logged=0 WHERE id=? AND user_id=?", (recipe_id, existing["id"], user_id))
            return existing["id"]
        return conn.execute("INSERT INTO meal_plan (user_id, plan_date, meal_type, recipe_id) VALUES (?,?,?,?)", (user_id, date_str, meal_type, recipe_id)).lastrowid

def clear_plan_slot(user_id: int, plan_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM meal_plan WHERE id=? AND user_id=?", (plan_id, user_id)).rowcount > 0

def mark_plan_logged(user_id: int, plan_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE meal_plan SET is_logged=1 WHERE id=? AND user_id=?", (plan_id, user_id))

def get_week_dashboard(user_id: int, start_date: str) -> dict:
    from datetime import datetime, timedelta
    with get_connection() as conn:
        # 1. On récupère les repas loggés
        food_rows = conn.execute("""
            SELECT log_date AS plan_date, meal_type, id AS plan_id, 1 AS is_logged, recipe_id, label AS recipe_name, servings,
                   kcal AS total_kcal, protein_g AS total_protein_g, carbs_g AS total_carbs_g, fat_g AS total_fat_g, fiber_g AS total_fiber_g, 0 AS total_iron_mg
            FROM food_log 
            WHERE user_id = ? AND log_date >= ? AND log_date < date(?, '+7 days')
        """, (user_id, start_date, start_date)).fetchall()

        # 2. NOUVEAU : On récupère les exercices loggés
        ex_rows = conn.execute("""
            SELECT log_date, SUM(kcal_burned) as total_burned
            FROM exercise_log
            WHERE user_id = ? AND log_date >= ? AND log_date < date(?, '+7 days')
            GROUP BY log_date
        """, (user_id, start_date, start_date)).fetchall()

    # Initialisation de la structure de la semaine
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    week_plan = {}
    for i in range(7):
        d_str = (start + timedelta(days=i)).isoformat()
        week_plan[d_str] = {
            "meals": {t: None for t in MEAL_TYPES},
            # Ajout de "burned": 0.0 ici pour éviter l'UndefinedError dans Jinja
            "daily_totals": {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "iron_mg": 0.0, "burned": 0.0}
        }

    # Remplissage avec les données de nourriture
    for r in food_rows:
        d_str = r["plan_date"]
        if d_str in week_plan:
            meal = dict(r)
            week_plan[d_str]["meals"][meal["meal_type"]] = meal
            for k in ["kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "iron_mg"]:
                if meal.get(f"total_{k}"): 
                    week_plan[d_str]["daily_totals"][k] += meal[f"total_{k}"]

    # NOUVEAU : Remplissage avec les données d'exercice
    for r in ex_rows:
        d_str = r["log_date"]
        if d_str in week_plan:
            week_plan[d_str]["daily_totals"]["burned"] = float(r["total_burned"] or 0.0)

    return week_plan

def get_week_shopping_list(user_id: int, start_date: str) -> dict:
    """
    Génère la liste de courses de la semaine en additionnant les ingrédients
    de tous les repas planifiés.
    """
    with get_connection() as conn:
        # 1. Récupérer tous les repas planifiés sur les 7 prochains jours
        meals = conn.execute("""
            SELECT mp.plan_date, mp.meal_type, r.id AS recipe_id, r.name AS recipe_name
            FROM meal_plan mp
            JOIN recipes r ON r.id = mp.recipe_id
            WHERE mp.user_id = ? AND mp.plan_date >= ? AND mp.plan_date < date(?, '+7 days')
            ORDER BY mp.plan_date ASC
        """, (user_id, start_date, start_date)).fetchall()

        days_list = [dict(m) for m in meals]

        # 2. Agréger les ingrédients
        items_dict = {}
        if meals:
            # Récupérer les IDs uniques des recettes de la semaine
            recipe_ids = list(set([m["recipe_id"] for m in meals]))
            placeholders = ",".join("?" for _ in recipe_ids)
            
            # Fetch tous les ingrédients de ces recettes d'un coup
            ings_rows = conn.execute(f"""
                SELECT recipe_id, name, quantity, unit 
                FROM ingredients 
                WHERE recipe_id IN ({placeholders})
            """, tuple(recipe_ids)).fetchall()
            
            # Grouper par recette pour un accès rapide
            ings_by_recipe = {}
            for row in ings_rows:
                rid = row["recipe_id"]
                if rid not in ings_by_recipe:
                    ings_by_recipe[rid] = []
                ings_by_recipe[rid].append(dict(row))

            # Construire la liste de courses
            for meal in meals:
                rid = meal["recipe_id"]
                for ing in ings_by_recipe.get(rid, []):
                    raw_name = ing["name"].strip()
                    norm_key = _norm(raw_name) # On utilise ta fonction de normalisation existante
                    qty = float(ing["quantity"] or 0)
                    unit = (ing["unit"] or "").strip().lower()

                    if norm_key not in items_dict:
                        items_dict[norm_key] = {
                            "name": raw_name, # Le nom original pour l'affichage
                            "total_by_unit": {},
                            "entries": [] # Pour savoir de quelle recette ça vient
                        }
                    
                    if unit not in items_dict[norm_key]["total_by_unit"]:
                        items_dict[norm_key]["total_by_unit"][unit] = 0.0
                    items_dict[norm_key]["total_by_unit"][unit] += qty
                    
                    items_dict[norm_key]["entries"].append({
                        "recipe": meal["recipe_name"],
                        "qty": qty,
                        "unit": unit
                    })

    return {
        "start_date": start_date,
        "days": days_list,
        "items": list(items_dict.values())
    }

# ── 10. Pantry (Garde-manger) ─────────────────────────────────────────────────

def list_pantry(user_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT id, name, quantity, unit FROM pantry WHERE user_id=? ORDER BY name", (user_id,))]

def add_pantry_item(user_id: int, name: str, quantity: Optional[float], unit: str) -> int:
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM pantry WHERE name=? AND user_id=?", (name.strip(), user_id)).fetchone()
        if existing:
            conn.execute("UPDATE pantry SET quantity=?, unit=? WHERE id=?", (quantity, unit.strip(), existing["id"]))
            return existing["id"]
        return conn.execute("INSERT INTO pantry (user_id, name, quantity, unit) VALUES (?,?,?,?)", (user_id, name.strip(), quantity, unit.strip())).lastrowid

def update_pantry_item(user_id: int, item_id: int, name: str, quantity: Optional[float], unit: str) -> bool:
    with get_connection() as conn:
        return conn.execute("UPDATE pantry SET name=?, quantity=?, unit=? WHERE id=? AND user_id=?", (name.strip(), quantity, unit.strip(), item_id, user_id)).rowcount > 0

def delete_pantry_item(user_id: int, item_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM pantry WHERE id=? AND user_id=?", (item_id, user_id)).rowcount > 0
    
def get_cookable_recipes(user_id: int) -> list[dict]:
    """
    Compare le stock du garde-manger avec les ingrédients des recettes.
    Retourne une liste enrichie pour l'affichage des suggestions (pantry.html).
    """
    # 1. Récupération et normalisation du stock de l'utilisateur
    pantry_items = list_pantry(user_id) 
    stock = {}
    for item in pantry_items:
        norm_name = normalize_string(item["name"])
        # On sécurise la conversion en float au cas où la base renvoie None
        stock[norm_name] = stock.get(norm_name, 0) + float(item["quantity"] or 0)

    # 2. Récupérer TOUTES les recettes via ta fonction existante
    all_recipes_summary = list_recipes()
    results = []
    
    for r_summary in all_recipes_summary:
        # On utilise ta fonction get_recipe pour récupérer les objets Ingrédients attachés
        recipe = get_recipe(r_summary["id"])
        if not recipe:
            continue
            
        missing = []
        
        # On vérifie chaque ingrédient de la recette
        for ing in recipe.ingredients:
            norm_ing_name = normalize_string(ing.name)
            req_qty = float(ing.quantity or 0)
            
            # Vérification du stock
            if norm_ing_name not in stock:
                missing.append(ing.name)
            elif stock[norm_ing_name] < req_qty:
                missing.append(ing.name)
                
        # Calcul des calories pour l'affichage dans le badge
        total_kcal = sum([i.kcal or 0 for i in recipe.ingredients if i.has_nutrition])
        
        results.append({
            "id": recipe.id,
            "name": recipe.name,
            "total_kcal": total_kcal,
            "cookable": len(missing) == 0,
            "missing": missing
        })
        
    # 3. Trier : Les recettes réalisables en premier, puis celles avec le moins de manquants
    results.sort(key=lambda x: (not x["cookable"], len(x["missing"])))
    
    return results

def set_day_active_status(user_id: int, date_str: str, is_active: bool) -> None:
    """Marque un jour comme actif (entraînement) ou inactif (repos)."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_status (
                user_id INTEGER,
                date_str TEXT,
                is_active INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date_str)
            )
        """)
        conn.execute("""
            INSERT INTO daily_status (user_id, date_str, is_active) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, date_str) DO UPDATE SET is_active=excluded.is_active
        """, (user_id, date_str, int(is_active)))

def get_day_active_status(user_id: int, date_str: str) -> bool:
    """Vérifie si un jour est marqué comme actif."""
    with get_connection() as conn:
        try:
            row = conn.execute("SELECT is_active FROM daily_status WHERE user_id=? AND date_str=?", (user_id, date_str)).fetchone()
            return bool(row["is_active"]) if row else False
        except:
            return False # Si la table n'existe pas encore

def get_week_active_status(user_id: int, start_date: str) -> dict:
    """Retourne un dictionnaire avec le statut (actif/repos) des 7 jours."""
    with get_connection() as conn:
        try:
            rows = conn.execute("""
                SELECT date_str, is_active FROM daily_status 
                WHERE user_id = ? AND date_str >= ? AND date_str < date(?, '+7 days')
            """, (user_id, start_date, start_date)).fetchall()
            return {r["date_str"]: bool(r["is_active"]) for r in rows}
        except Exception:
            # Si la table n'existe pas encore ou qu'il y a un souci de lecture,
            # on renvoie un dictionnaire vide (tous les jours seront considérés inactifs)
            return {}
        

def log_body_metrics(user_id: int, date_str: str, weight: float = None, bf: float = None) -> None:
    """Ajoute ou met à jour la pesée et le bodyfat pour un jour donné."""
    with get_connection() as conn:
        # On utilise UPSERT (INSERT ... ON CONFLICT) pour écraser si on se repèse le même jour
        conn.execute("""
            INSERT INTO body_tracking (user_id, date_str, weight_kg, bf_pct)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, date_str) DO UPDATE SET
                weight_kg = excluded.weight_kg,
                bf_pct = excluded.bf_pct
        """, (user_id, date_str, weight, bf))
        
        # Optionnel mais recommandé : on met aussi à jour le profil global de l'utilisateur
        # pour que les macros (Katch-McArdle) s'ajustent avec son nouveau poids !
        if weight is not None:
            conn.execute("UPDATE user_profile SET weight_kg = ? WHERE id = ?", (weight, user_id))
        if bf is not None:
            conn.execute("UPDATE user_profile SET current_bf_pct = ? WHERE id = ?", (bf, user_id))

def get_body_history(user_id: int, limit: int = 30) -> list[BodyTrackingEntry]:
    """Récupère l'historique des pesées, trié chronologiquement pour les graphiques."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, date_str, weight_kg, bf_pct 
            FROM body_tracking 
            WHERE user_id = ? 
            ORDER BY date_str ASC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        
        return [BodyTrackingEntry(
            id=r["id"],
            log_date=r["date_str"],
            weight_kg=r["weight_kg"],
            bf_pct=r["bf_pct"]
        ) for r in rows]