"""
crud.py - SQLite data-access layer.
"""

from dataclasses import fields
from typing import Optional

from constants import MEAL_TYPES, NUTRIENT_FIELDS
from db import LOCAL_DATA_ID, get_connection
from models import BodyTrackingEntry, ExerciseEntry, FoodLogEntry, Ingredient, Recipe, UserProfile
from services.unit_conversion import convert_between_units
from utils import normalize_string

WEEKLY_TOTAL_FIELDS = ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "iron_mg")
DEFAULT_TAGS = (
    {"name": "breakfast", "color": "#f59f00", "icon": "bi-sunrise-fill"},
    {"name": "lunch", "color": "#0d6efd", "icon": "bi-sun-fill"},
    {"name": "dinner", "color": "#6f42c1", "icon": "bi-moon-stars-fill"},
    {"name": "snack", "color": "#fd7e14", "icon": "bi-cup-hot-fill"},
    {"name": "vegetarian", "color": "#2f9e44", "icon": "bi-flower1"},
    {"name": "vegan", "color": "#20c997", "icon": "bi-leaf-fill"},
    {"name": "sauce", "color": "#b35c1e", "icon": "bi-droplet-fill"},
    {"name": "soup", "color": "#0ea5a4", "icon": "bi-bowl-hot-fill"},
    {"name": "high-protein", "color": "#e03131", "icon": "bi-lightning-charge-fill"},
    {"name": "cheap", "color": "#198754", "icon": "bi-piggy-bank-fill"},
    {"name": "quick", "color": "#6c757d", "icon": "bi-stopwatch-fill"},
    {"name": "batch-cook", "color": "#795548", "icon": "bi-box2-heart-fill"},
    {"name": "post-workout", "color": "#d63384", "icon": "bi-bicycle"},
)
DEFAULT_TAG_NAMES = {tag["name"] for tag in DEFAULT_TAGS}
MEAL_TAG_ALIASES = {
    "breakfast": {"breakfast", "petit dejeuner", "petit-dejeuner", "matin"},
    "lunch": {"lunch", "dejeuner", "midi"},
    "dinner": {"dinner", "diner", "soir"},
    "snack": {"snack", "collation", "gouter", "encas"},
}


def _row_to_dataclass(model_cls, row):
    valid_fields = {field.name for field in fields(model_cls)}
    return model_cls(**{key: value for key, value in dict(row).items() if key in valid_fields})


def _clean_tag_name(name: str) -> str:
    return (name or "").strip()


def _normalize_tag_name(name: str) -> str:
    return normalize_string(_clean_tag_name(name))

def get_profile() -> UserProfile:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE user_id = ?", (LOCAL_DATA_ID,)).fetchone()
        return _row_to_dataclass(UserProfile, row) if row else UserProfile()


def save_profile(profile: UserProfile) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM user_profile WHERE user_id = ?", (LOCAL_DATA_ID,))
        conn.execute(
            """
            INSERT INTO user_profile (
                user_id, name, weight_kg, height_cm, age, sex,
                activity_level, goal, meals_per_day,
                current_bf_pct, goal_weight_kg, goal_bf_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                LOCAL_DATA_ID,
                profile.name,
                profile.weight_kg,
                profile.height_cm,
                profile.age,
                profile.sex,
                profile.activity_level,
                profile.goal,
                profile.meals_per_day,
                profile.current_bf_pct,
                profile.goal_weight_kg,
                profile.goal_bf_pct,
            ),
        )


def list_tags() -> list[dict]:
    with get_connection() as conn:
        return [dict(row) for row in conn.execute("SELECT id, name, color, icon FROM tags ORDER BY name")]


def list_tags_with_usage() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.name, t.color, t.icon, COUNT(rt.recipe_id) AS recipe_count
            FROM tags t
            LEFT JOIN recipe_tags rt ON rt.tag_id = t.id
            GROUP BY t.id
            ORDER BY t.name
            """
        ).fetchall()
        tags = []
        for row in rows:
            tag = dict(row)
            tag["is_default"] = tag["name"] in DEFAULT_TAG_NAMES
            tags.append(tag)
        return tags


def ensure_default_tags() -> None:
    with get_connection() as conn:
        for tag in DEFAULT_TAGS:
            existing = conn.execute("SELECT id FROM tags WHERE name = ?", (tag["name"],)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE tags SET color = ?, icon = ? WHERE id = ?",
                    (tag["color"], tag["icon"], existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO tags (name, color, icon) VALUES (?, ?, ?)",
                    (tag["name"], tag["color"], tag["icon"]),
                )


def rename_tag(tag_id: int, new_name: str) -> bool:
    cleaned = _clean_tag_name(new_name)
    normalized = _normalize_tag_name(cleaned)
    if not cleaned:
        return False

    with get_connection() as conn:
        current = conn.execute("SELECT name FROM tags WHERE id = ?", (tag_id,)).fetchone()
        if not current or current["name"] in DEFAULT_TAG_NAMES:
            return False

        duplicate = conn.execute(
            "SELECT id FROM tags WHERE lower(name) = lower(?) AND id != ?",
            (cleaned, tag_id),
        ).fetchone()
        if duplicate:
            return False

        display_name = cleaned.lower() if normalized in DEFAULT_TAG_NAMES else cleaned
        return conn.execute("UPDATE tags SET name = ? WHERE id = ?", (display_name, tag_id)).rowcount > 0


def delete_tag(tag_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT name FROM tags WHERE id = ?", (tag_id,)).fetchone()
        if not row or row["name"] in DEFAULT_TAG_NAMES:
            return False
        conn.execute("DELETE FROM recipe_tags WHERE tag_id = ?", (tag_id,))
        deleted = conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,)).rowcount > 0
        _delete_unused_custom_tags(conn)
        return deleted


