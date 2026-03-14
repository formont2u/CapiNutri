"""
crud.py — Database operations for all modules.
"""
from flask import jsonify
from db import get_connection, NUTRIENT_FIELDS
from models import Recipe, Ingredient, UserProfile, FoodLogEntry, ExerciseEntry
from typing import Optional
import inspect


def _norm(name):
    """Normalise un nom d'ingrédient pour faciliter les comparaisons."""
    if not name:
        return ""
    return name.strip().lower()

# ── Categories ────────────────────────────────────────────────────────────────

def get_or_create_category(name: str) -> int:
    name = name.strip().title()
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
        if row: return row["id"]
        return conn.execute("INSERT INTO categories (name) VALUES (?)", (name,)).lastrowid

def list_categories() -> list[str]:
    with get_connection() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM categories ORDER BY name")]

def delete_category(name: str) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM categories WHERE name=?", (name.title(),)).rowcount > 0


# ── Recipes ───────────────────────────────────────────────────────────────────

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


def _set_recipe_tags(conn, recipe_id: int, tag_names: list[str]) -> None:
    conn.execute("DELETE FROM recipe_tags WHERE recipe_id=?", (recipe_id,))
    for name in tag_names:
        row = conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
        if row:
            conn.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?,?)",
                         (recipe_id, row["id"]))


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


