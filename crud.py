"""
crud.py — Database operations for all modules.
"""

from db import get_connection, NUTRIENT_FIELDS
from models import Recipe, Ingredient, UserProfile, FoodLogEntry, ExerciseEntry
from typing import Optional


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

def get_profile() -> UserProfile:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
        if not row:
            return UserProfile()
        keys = [k for k in row.keys() if k != 'updated_at']
        return UserProfile(**{k: row[k] for k in keys})


def save_profile(p: UserProfile) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO user_profile (id,name,weight_kg,height_cm,age,sex,activity_level,goal,
                goal_kcal,goal_protein_g,goal_carbs_g,goal_fat_g,meals_per_day,updated_at)
            VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, weight_kg=excluded.weight_kg,
                height_cm=excluded.height_cm, age=excluded.age, sex=excluded.sex,
                activity_level=excluded.activity_level, goal=excluded.goal,
                goal_kcal=excluded.goal_kcal, goal_protein_g=excluded.goal_protein_g,
                goal_carbs_g=excluded.goal_carbs_g, goal_fat_g=excluded.goal_fat_g,
                meals_per_day=excluded.meals_per_day,
                updated_at=CURRENT_TIMESTAMP
        """, (p.name, p.weight_kg, p.height_cm, p.age, p.sex, p.activity_level, p.goal,
              p.goal_kcal, p.goal_protein_g, p.goal_carbs_g, p.goal_fat_g, p.meals_per_day))


# ── Food Log ──────────────────────────────────────────────────────────────────

_LOG_FIELDS = ["id","log_date","meal_type","recipe_id","label","servings"] + NUTRIENT_FIELDS

def add_food_log(entry: FoodLogEntry) -> int:
    fields = ["log_date","meal_type","recipe_id","label","servings"] + NUTRIENT_FIELDS
    vals   = [entry.log_date, entry.meal_type, entry.recipe_id, entry.label, entry.servings]
    vals  += [getattr(entry, f, None) for f in NUTRIENT_FIELDS]
    with get_connection() as conn:
        return conn.execute(
            f"INSERT INTO food_log ({','.join(fields)}) VALUES ({','.join(['?']*len(fields))})",
            vals
        ).lastrowid


def get_food_log_day(date_str: str) -> list[FoodLogEntry]:
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT {','.join(_LOG_FIELDS)} FROM food_log WHERE log_date=? ORDER BY created_at",
            (date_str,)
        ).fetchall()
        return [FoodLogEntry(**{k: r[k] for k in _LOG_FIELDS}) for r in rows]


def delete_food_log(entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM food_log WHERE id=?", (entry_id,)).rowcount > 0


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

def add_exercise(entry: ExerciseEntry) -> int:
    with get_connection() as conn:
        return conn.execute(
            "INSERT INTO exercise_log (log_date,name,kcal_burned,duration_min) VALUES (?,?,?,?)",
            (entry.log_date, entry.name, entry.kcal_burned, entry.duration_min)
        ).lastrowid


def get_exercise_day(date_str: str) -> list[ExerciseEntry]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id,log_date,name,kcal_burned,duration_min FROM exercise_log WHERE log_date=? ORDER BY created_at",
            (date_str,)
        ).fetchall()
        return [ExerciseEntry(**dict(r)) for r in rows]


def delete_exercise(entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM exercise_log WHERE id=?", (entry_id,)).rowcount > 0


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

def get_daily_goal(date_str: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM daily_goals WHERE log_date=?", (date_str,)).fetchone()
        return dict(row) if row else None


def set_daily_goal(date_str: str, kcal: float, protein: float, carbs: float, fat: float) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO daily_goals (log_date,goal_kcal,goal_protein_g,goal_carbs_g,goal_fat_g)
            VALUES (?,?,?,?,?)
            ON CONFLICT(log_date) DO UPDATE SET
                goal_kcal=excluded.goal_kcal, goal_protein_g=excluded.goal_protein_g,
                goal_carbs_g=excluded.goal_carbs_g, goal_fat_g=excluded.goal_fat_g
        """, (date_str, kcal, protein, carbs, fat))