def migrate_recipe_categories_to_tags() -> int:
    migrated = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.id, c.name AS category_name
            FROM recipes r
            JOIN categories c ON c.id = r.category_id
            WHERE c.name IS NOT NULL AND TRIM(c.name) <> ''
            """
        ).fetchall()

        for row in rows:
            category_name = row["category_name"].strip()
            tag_id = _get_or_create_tag_id(conn, category_name)
            inserted = conn.execute(
                "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?, ?)",
                (row["id"], tag_id),
            ).rowcount
            migrated += inserted

    return migrated


def add_recipe(recipe: Recipe) -> int:
    with get_connection() as conn:
        recipe_id = conn.execute(
            "INSERT INTO recipes (name, servings, instructions) VALUES (?, ?, ?)",
            (recipe.name.strip(), recipe.servings, recipe.instructions.strip()),
        ).lastrowid
        _insert_ingredients(conn, recipe_id, recipe.ingredients)
        _set_recipe_tags(conn, recipe_id, recipe.tags)
    return recipe_id


def update_recipe(recipe: Recipe) -> bool:
    if recipe.id is None:
        return False

    with get_connection() as conn:
        conn.execute(
            "UPDATE recipes SET name = ?, servings = ?, instructions = ? WHERE id = ?",
            (recipe.name.strip(), recipe.servings, recipe.instructions.strip(), recipe.id),
        )
        conn.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe.id,))
        _insert_ingredients(conn, recipe.id, recipe.ingredients)
        _set_recipe_tags(conn, recipe.id, recipe.tags)
    return True


def delete_recipe(recipe_id: int) -> bool:
    with get_connection() as conn:
        deleted = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,)).rowcount > 0
        if deleted:
            _delete_unused_custom_tags(conn)
        return deleted


def get_recipe(recipe_id: int) -> Optional[Recipe]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.id, r.name, r.servings, r.instructions
            FROM recipes r
            WHERE r.id = ?
            """,
            (recipe_id,),
        ).fetchone()
        if not row:
            return None

        tags = [
            tag["name"]
            for tag in conn.execute(
                """
                SELECT t.name
                FROM tags t
                JOIN recipe_tags rt ON rt.tag_id = t.id
                WHERE rt.recipe_id = ?
                ORDER BY t.name
                """,
                (recipe_id,),
            )
        ]
        return Recipe(
            id=row["id"],
            name=row["name"],
            servings=row["servings"],
            instructions=row["instructions"] or "",
            tags=tags,
            ingredients=_fetch_ingredients(conn, recipe_id),
        )


def list_recipes(search: Optional[str] = None, tag: Optional[str] = None) -> list[dict]:
    query = """
        SELECT r.id, r.name, r.servings,
               ROUND(SUM(i.kcal), 0) AS total_kcal,
               ROUND(SUM(i.protein_g), 1) AS total_protein,
               ROUND(SUM(i.sugars_g), 1) AS total_sugars,
               ROUND(SUM(i.fiber_g), 1) AS total_fiber,
               ROUND(SUM(i.saturated_g), 1) AS total_saturated,
               ROUND(SUM(i.sodium_mg), 1) AS total_sodium
        FROM recipes r
        LEFT JOIN ingredients i ON i.recipe_id = r.id
        WHERE 1 = 1
    """
    params = []
    if search:
        query += " AND r.name LIKE ?"
        params.append(f"%{search}%")
    if tag:
        query += """
            AND r.id IN (
                SELECT rt.recipe_id
                FROM recipe_tags rt
                JOIN tags t ON t.id = rt.tag_id
                WHERE t.name = ?
            )
        """
        params.append(tag)

    query += " GROUP BY r.id ORDER BY r.name"

    with get_connection() as conn:
        rows = [dict(row) for row in conn.execute(query, params)]
        for row in rows:
            row["tags"] = [
                tag["name"]
                for tag in conn.execute(
                    """
                    SELECT t.name
                    FROM tags t
                    JOIN recipe_tags rt ON rt.tag_id = t.id
                    WHERE rt.recipe_id = ?
                    ORDER BY t.name
                    """,
                    (row["id"],),
                )
            ]
        return rows


def _set_recipe_tags(conn, recipe_id: int, tag_names: list[str]) -> None:
    conn.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
    for name in tag_names:
        tag_id = _get_or_create_tag_id(conn, name)
        if tag_id:
            conn.execute(
                "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?, ?)",
                (recipe_id, tag_id),
            )
    _delete_unused_custom_tags(conn)


def _get_or_create_tag_id(conn, name: str) -> Optional[int]:
    cleaned = _clean_tag_name(name)
    if not cleaned:
        return None

    row = conn.execute(
        "SELECT id FROM tags WHERE lower(name) = lower(?)",
        (cleaned,),
    ).fetchone()
    if row:
        return row["id"]

    normalized = _normalize_tag_name(cleaned)
    display_name = cleaned.lower() if normalized in DEFAULT_TAG_NAMES else cleaned
    return conn.execute(
        "INSERT INTO tags (name) VALUES (?)",
        (display_name,),
    ).lastrowid