def get_recipe(recipe_id: int) -> Optional[Recipe]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT r.id, r.name, r.servings, r.instructions, c.name AS category, r.category_id
               FROM recipes r LEFT JOIN categories c ON c.id=r.category_id WHERE r.id=?""",
            (recipe_id,)
        ).fetchone()
        if not row: return None
        tags = [r["name"] for r in conn.execute(
            """SELECT t.name FROM tags t
               JOIN recipe_tags rt ON rt.tag_id=t.id
               WHERE rt.recipe_id=? ORDER BY t.name""", (recipe_id,)
        )]
        return Recipe(
            id=row["id"], name=row["name"], servings=row["servings"],
            instructions=row["instructions"] or "", category=row["category"],
            category_id=row["category_id"], tags=tags,
            ingredients=_fetch_ingredients(conn, recipe_id),
        )


def _fetch_ingredients(conn, recipe_id: int) -> list[Ingredient]:
    fields = ["id","name","quantity","unit"] + NUTRIENT_FIELDS
    rows = conn.execute(
        f"SELECT {','.join(fields)} FROM ingredients WHERE recipe_id=? ORDER BY id",
        (recipe_id,)
    ).fetchall()
    return [
        Ingredient(
            id=r["id"], recipe_id=recipe_id,
            name=r["name"], quantity=r["quantity"], unit=r["unit"],
            **{f: r[f] for f in NUTRIENT_FIELDS}
        )
        for r in rows
    ]


def list_recipes(category: Optional[str] = None, search: Optional[str] = None,
                 tag: Optional[str] = None) -> list[dict]:
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
                """SELECT t.name FROM tags t JOIN recipe_tags rt ON rt.tag_id=t.id
                   WHERE rt.recipe_id=? ORDER BY t.name""", (r["id"],)
            )]
        return rows


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


def recipe_count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]


# ── User Profile ──────────────────────────────────────────────────────────────

# ── Profil Utilisateur (Multi-comptes) ────────────────────────────────────────

def get_profile(user_id: int) -> UserProfile:
    with get_connection() as conn:
        # On cherche le profil de L'UTILISATEUR connecté, plus l'id=1 fixe
        row = conn.execute("SELECT * FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return UserProfile()
            
        from dataclasses import fields
        valid_keys = {f.name for f in fields(UserProfile)}
        kwargs = {k: row[k] for k in row.keys() if k in valid_keys}
        return UserProfile(**kwargs)

def save_profile(p: UserProfile, user_id: int):
    with get_connection() as conn:
        # On supprime l'ancien profil de CET utilisateur
        conn.execute("DELETE FROM user_profile WHERE user_id=?", (user_id,))
        
        # On insère le nouveau avec son user_id
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
# ── Food Log ──────────────────────────────────────────────────────────────────

_LOG_FIELDS = ["id","log_date","meal_type","recipe_id","label","servings"] + NUTRIENT_FIELDS

def create_food_log(user_id, label, servings, kcal, meal_type, date_str, 
                 protein_g=0, carbs_g=0, fat_g=0, sugars_g=0, 
                 fiber_g=0, saturated_g=0, sodium_mg=0, recipe_id=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # On déclare bien nos 14 colonnes, et on met 14 points d'interrogation
        query = """
            INSERT INTO food_log (
                user_id, label, servings, kcal, meal_type, log_date, recipe_id,
                protein_g, carbs_g, fat_g, sugars_g, fiber_g, saturated_g, sodium_mg
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        # On passe exactement les 14 variables dans le même ordre
        cursor.execute(query, (
            user_id, label, servings, kcal, meal_type, date_str, recipe_id,
            protein_g, carbs_g, fat_g, sugars_g, fiber_g, saturated_g, sodium_mg
        ))
        
        # --- C'EST ICI QUE CA SE JOUE ---
        new_id = cursor.lastrowid  # Récupère l'ID auto-incrémenté
        conn.commit()
        
        return new_id
def get_food_log_day(user_id, date_str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM food_log 
            WHERE user_id = ? AND log_date = ?
            ORDER BY id ASC
        """, (user_id, date_str))

        rows = cursor.fetchall()

        # On récupère la liste des arguments acceptés par le constructeur de FoodLogEntry
        sig = inspect.signature(FoodLogEntry.__init__)
        valid_keys = sig.parameters.keys()
        
       
        entries = []
        for r in rows:
            d = dict(r)
            # On ne garde que les clés qui existent dans le constructeur de la classe
            filtered_d = {k: v for k, v in d.items() if k in valid_keys}
            entries.append(FoodLogEntry(**filtered_d))
            
        return entries


def delete_food_log(user_id, entry_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        # Sécurité : on vérifie l'user_id en plus de l'id de la ligne
        cursor.execute("DELETE FROM food_log WHERE id = ? AND user_id = ?", (entry_id, user_id))
        return cursor.rowcount > 0


def get_week_summary(start_date: str) -> list[dict]:
    """Return daily kcal + macro totals for 7 days starting from start_date."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT log_date,
                   ROUND(SUM(kcal),0)      AS kcal,
                   ROUND(SUM(protein_g),1) AS protein_g,
                   ROUND(SUM(carbs_g),1)   AS carbs_g,
                   ROUND(SUM(fat_g),1)     AS fat_g
            FROM food_log
            WHERE log_date >= ? AND log_date < date(?, '+7 days')
            GROUP BY log_date ORDER BY log_date
        """, (start_date, start_date)).fetchall()
        return [dict(r) for r in rows]


def sum_day_nutrition(entries: list[FoodLogEntry]) -> dict:
    totals = {f: 0.0 for f in NUTRIENT_FIELDS}
    for e in entries:
        for f in NUTRIENT_FIELDS:
            totals[f] += getattr(e, f) or 0.0
    return {k: round(v, 2) for k, v in totals.items()}


# ── Exercise Log ──────────────────────────────────────────────────────────────

def add_exercise(user_id: int, entry: ExerciseEntry) -> int:
    with get_connection() as conn:
        return conn.execute(
            "INSERT INTO exercise_log (user_id, log_date, name, kcal_burned, duration_min) VALUES (?,?,?,?,?)",
            (user_id, entry.log_date, entry.name, entry.kcal_burned, entry.duration_min)
        ).lastrowid


def get_exercise_day(user_id: int, date_str: str) -> list[ExerciseEntry]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM exercise_log WHERE user_id=? AND log_date=?", 
            (user_id, date_str)
        ).fetchall()
        
        entries = []
        for r in rows:
            d = dict(r)
            d.pop("id", None)
            d.pop("user_id", None)
            entries.append(ExerciseEntry(**d))
        return entries


def delete_exercise(user_id: int, entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM exercise_log WHERE id=? AND user_id=?", (entry_id, user_id)).rowcount > 0


def get_exercise_week(start_date: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT log_date, ROUND(SUM(kcal_burned),0) AS kcal_burned
            FROM exercise_log
            WHERE log_date >= ? AND log_date < date(?, '+7 days')
            GROUP BY log_date ORDER BY log_date
        """, (start_date, start_date)).fetchall()
        return [dict(r) for r in rows]


# ── Daily goal override ───────────────────────────────────────────────────────

def get_daily_goal(user_id: int, date_str: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_goals WHERE user_id=? AND goal_date=?", 
            (user_id, date_str)
        ).fetchone()
        return dict(row) if row else None


def set_daily_goal(user_id: int, date_str: str, kcal: float, protein: float, carbs: float, fat: float) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_goals WHERE user_id=? AND goal_date=?", 
            (user_id, date_str)
        ).fetchone()
        
        if existing:
            conn.execute(
                "UPDATE daily_goals SET goal_kcal=?, goal_protein_g=?, goal_carbs_g=?, goal_fat_g=? WHERE id=?",
                (kcal, protein, carbs, fat, existing["id"])
            )
            return existing["id"]
        else:
            return conn.execute(
                "INSERT INTO daily_goals (user_id, goal_date, goal_kcal, goal_protein_g, goal_carbs_g, goal_fat_g) VALUES (?,?,?,?,?,?)",
                (user_id, date_str, kcal, protein, carbs, fat)
            )


