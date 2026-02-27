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
    return rid


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
        return Recipe(
            id=row["id"], name=row["name"], servings=row["servings"],
            instructions=row["instructions"] or "", category=row["category"],
            category_id=row["category_id"],
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


def list_recipes(category: Optional[str] = None, search: Optional[str] = None) -> list[dict]:
    query = """
        SELECT r.id, r.name, r.servings, c.name AS category, ROUND(SUM(i.kcal),0) AS total_kcal
        FROM recipes r
        LEFT JOIN categories c ON c.id=r.category_id
        LEFT JOIN ingredients i ON i.recipe_id=r.id
        WHERE 1=1
    """
    params = []
    if category: query += " AND c.name=?"; params.append(category.title())
    if search:   query += " AND r.name LIKE ?"; params.append(f"%{search}%")
    query += " GROUP BY r.id ORDER BY r.name"
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(query, params)]


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
                goal_kcal,goal_protein_g,goal_carbs_g,goal_fat_g,updated_at)
            VALUES (1,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, weight_kg=excluded.weight_kg,
                height_cm=excluded.height_cm, age=excluded.age, sex=excluded.sex,
                activity_level=excluded.activity_level, goal=excluded.goal,
                goal_kcal=excluded.goal_kcal, goal_protein_g=excluded.goal_protein_g,
                goal_carbs_g=excluded.goal_carbs_g, goal_fat_g=excluded.goal_fat_g,
                updated_at=CURRENT_TIMESTAMP
        """, (p.name, p.weight_kg, p.height_cm, p.age, p.sex, p.activity_level, p.goal,
              p.goal_kcal, p.goal_protein_g, p.goal_carbs_g, p.goal_fat_g))


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