def _delete_unused_custom_tags(conn) -> None:
    conn.execute(
        f"""
        DELETE FROM tags
        WHERE name NOT IN ({",".join("?" for _ in DEFAULT_TAG_NAMES)})
          AND id NOT IN (SELECT DISTINCT tag_id FROM recipe_tags)
        """,
        tuple(DEFAULT_TAG_NAMES),
    )


def _insert_ingredients(conn, recipe_id: int, ingredients: list[Ingredient]) -> None:
    if not ingredients:
        return

    fields_list = ["recipe_id", "name", "quantity", "unit", "library_id", *NUTRIENT_FIELDS]
    placeholders = ",".join(["?"] * len(fields_list))
    rows = []
    for ingredient in ingredients:
        rows.append(
            [
                recipe_id,
                ingredient.name.strip(),
                ingredient.quantity,
                ingredient.unit.strip(),
                ingredient.library_id,
                *[getattr(ingredient, field, None) for field in NUTRIENT_FIELDS],
            ]
        )

    conn.executemany(
        f"INSERT INTO ingredients ({','.join(fields_list)}) VALUES ({placeholders})",
        rows,
    )


def _fetch_ingredients(conn, recipe_id: int) -> list[Ingredient]:
    fields_list = ["id", "name", "quantity", "unit", "library_id", *NUTRIENT_FIELDS]
    rows = conn.execute(
        f"SELECT {','.join(fields_list)} FROM ingredients WHERE recipe_id = ? ORDER BY id",
        (recipe_id,),
    ).fetchall()
    return [
        Ingredient(
            id=row["id"],
            recipe_id=recipe_id,
            name=row["name"],
            quantity=row["quantity"],
            unit=row["unit"],
            library_id=row["library_id"],
            **{field: row[field] for field in NUTRIENT_FIELDS},
        )
        for row in rows
    ]