def delete_daily_goal(user_id: int, date_str: str) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM daily_goals WHERE user_id=? AND goal_date=?", (user_id, date_str)).rowcount > 0


# ── Ingredient Library ────────────────────────────────────────────────────────

def list_library(search: str = "") -> list[dict]:
    """All library entries, with optional name search, sorted by used_count desc."""
    sql = """
        SELECT id, name, brand, barcode, used_count, updated_at,
               kcal_100g, protein_g_100g, carbs_g_100g, fat_g_100g
        FROM ingredient_library
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (name LIKE ? OR brand LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY used_count DESC, name"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def get_library_entry(entry_id: int) -> Optional[dict]:
    cols = ["id", "name", "search_key", "brand", "barcode", "used_count"] + \
           [f + "_100g" for f in NUTRIENT_FIELDS]
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(cols)} FROM ingredient_library WHERE id=?", (entry_id,)
        ).fetchone()
        return dict(row) if row else None


def update_library_entry(entry_id: int, name: str, brand: str, barcode: str,
                         per_100g: dict) -> bool:
    from nutrition_api import _normalise
    nutr_vals = {f + "_100g": per_100g.get(f) for f in NUTRIENT_FIELDS}
    set_clause = ", ".join(f"{k} = ?" for k in nutr_vals)
    with get_connection() as conn:
        rows = conn.execute(
            f"UPDATE ingredient_library SET name=?, search_key=?, brand=?, barcode=?, "
            f"{set_clause}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [name, _normalise(name), brand, barcode, *nutr_vals.values(), entry_id]
        ).rowcount
    return rows > 0


def delete_library_entry(entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "DELETE FROM ingredient_library WHERE id=?", (entry_id,)
        ).rowcount > 0


# ── Meal Plan ─────────────────────────────────────────────────────────────────

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]
MEAL_LABELS = {"breakfast": "Petit-déjeuner", "lunch": "Déjeuner",
               "dinner": "Dîner", "snack": "Snack"}
MEAL_ICONS  = {"breakfast": "bi-sunrise", "lunch": "bi-sun",
               "dinner": "bi-moon-stars", "snack": "bi-apple"}

def get_plan(user_id: int, date_str: str) -> dict:
    """Return the meal plan for a given user and date as {meal_type: {recipe, ...} | None}."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT mp.meal_type, mp.id AS plan_id, mp.is_logged,
                   r.id AS recipe_id, r.name AS recipe_name, r.servings,
                   ROUND(SUM(i.kcal), 0) AS total_kcal
            FROM meal_plan mp
            JOIN recipes r ON r.id = mp.recipe_id
            LEFT JOIN ingredients i ON i.recipe_id = r.id
            WHERE mp.user_id = ? AND mp.plan_date = ?
            GROUP BY mp.id
        """, (user_id, date_str)).fetchall()

    plan = {t: None for t in MEAL_TYPES}
    for r in rows:
        plan[r["meal_type"]] = dict(r)
    return plan

def set_plan_slot(user_id: int, date_str: str, meal_type: str, recipe_id: int) -> int:
    """Set (upsert) a recipe for a user's meal slot. Returns plan row id."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM meal_plan WHERE user_id=? AND plan_date=? AND meal_type=?",
            (user_id, date_str, meal_type)
        ).fetchone()
        
        if existing:
            conn.execute(
                "UPDATE meal_plan SET recipe_id=?, is_logged=0 WHERE id=? AND user_id=?",
                (recipe_id, existing["id"], user_id)
            )
            return existing["id"]
            
        return conn.execute(
            "INSERT INTO meal_plan (user_id, plan_date, meal_type, recipe_id) VALUES (?,?,?,?)",
            (user_id, date_str, meal_type, recipe_id)
        ).lastrowid