def delete_daily_goal(date_str: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM daily_goals WHERE log_date=?", (date_str,))


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


def get_plan(date_str: str) -> dict:
    """Return the meal plan for a given date as {meal_type: {recipe, ...} | None}."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT mp.meal_type, mp.id AS plan_id, mp.is_logged,
                   r.id AS recipe_id, r.name AS recipe_name, r.servings,
                   ROUND(SUM(i.kcal), 0) AS total_kcal
            FROM meal_plan mp
            JOIN recipes r ON r.id = mp.recipe_id
            LEFT JOIN ingredients i ON i.recipe_id = r.id
            WHERE mp.plan_date = ?
            GROUP BY mp.id
        """, (date_str,)).fetchall()

    plan = {t: None for t in MEAL_TYPES}
    for r in rows:
        plan[r["meal_type"]] = dict(r)
    return plan


def set_plan_slot(date_str: str, meal_type: str, recipe_id: int) -> int:
    """Set (upsert) a recipe for a meal slot. Returns plan row id."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM meal_plan WHERE plan_date=? AND meal_type=?",
            (date_str, meal_type)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE meal_plan SET recipe_id=?, is_logged=0 WHERE id=?",
                (recipe_id, existing["id"])
            )
            return existing["id"]
        return conn.execute(
            "INSERT INTO meal_plan (plan_date, meal_type, recipe_id) VALUES (?,?,?)",
            (date_str, meal_type, recipe_id)
        ).lastrowid


def clear_plan_slot(plan_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM meal_plan WHERE id=?", (plan_id,)).rowcount > 0


def mark_plan_logged(plan_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE meal_plan SET is_logged=1 WHERE id=?", (plan_id,))


def suggest_recipe(meal_type: str, date_str: str) -> Optional[dict]:
    """
    Pick a random recipe for a meal slot, preferring recipes NOT logged recently (7 days).
    Returns a minimal recipe dict, or None if no recipes exist.
    """
    with get_connection() as conn:
        # Recipes logged in the last 7 days (avoid repeats)
        recent = {r["recipe_id"] for r in conn.execute("""
            SELECT DISTINCT recipe_id FROM food_log
            WHERE recipe_id IS NOT NULL
              AND log_date >= date(?, '-7 days') AND log_date < ?
        """, (date_str, date_str)).fetchall() if r["recipe_id"]}

        # Also avoid what's already planned today
        planned = {r["recipe_id"] for r in conn.execute(
            "SELECT recipe_id FROM meal_plan WHERE plan_date=?", (date_str,)
        ).fetchall()}

        excluded = recent | planned

        # All recipes with their total kcal
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

def list_pantry() -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, name, quantity, unit FROM pantry ORDER BY name"
        )]

def add_pantry_item(name: str, quantity: Optional[float], unit: str) -> int:
    with get_connection() as conn:
        try:
            return conn.execute(
                "INSERT INTO pantry (name, quantity, unit) VALUES (?,?,?)",
                (name.strip(), quantity, unit.strip())
            ).lastrowid
        except Exception:
            # Update if name already exists
            conn.execute(
                "UPDATE pantry SET quantity=?, unit=? WHERE name=?",
                (quantity, unit.strip(), name.strip())
            )
            return conn.execute("SELECT id FROM pantry WHERE name=?", (name.strip(),)).fetchone()["id"]

def update_pantry_item(item_id: int, name: str, quantity: Optional[float], unit: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "UPDATE pantry SET name=?, quantity=?, unit=? WHERE id=?",
            (name.strip(), quantity, unit.strip(), item_id)
        ).rowcount > 0

def delete_pantry_item(item_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM pantry WHERE id=?", (item_id,)).rowcount > 0

def get_cookable_recipes() -> list[dict]:
    """
    Return recipes where ALL ingredients (by name) exist in the pantry.
    Matching is case-insensitive substring: pantry 'lait' matches ingredient 'Lait entier'.
    """
    pantry_names = [r["name"].lower() for r in list_pantry()]
    if not pantry_names:
        return []

    all_recipes = list_recipes()
    cookable = []
    for r in all_recipes:
        recipe = get_recipe(r["id"])
        if not recipe or not recipe.ingredients:
            continue
        # Check if every ingredient has a match in pantry
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

def get_week_shopping_list(start_date: str) -> dict:
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
        rows = conn.execute("""
            SELECT mp.plan_date, mp.meal_type, r.id AS recipe_id, r.name AS recipe_name
            FROM meal_plan mp
            JOIN recipes r ON r.id=mp.recipe_id
            WHERE mp.plan_date >= ? AND mp.plan_date < date(?, '+7 days')
            ORDER BY mp.plan_date, mp.meal_type
        """, (start_date, start_date)).fetchall()

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