def create_food_log(
    label: str,
    servings: float,
    kcal: float,
    meal_type: str,
    date_str: str,
    protein_g=0,
    carbs_g=0,
    fat_g=0,
    sugars_g=0,
    fiber_g=0,
    saturated_g=0,
    sodium_mg=0,
    recipe_id=None,
) -> int:
    with get_connection() as conn:
        return conn.execute(
            """
            INSERT INTO food_log (
                user_id, label, servings, kcal, meal_type, log_date, recipe_id,
                protein_g, carbs_g, fat_g, sugars_g, fiber_g, saturated_g, sodium_mg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                LOCAL_DATA_ID,
                label,
                servings,
                kcal,
                meal_type,
                date_str,
                recipe_id,
                protein_g,
                carbs_g,
                fat_g,
                sugars_g,
                fiber_g,
                saturated_g,
                sodium_mg,
            ),
        ).lastrowid


def get_food_log_day(date_str: str) -> list[FoodLogEntry]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM food_log WHERE user_id = ? AND log_date = ? ORDER BY id ASC",
            (LOCAL_DATA_ID, date_str),
        ).fetchall()
        return [_row_to_dataclass(FoodLogEntry, row) for row in rows]


def delete_food_log(entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM food_log WHERE id = ? AND user_id = ?", (entry_id, LOCAL_DATA_ID)).rowcount > 0


def get_food_log_entry(entry_id: int) -> Optional[FoodLogEntry]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM food_log WHERE id = ? AND user_id = ?", (entry_id, LOCAL_DATA_ID)).fetchone()
        return _row_to_dataclass(FoodLogEntry, row) if row else None


def add_exercise(entry: ExerciseEntry) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO exercise_log (user_id, log_date, name, kcal_burned, duration_min, rpe, exercise_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                LOCAL_DATA_ID,
                entry.log_date,
                entry.name,
                entry.kcal_burned,
                entry.duration_min,
                entry.rpe,
                entry.exercise_type,
            ),
        )


def get_exercise_day(date_str: str) -> list[ExerciseEntry]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM exercise_log WHERE user_id = ? AND log_date = ?",
            (LOCAL_DATA_ID, date_str),
        ).fetchall()
        return [
            ExerciseEntry(
                id=row["id"],
                log_date=row["log_date"],
                name=row["name"],
                kcal_burned=row["kcal_burned"],
                duration_min=row["duration_min"],
                rpe=row["rpe"],
                exercise_type=row["exercise_type"],
            )
            for row in rows
        ]


def delete_exercise(entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM exercise_log WHERE id = ? AND user_id = ?", (entry_id, LOCAL_DATA_ID)).rowcount > 0


def get_daily_goal(date_str: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_goals WHERE user_id = ? AND goal_date = ?",
            (LOCAL_DATA_ID, date_str),
        ).fetchone()
        return dict(row) if row else None


def set_daily_goal(date_str: str, kcal: float, protein: float, carbs: float, fat: float) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_goals WHERE user_id = ? AND goal_date = ?",
            (LOCAL_DATA_ID, date_str),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE daily_goals
                SET goal_kcal = ?, goal_protein_g = ?, goal_carbs_g = ?, goal_fat_g = ?
                WHERE id = ?
                """,
                (kcal, protein, carbs, fat, existing["id"]),
            )
            return existing["id"]

        return conn.execute(
            """
            INSERT INTO daily_goals (user_id, goal_date, goal_kcal, goal_protein_g, goal_carbs_g, goal_fat_g)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (LOCAL_DATA_ID, date_str, kcal, protein, carbs, fat),
        ).lastrowid


def delete_daily_goal(date_str: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "DELETE FROM daily_goals WHERE user_id = ? AND goal_date = ?",
            (LOCAL_DATA_ID, date_str),
        ).rowcount > 0


def list_library(search: str = "") -> list[dict]:
    sql = """
        SELECT il.id, il.name, il.brand, il.barcode, il.used_count, il.updated_at,
               il.density_g_ml,
               COUNT(iu.id) AS unit_count,
               kcal_100g, protein_g_100g, carbs_g_100g, fat_g_100g
        FROM ingredient_library il
        LEFT JOIN ingredient_units iu ON iu.library_id = il.id
        WHERE 1 = 1
    """
    params = []
    if search:
        sql += " AND (il.name LIKE ? OR il.brand LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " GROUP BY il.id ORDER BY il.used_count DESC, il.name"

    with get_connection() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def get_library_entry(entry_id: int) -> Optional[dict]:
    columns = ["id", "name", "search_key", "brand", "barcode", "density_g_ml", "used_count", *[f"{field}_100g" for field in NUTRIENT_FIELDS]]
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT {', '.join(columns)} FROM ingredient_library WHERE id = ?",
            (entry_id,),
        ).fetchone()
        return dict(row) if row else None


def update_library_entry(entry_id: int, name: str, brand: str, barcode: str, per_100g: dict, density_g_ml: float | None = None) -> bool:
    nutrient_values = {f"{field}_100g": per_100g.get(field) for field in NUTRIENT_FIELDS}
    set_clause = ", ".join(f"{column} = ?" for column in nutrient_values)
    with get_connection() as conn:
        return conn.execute(
            f"""
            UPDATE ingredient_library
            SET name = ?, search_key = ?, brand = ?, barcode = ?, density_g_ml = ?, {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [name, normalize_string(name), brand, barcode, density_g_ml, *nutrient_values.values(), entry_id],
        ).rowcount > 0


def delete_library_entry(entry_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM ingredient_library WHERE id = ?", (entry_id,)).rowcount > 0


def search_ingredient_library(query: str, limit: int = 5) -> list[dict]:
    key = normalize_string(query)
    if not key:
        return []

    sql = """
        SELECT *
        FROM ingredient_library
        WHERE search_key LIKE ?
        ORDER BY
            CASE
                WHEN search_key = ? THEN 0
                WHEN search_key LIKE ? THEN 1
                ELSE 2
            END,
            used_count DESC
        LIMIT ?
    """
    with get_connection() as conn:
        return [dict(row) for row in conn.execute(sql, (f"%{key}%", key, f"{key}%", limit)).fetchall()]


def get_library_entry_by_barcode(barcode: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ingredient_library WHERE barcode = ?", (barcode,)).fetchone()
        return dict(row) if row else None


def save_ingredient_to_library(name: str, brand: str, barcode: str, per_100g: dict, density_g_ml: float | None = None) -> int:
    key = normalize_string(name)
    nutrient_values = {f"{field}_100g": per_100g.get(field) for field in NUTRIENT_FIELDS}
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, used_count, density_g_ml FROM ingredient_library WHERE search_key = ?",
            (key,),
        ).fetchone()
        if existing:
            set_clause = ", ".join(f"{column} = ?" for column in nutrient_values)
            conn.execute(
                f"""
                UPDATE ingredient_library
                SET {set_clause}, brand = ?, barcode = ?, density_g_ml = ?, used_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                [
                    *nutrient_values.values(),
                    brand,
                    barcode,
                    density_g_ml if density_g_ml is not None else existing["density_g_ml"],
                    existing["used_count"] + 1,
                    existing["id"],
                ],
            )
            return existing["id"]

        columns = ["name", "search_key", "brand", "barcode", "density_g_ml", *nutrient_values.keys()]
        values = [name, key, brand, barcode, density_g_ml, *nutrient_values.values()]
        placeholders = ", ".join(["?"] * len(columns))
        return conn.execute(
            f"INSERT INTO ingredient_library ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        ).lastrowid


def get_library_density(library_id: int, conn=None) -> float | None:
    if conn is None:
        with get_connection() as own_conn:
            return get_library_density(library_id, conn=own_conn)

    row = conn.execute("SELECT density_g_ml FROM ingredient_library WHERE id = ?", (library_id,)).fetchone()
    return float(row["density_g_ml"]) if row and row["density_g_ml"] is not None else None


def get_library_context(library_id: int | None = None, name: str = "", conn=None) -> dict:
    if conn is None:
        with get_connection() as own_conn:
            return get_library_context(library_id, name, conn=own_conn)

    row = None
    if library_id:
        row = conn.execute(
            "SELECT id, density_g_ml FROM ingredient_library WHERE id = ?",
            (library_id,),
        ).fetchone()
    elif name:
        row = conn.execute(
            "SELECT id, density_g_ml FROM ingredient_library WHERE search_key = ?",
            (normalize_string(name),),
        ).fetchone()

    resolved_id = row["id"] if row else library_id
    return {
        "library_id": resolved_id,
        "density_g_ml": float(row["density_g_ml"]) if row and row["density_g_ml"] is not None else None,
        "unit_rows": list_ingredient_units(resolved_id, conn=conn) if resolved_id else [],
    }


def split_quantity_by_stock(
    required_by_unit: dict[str, float],
    pantry_quantity: float | None,
    pantry_unit: str,
    *,
    unit_rows: list[dict] | None = None,
    density_g_ml: float | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    to_buy: dict[str, float] = {}
    in_stock: dict[str, float] = {}
    available_quantity = float(pantry_quantity or 0)
    available_unit = (pantry_unit or "").strip().lower()

    for unit, total_needed in required_by_unit.items():
        target_unit = (unit or "").strip().lower()
        if available_quantity <= 0:
            to_buy[target_unit] = round(total_needed, 4)
            continue

        if not available_unit:
            to_buy[target_unit] = round(total_needed, 4)
            continue

        available_in_target = convert_between_units(
            available_quantity,
            available_unit,
            target_unit,
            unit_rows,
            density_g_ml=density_g_ml,
        )
        if available_in_target is None:
            to_buy[target_unit] = round(total_needed, 4)
            continue

        covered = min(total_needed, available_in_target)
        if covered > 0:
            in_stock[target_unit] = round(covered, 4)

        remainder = total_needed - covered
        if remainder > 0.0001:
            to_buy[target_unit] = round(remainder, 4)

        consumed_in_pantry_unit = convert_between_units(
            covered,
            target_unit,
            available_unit,
            unit_rows,
            density_g_ml=density_g_ml,
        )
        if consumed_in_pantry_unit is not None:
            available_quantity = max(0.0, available_quantity - consumed_in_pantry_unit)

    return to_buy, in_stock


def split_quantity_by_stocks(
    required_by_unit: dict[str, float],
    pantry_items: list[dict] | None,
    *,
    unit_rows: list[dict] | None = None,
    density_g_ml: float | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    remaining = {unit: float(quantity or 0) for unit, quantity in required_by_unit.items()}
    covered_totals: dict[str, float] = {}

    for pantry_item in pantry_items or []:
        if not remaining:
            break

        to_buy, in_stock = split_quantity_by_stock(
            remaining,
            pantry_item.get("quantity"),
            pantry_item.get("unit", ""),
            unit_rows=unit_rows,
            density_g_ml=density_g_ml,
        )
        for unit, covered in in_stock.items():
            covered_totals[unit] = round(covered_totals.get(unit, 0.0) + covered, 4)
        remaining = to_buy

    return remaining, covered_totals


def increment_library_usage(library_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE ingredient_library SET used_count = used_count + 1 WHERE id = ?", (library_id,))


def list_ingredient_units(library_id: int, conn=None) -> list[dict]:
    if conn is None:
        with get_connection() as own_conn:
            return list_ingredient_units(library_id, conn=own_conn)

    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, library_id, unit_name, unit_key, grams_equivalent, ml_equivalent
            FROM ingredient_units
            WHERE library_id = ?
            ORDER BY unit_name
            """,
            (library_id,),
        )
    ]


def update_library_density(entry_id: int, density_g_ml: float | None) -> bool:
    with get_connection() as conn:
        return conn.execute(
            """
            UPDATE ingredient_library
            SET density_g_ml = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (density_g_ml, entry_id),
        ).rowcount > 0


def add_ingredient_unit(library_id: int, unit_name: str, grams_equivalent: float | None = None, ml_equivalent: float | None = None) -> int:
    key = normalize_string(unit_name)
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM ingredient_units WHERE library_id = ? AND unit_key = ?",
            (library_id, key),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE ingredient_units
                SET unit_name = ?, grams_equivalent = ?, ml_equivalent = ?
                WHERE id = ?
                """,
                (unit_name.strip(), grams_equivalent, ml_equivalent, existing["id"]),
            )
            return existing["id"]

        return conn.execute(
            """
            INSERT INTO ingredient_units (library_id, unit_name, unit_key, grams_equivalent, ml_equivalent)
            VALUES (?, ?, ?, ?, ?)
            """,
            (library_id, unit_name.strip(), key, grams_equivalent, ml_equivalent),
        ).lastrowid


def delete_ingredient_unit(library_id: int, unit_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "DELETE FROM ingredient_units WHERE id = ? AND library_id = ?",
            (unit_id, library_id),
        ).rowcount > 0


def get_plan(date_str: str) -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT mp.meal_type, mp.id AS plan_id, mp.is_logged, r.id AS recipe_id, r.name AS recipe_name,
                   r.servings, ROUND(SUM(i.kcal), 0) AS total_kcal
            FROM meal_plan mp
            JOIN recipes r ON r.id = mp.recipe_id
            LEFT JOIN ingredients i ON i.recipe_id = r.id
            WHERE mp.user_id = ? AND mp.plan_date = ?
            GROUP BY mp.id
            """,
            (LOCAL_DATA_ID, date_str),
        ).fetchall()

    plan = {meal_type: None for meal_type in MEAL_TYPES}
    for row in rows:
        plan[row["meal_type"]] = dict(row)
    return plan


def suggest_recipe(meal_type: str, date_str: str) -> Optional[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.name, r.servings, ROUND(SUM(i.kcal), 0) AS total_kcal
            FROM recipes r
            LEFT JOIN ingredients i ON i.recipe_id = r.id
            WHERE r.id NOT IN (
                SELECT recipe_id
                FROM meal_plan
                WHERE user_id = ? AND plan_date = ?
            )
            GROUP BY r.id
            """,
            (LOCAL_DATA_ID, date_str),
        ).fetchall()
        if not rows:
            return None

        meal_tag_keys = MEAL_TAG_ALIASES.get(_normalize_tag_name(meal_type), {_normalize_tag_name(meal_type)})
        pantry_names = {normalize_string(item["name"]) for item in list_pantry()}
        profile = get_profile()
        is_active_day = get_day_active_status(date_str)
        recent_rows = conn.execute(
            """
            SELECT recipe_id, COUNT(*) AS usage_count, MAX(plan_date) AS last_used
            FROM meal_plan
            WHERE user_id = ? AND plan_date >= date(?, '-14 days')
            GROUP BY recipe_id
            """,
            (LOCAL_DATA_ID, date_str),
        ).fetchall()
        recent_usage = {
            row["recipe_id"]: {
                "usage_count": int(row["usage_count"] or 0),
                "last_used": row["last_used"],
            }
            for row in recent_rows
        }
        candidates = []
        for row in rows:
            ingredient_rows = conn.execute(
                "SELECT name FROM ingredients WHERE recipe_id = ?",
                (row["id"],),
            ).fetchall()
            tags = [
                tag["name"]
                for tag in conn.execute(
                    """
                    SELECT t.name
                    FROM tags t
                    JOIN recipe_tags rt ON rt.tag_id = t.id
                    WHERE rt.recipe_id = ?
                    ORDER BY t.name
                    """,
                    (row["id"],),
                )
            ]
            normalized_tags = {_normalize_tag_name(tag) for tag in tags}
            ingredient_names = [normalize_string(ingredient["name"]) for ingredient in ingredient_rows if ingredient["name"]]
            ingredient_count = len(ingredient_names)
            pantry_matches = sum(1 for ingredient_name in ingredient_names if ingredient_name in pantry_names)
            pantry_ratio = (pantry_matches / ingredient_count) if ingredient_count else 0.0
            usage = recent_usage.get(row["id"], {})
            recent_penalty = float(usage.get("usage_count", 0)) * 1.2
            if usage.get("last_used") == date_str:
                recent_penalty += 6.0

            score = 0.0
            reasons = []

            if normalized_tags & meal_tag_keys:
                score += 5.0
                reasons.append("adaptée au créneau")

            if pantry_ratio >= 1:
                score += 3.0
                reasons.append("stock complet")
            elif pantry_ratio >= 0.6:
                score += 1.5
                reasons.append("presque tout en stock")

            if is_active_day and normalized_tags & {"high protein", "high-protein", "post workout", "post-workout"}:
                score += 2.0
                reasons.append("utile un jour actif")

            if meal_type == "breakfast" and normalized_tags & {"quick"}:
                score += 1.0
                reasons.append("rapide")

            if profile.goal in {"cut", "bulk"} and normalized_tags & {"high protein", "high-protein"}:
                score += 1.0
                reasons.append("riche en protéines")

            if normalized_tags & {"cheap"}:
                score += 0.5

            score -= recent_penalty

            candidates.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "servings": row["servings"],
                    "total_kcal": row["total_kcal"],
                    "tags": tags,
                    "pantry_ratio": round(pantry_ratio, 2),
                    "reason": ", ".join(reasons[:2]) if reasons else "bonne option disponible",
                    "_score": score,
                }
            )

        candidates.sort(key=lambda recipe: (-recipe["_score"], -recipe["pantry_ratio"], recipe["name"].lower()))
        suggestion = dict(candidates[0])
        suggestion.pop("_score", None)
        return suggestion