def clear_plan_slot(user_id: int, plan_id: int) -> bool:
    with get_connection() as conn:
        # Sécurité : on ne supprime que si ça appartient à user_id
        return conn.execute("DELETE FROM meal_plan WHERE id=? AND user_id=?", (plan_id, user_id)).rowcount > 0

def mark_plan_logged(user_id: int, plan_id: int) -> None:
    with get_connection() as conn:
        # Sécurité : on ne met à jour que si ça appartient à user_id
        conn.execute("UPDATE meal_plan SET is_logged=1 WHERE id=? AND user_id=?", (plan_id, user_id))

def suggest_recipe(user_id: int, meal_type: str, date_str: str) -> Optional[dict]:
    """
    Pick a random recipe for a meal slot, preferring recipes NOT logged recently by THIS USER (7 days).
    Returns a minimal recipe dict, or None if no recipes exist.
    """
    with get_connection() as conn:
        # Recipes logged in the last 7 days BY THIS USER (avoid repeats)
        recent = {r["recipe_id"] for r in conn.execute("""
            SELECT DISTINCT recipe_id FROM food_log
            WHERE user_id = ? AND recipe_id IS NOT NULL
              AND log_date >= date(?, '-7 days') AND log_date < ?
        """, (user_id, date_str, date_str)).fetchall() if r["recipe_id"]}

        # Also avoid what's already planned today BY THIS USER
        planned = {r["recipe_id"] for r in conn.execute(
            "SELECT recipe_id FROM meal_plan WHERE user_id=? AND plan_date=?", 
            (user_id, date_str)
        ).fetchall()}

        excluded = recent | planned

        # All recipes with their total kcal (Les recettes restent communes)
        rows = conn.execute("""
            SELECT r.id, r.name, r.servings, ROUND(SUM(i.kcal),0) AS total_kcal
            FROM recipes r
            LEFT JOIN ingredients i ON i.recipe_id = r.id
            GROUP BY r.id ORDER BY RANDOM()
        """).fetchall()

    if not rows:
        return None

    # Prefer not recently eaten; fall back to any if all are recent
    preferred = [r for r in rows if r["id"] not in excluded]
    pick = (preferred or list(rows))[0]
    return dict(pick)

# ── Tags ──────────────────────────────────────────────────────────────────────

def list_tags() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, name, color, icon FROM tags ORDER BY name"
        )]

def get_recipe_tags(recipe_id: int) -> list[str]:
    with get_connection() as conn:
        return [r["name"] for r in conn.execute(
            """SELECT t.name FROM tags t JOIN recipe_tags rt ON rt.tag_id=t.id
               WHERE rt.recipe_id=? ORDER BY t.name""", (recipe_id,)
        )]


# ── Pantry ────────────────────────────────────────────────────────────────────

def list_pantry(user_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, name, quantity, unit FROM pantry WHERE user_id=? ORDER BY name",
            (user_id,)
        )]