def set_plan_slot(date_str: str, meal_type: str, recipe_id: int) -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM meal_plan WHERE user_id = ? AND plan_date = ? AND meal_type = ?",
            (LOCAL_DATA_ID, date_str, meal_type),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE meal_plan SET recipe_id = ?, is_logged = 0 WHERE id = ? AND user_id = ?",
                (recipe_id, existing["id"], LOCAL_DATA_ID),
            )
            return existing["id"]

        return conn.execute(
            "INSERT INTO meal_plan (user_id, plan_date, meal_type, recipe_id) VALUES (?, ?, ?, ?)",
            (LOCAL_DATA_ID, date_str, meal_type, recipe_id),
        ).lastrowid


def clear_plan_slot(plan_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM meal_plan WHERE id = ? AND user_id = ?", (plan_id, LOCAL_DATA_ID)).rowcount > 0


def mark_plan_logged(plan_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE meal_plan SET is_logged = 1 WHERE id = ? AND user_id = ?", (plan_id, LOCAL_DATA_ID))


def get_week_dashboard(start_date: str) -> dict:
    from datetime import datetime, timedelta

    with get_connection() as conn:
        food_rows = conn.execute(
            """
            SELECT log_date AS plan_date, meal_type, id AS plan_id, 1 AS is_logged, recipe_id, label AS recipe_name,
                   servings, kcal AS total_kcal, protein_g AS total_protein_g, carbs_g AS total_carbs_g,
                   fat_g AS total_fat_g, fiber_g AS total_fiber_g, 0 AS total_iron_mg
            FROM food_log
            WHERE user_id = ? AND log_date >= ? AND log_date < date(?, '+7 days')
            """,
            (LOCAL_DATA_ID, start_date, start_date),
        ).fetchall()
        exercise_rows = conn.execute(
            """
            SELECT log_date, SUM(kcal_burned) AS total_burned
            FROM exercise_log
            WHERE user_id = ? AND log_date >= ? AND log_date < date(?, '+7 days')
            GROUP BY log_date
            """,
            (LOCAL_DATA_ID, start_date, start_date),
        ).fetchall()

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    week_plan = {}
    for offset in range(7):
        current_date = (start + timedelta(days=offset)).isoformat()
        week_plan[current_date] = {
            "meals": {meal_type: None for meal_type in MEAL_TYPES},
            "daily_totals": {
                "kcal": 0.0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "fiber_g": 0.0,
                "iron_mg": 0.0,
                "burned": 0.0,
            },
        }

    for row in food_rows:
        current_date = row["plan_date"]
        if current_date not in week_plan:
            continue

        meal = dict(row)
        week_plan[current_date]["meals"][meal["meal_type"]] = meal
        for field in WEEKLY_TOTAL_FIELDS:
            value = meal.get(f"total_{field}")
            if value:
                week_plan[current_date]["daily_totals"][field] += value

    for row in exercise_rows:
        current_date = row["log_date"]
        if current_date in week_plan:
            week_plan[current_date]["daily_totals"]["burned"] = float(row["total_burned"] or 0.0)

    return week_plan


def get_week_shopping_list(start_date: str) -> dict:
    with get_connection() as conn:
        meals = conn.execute(
            """
            SELECT mp.plan_date, mp.meal_type, r.id AS recipe_id, r.name AS recipe_name
            FROM meal_plan mp
            JOIN recipes r ON r.id = mp.recipe_id
            WHERE mp.user_id = ? AND mp.plan_date >= ? AND mp.plan_date < date(?, '+7 days')
            ORDER BY mp.plan_date ASC
            """,
            (LOCAL_DATA_ID, start_date, start_date),
        ).fetchall()
        days_list = [dict(meal) for meal in meals]

        items = {}
        if meals:
            recipe_ids = sorted({meal["recipe_id"] for meal in meals})
            placeholders = ",".join("?" for _ in recipe_ids)
            ingredient_rows = conn.execute(
                f"SELECT recipe_id, name, quantity, unit, library_id FROM ingredients WHERE recipe_id IN ({placeholders})",
                tuple(recipe_ids),
            ).fetchall()

            ingredients_by_recipe = {}
            for row in ingredient_rows:
                ingredients_by_recipe.setdefault(row["recipe_id"], []).append(dict(row))

            library_context_cache: dict[tuple[int | None, str], dict] = {}
            for meal in meals:
                for ingredient in ingredients_by_recipe.get(meal["recipe_id"], []):
                    name = ingredient["name"].strip()
                    key = normalize_string(name)
                    quantity = float(ingredient["quantity"] or 0)
                    unit = (ingredient["unit"] or "").strip().lower()
                    context_key = (ingredient.get("library_id"), key)
                    library_context = library_context_cache.get(context_key)
                    if library_context is None:
                        library_context = get_library_context(ingredient.get("library_id"), name, conn=conn)
                        library_context_cache[context_key] = library_context
                    item = items.setdefault(
                        key,
                        {
                            "name": name,
                            "library_id": library_context.get("library_id"),
                            "density_g_ml": library_context.get("density_g_ml"),
                            "total_by_unit": {},
                            "entries": [],
                        },
                    )
                    item["total_by_unit"][unit] = item["total_by_unit"].get(unit, 0.0) + quantity
                    item["entries"].append({"recipe": meal["recipe_name"], "qty": quantity, "unit": unit})

    return {"start_date": start_date, "days": days_list, "items": list(items.values())}


def list_pantry() -> list[dict]:
    with get_connection() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id, name, quantity, unit FROM pantry WHERE user_id = ? ORDER BY name",
                (LOCAL_DATA_ID,),
            )
        ]


def add_pantry_item(name: str, quantity: Optional[float], unit: str) -> int:
    stripped_name = name.strip()
    normalized_name = normalize_string(stripped_name)
    with get_connection() as conn:
        existing_rows = conn.execute(
            "SELECT id, name FROM pantry WHERE user_id = ? ORDER BY id",
            (LOCAL_DATA_ID,),
        ).fetchall()
        matching_rows = [row for row in existing_rows if normalize_string(row["name"]) == normalized_name]
        if matching_rows:
            primary_id = matching_rows[0]["id"]
            conn.execute(
                "UPDATE pantry SET quantity = ?, unit = ? WHERE id = ?",
                (quantity, unit.strip(), primary_id),
            )
            conn.execute("UPDATE pantry SET name = ? WHERE id = ?", (stripped_name, primary_id))
            for row in matching_rows[1:]:
                conn.execute("DELETE FROM pantry WHERE id = ?", (row["id"],))
            return primary_id

        return conn.execute(
            "INSERT INTO pantry (user_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
            (LOCAL_DATA_ID, stripped_name, quantity, unit.strip()),
        ).lastrowid


def update_pantry_item(item_id: int, name: str, quantity: Optional[float], unit: str) -> bool:
    with get_connection() as conn:
        updated = conn.execute(
            "UPDATE pantry SET name = ?, quantity = ?, unit = ? WHERE id = ? AND user_id = ?",
            (name.strip(), quantity, unit.strip(), item_id, LOCAL_DATA_ID),
        ).rowcount > 0
        if not updated:
            return False

        normalized_name = normalize_string(name)
        duplicates = conn.execute(
            "SELECT id, name FROM pantry WHERE user_id = ? AND id != ?",
            (LOCAL_DATA_ID, item_id),
        ).fetchall()
        for row in duplicates:
            if normalize_string(row["name"]) == normalized_name:
                conn.execute("DELETE FROM pantry WHERE id = ?", (row["id"],))
        return True