def add_pantry_item(user_id: int, name: str, quantity: Optional[float], unit: str) -> int:
    with get_connection() as conn:
        # On vérifie si l'utilisateur possède déjà cet ingrédient
        existing = conn.execute(
            "SELECT id FROM pantry WHERE name=? AND user_id=?", 
            (name.strip(), user_id)
        ).fetchone()
        
        if existing:
            # S'il existe déjà pour CET utilisateur, on met à jour la quantité
            conn.execute(
                "UPDATE pantry SET quantity=?, unit=? WHERE id=?",
                (quantity, unit.strip(), existing["id"])
            )
            return existing["id"]
        else:
            # Sinon, on le crée pour lui
            return conn.execute(
                "INSERT INTO pantry (user_id, name, quantity, unit) VALUES (?,?,?,?)",
                (user_id, name.strip(), quantity, unit.strip())
            ).lastrowid

def update_pantry_item(user_id: int, item_id: int, name: str, quantity: Optional[float], unit: str) -> bool:
    with get_connection() as conn:
        # On sécurise la modification avec le user_id
        return conn.execute(
            "UPDATE pantry SET name=?, quantity=?, unit=? WHERE id=? AND user_id=?",
            (name.strip(), quantity, unit.strip(), item_id, user_id)
        ).rowcount > 0

def delete_pantry_item(user_id: int, item_id: int) -> bool:
    with get_connection() as conn:
        # On sécurise la suppression avec le user_id
        return conn.execute("DELETE FROM pantry WHERE id=? AND user_id=?", (item_id, user_id)).rowcount > 0

def get_cookable_recipes(user_id: int) -> list[dict]:
    """
    Return recipes where ALL ingredients (by name) exist in the user's pantry.
    """
    # On charge uniquement le garde-manger de l'utilisateur connecté !
    pantry_names = [r["name"].lower() for r in list_pantry(user_id)]
    if not pantry_names:
        return []

    all_recipes = list_recipes()
    cookable = []
    for r in all_recipes:
        recipe = get_recipe(r["id"])
        if not recipe or not recipe.ingredients:
            continue
        missing = []
        for ing in recipe.ingredients:
            ing_name = ing.name.lower()
            if not any(p in ing_name or ing_name in p for p in pantry_names):
                missing.append(ing.name)
        r["missing"] = missing
        r["cookable"] = len(missing) == 0
        if len(missing) <= 2:  # Show recipes missing ≤2 items too
            cookable.append(r)
    return sorted(cookable, key=lambda x: len(x["missing"]))


# ── Shopping List ─────────────────────────────────────────────────────────────

def get_week_shopping_list(user_id: int, start_date: str) -> dict:
    """
    Aggregate all ingredients from recipes planned in the 7 days starting start_date.
    Returns: {
        "days": [{date, meal_type, recipe_name},...],
        "items": [{"name", "entries": [{"qty","unit","recipe"}], "total_by_unit": {unit: total}}]
    }
    """
    import unicodedata, re

    def _norm(s: str) -> str:
        s = s.strip().lower()
        s = unicodedata.normalize("NFKD", s)
        s = s.encode("ascii", "ignore").decode()
        s = re.sub(r"[^a-z0-9 ]", "", s)
        return re.sub(r"\s+", " ", s).strip()

    with get_connection() as conn:
        # 👇 Ajout du filtre mp.user_id = ? dans la requête !
        rows = conn.execute("""
            SELECT mp.plan_date, mp.meal_type, r.id AS recipe_id, r.name AS recipe_name
            FROM meal_plan mp
            JOIN recipes r ON r.id=mp.recipe_id
            WHERE mp.user_id = ? AND mp.plan_date >= ? AND mp.plan_date < date(?, '+7 days')
            ORDER BY mp.plan_date, mp.meal_type
        """, (user_id, start_date, start_date)).fetchall()

    days = [dict(r) for r in rows]
    recipe_ids_seen = set()
    # Collect ingredients grouped by normalized name
    agg: dict[str, dict] = {}  # norm_name -> {display_name, entries:[{qty,unit,recipe}]}

    for row in rows:
        rid = row["recipe_id"]
        if rid in recipe_ids_seen:
            continue
        recipe_ids_seen.add(rid)
        recipe = get_recipe(rid)
        if not recipe:
            continue
        for ing in recipe.ingredients:
            key = _norm(ing.name)
            if key not in agg:
                agg[key] = {"name": ing.name.strip(), "entries": []}
            agg[key]["entries"].append({
                "qty": ing.quantity,
                "unit": ing.unit or "",
                "recipe": recipe.name,
            })

    # Sum by unit within each ingredient group
    items = []
    for key, data in sorted(agg.items()):
        by_unit: dict[str, float] = {}
        for e in data["entries"]:
            u = e["unit"]
            by_unit[u] = round(by_unit.get(u, 0) + (e["qty"] or 0), 2)
        items.append({
            "name": data["name"],
            "entries": data["entries"],
            "total_by_unit": by_unit,
        })

    return {"days": days, "items": items, "start_date": start_date}
    
    # ── Dashboard Semaine ─────────────────────────────────────────────────────────