def delete_pantry_item(item_id: int) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM pantry WHERE id = ? AND user_id = ?", (item_id, LOCAL_DATA_ID)).rowcount > 0


def get_cookable_recipes() -> list[dict]:
    pantry_stock: dict[str, list[dict]] = {}
    for item in list_pantry():
        key = normalize_string(item["name"])
        pantry_stock.setdefault(key, []).append(dict(item))

    results = []
    library_context_cache: dict[tuple[int | None, str], dict] = {}
    for recipe_summary in list_recipes():
        recipe = get_recipe(recipe_summary["id"])
        if not recipe:
            continue

        missing = []
        available_count = 0
        for ingredient in recipe.ingredients:
            key = normalize_string(ingredient.name)
            pantry_items = pantry_stock.get(key, [])
            if not pantry_items:
                missing.append(ingredient.name)
                continue

            cache_key = (ingredient.library_id, normalize_string(ingredient.name))
            library_context = library_context_cache.get(cache_key)
            if library_context is None:
                library_context = get_library_context(ingredient.library_id, ingredient.name)
                library_context_cache[cache_key] = library_context
            required_by_unit = {(ingredient.unit or "").strip().lower(): float(ingredient.quantity or 0)}
            to_buy, _ = split_quantity_by_stocks(
                required_by_unit,
                pantry_items,
                unit_rows=library_context.get("unit_rows"),
                density_g_ml=library_context.get("density_g_ml"),
            )
            if to_buy:
                missing.append(ingredient.name)
            else:
                available_count += 1

        total_ingredients = len(recipe.ingredients)
        pantry_ratio = (available_count / total_ingredients) if total_ingredients else 0.0

        results.append(
            {
                "id": recipe.id,
                "name": recipe.name,
                "total_kcal": sum(ingredient.kcal or 0 for ingredient in recipe.ingredients if ingredient.has_nutrition),
                "cookable": not missing,
                "missing": missing,
                "available_count": available_count,
                "total_ingredients": total_ingredients,
                "pantry_ratio": round(pantry_ratio, 2),
            }
        )

    results.sort(key=lambda recipe: (not recipe["cookable"], len(recipe["missing"])))
    return results