def get_week_dashboard(user_id: int, start_date: str) -> dict:
    """Récupère tous les repas et leurs macros pour 7 jours consécutifs depuis le journal unique."""
    from datetime import datetime, timedelta
    
    with get_connection() as conn: # Attention à bien utiliser ton objet db habituel
        # La requête est BEAUCOUP plus simple maintenant !
        rows = conn.execute("""
            SELECT 
                log_date AS plan_date, 
                meal_type, 
                id AS plan_id, 
                1 AS is_logged, 
                recipe_id, 
                label AS recipe_name, 
                servings,
                kcal AS total_kcal,
                protein_g AS total_protein_g,
                carbs_g AS total_carbs_g,
                fat_g AS total_fat_g,
                fiber_g AS total_fiber_g,
                0 AS total_iron_mg -- On force 0 au cas où le fer ne soit pas dans food_log
            FROM food_log
            WHERE user_id = ? AND log_date >= ? AND log_date < date(?, '+7 days')
        """, (user_id, start_date, start_date)).fetchall()

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    
    # 1. On prépare un dictionnaire vide pour les 7 jours de la semaine
    week_plan = {}
    from models import MEAL_TYPES # Assure-toi que cet import est bon
    for i in range(7):
        d_str = (start + timedelta(days=i)).isoformat()
        week_plan[d_str] = {
            "meals": {t: None for t in MEAL_TYPES},
            "daily_totals": {
                "kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, 
                "fat_g": 0.0, "fiber_g": 0.0, "iron_mg": 0.0
            }
        }

    # 2. On remplit les cases avec les repas trouvés dans food_log
    for r in rows:
        d_str = r["plan_date"]
        if d_str in week_plan:
            meal = dict(r)
            week_plan[d_str]["meals"][meal["meal_type"]] = meal
            
            # On additionne au total de la journée
            if meal["total_kcal"]: week_plan[d_str]["daily_totals"]["kcal"] += meal["total_kcal"]
            if meal["total_protein_g"]: week_plan[d_str]["daily_totals"]["protein_g"] += meal["total_protein_g"]
            if meal["total_carbs_g"]: week_plan[d_str]["daily_totals"]["carbs_g"] += meal["total_carbs_g"]
            if meal["total_fat_g"]: week_plan[d_str]["daily_totals"]["fat_g"] += meal["total_fat_g"]
            if meal["total_fiber_g"]: week_plan[d_str]["daily_totals"]["fiber_g"] += meal["total_fiber_g"]
            if meal["total_iron_mg"]: week_plan[d_str]["daily_totals"]["iron_mg"] += meal["total_iron_mg"]
            
    return week_plan
# ── Authentification & Sécurité ───────────────────────────────────────────────

def get_user_by_username(username: str):
    from models import User
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            return User(id=row["id"], username=row["username"], password_hash=row["password_hash"])
        return None

def get_user_by_id(user_id: int):
    from models import User
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            return User(id=row["id"], username=row["username"], password_hash=row["password_hash"])
        return None

def create_user(username: str, password_hash: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        return cur.lastrowid