def set_day_active_status(date_str: str, is_active: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_status (
                user_id INTEGER,
                date_str TEXT,
                is_active INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, date_str)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO daily_status (user_id, date_str, is_active)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, date_str) DO UPDATE SET is_active = excluded.is_active
            """,
            (LOCAL_DATA_ID, date_str, int(is_active)),
        )


def get_day_active_status(date_str: str) -> bool:
    with get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT is_active FROM daily_status WHERE user_id = ? AND date_str = ?",
                (LOCAL_DATA_ID, date_str),
            ).fetchone()
            return bool(row["is_active"]) if row else False
        except Exception:
            return False


def get_week_active_status(start_date: str) -> dict:
    with get_connection() as conn:
        try:
            rows = conn.execute(
                """
                SELECT date_str, is_active
                FROM daily_status
                WHERE user_id = ? AND date_str >= ? AND date_str < date(?, '+7 days')
                """,
                (LOCAL_DATA_ID, start_date, start_date),
            ).fetchall()
            return {row["date_str"]: bool(row["is_active"]) for row in rows}
        except Exception:
            return {}


def log_body_metrics(date_str: str, weight: float = None, bf: float = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO body_tracking (user_id, date_str, weight_kg, bf_pct)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, date_str) DO UPDATE SET
                weight_kg = excluded.weight_kg,
                bf_pct = excluded.bf_pct
            """,
            (LOCAL_DATA_ID, date_str, weight, bf),
        )

        if weight is not None:
            conn.execute("UPDATE user_profile SET weight_kg = ? WHERE user_id = ?", (weight, LOCAL_DATA_ID))
        if bf is not None:
            conn.execute("UPDATE user_profile SET current_bf_pct = ? WHERE user_id = ?", (bf, LOCAL_DATA_ID))


def get_body_history(limit: int = 30) -> list[BodyTrackingEntry]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, date_str, weight_kg, bf_pct
            FROM body_tracking
            WHERE user_id = ?
            ORDER BY date_str DESC
            LIMIT ?
            """,
            (LOCAL_DATA_ID, limit),
        ).fetchall()
        history = [
            BodyTrackingEntry(
                id=row["id"],
                log_date=row["date_str"],
                weight_kg=row["weight_kg"],
                bf_pct=row["bf_pct"],
            )
            for row in rows
        ]
        history.reverse()
        return history
