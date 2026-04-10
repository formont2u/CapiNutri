"""
services/nutrition.py - Business nutrition logic.
"""

from typing import Optional

from constants import ACTIVITY_MULTIPLIERS, NUTRIENT_FIELDS
from models import FoodLogEntry, Recipe, UserProfile


def sum_nutrients(items: list[dict], scale: float = 1.0) -> dict:
    """Add nutrient dictionaries together while applying an optional scale."""
    totals = {field: 0.0 for field in NUTRIENT_FIELDS}
    for item in items:
        for field in NUTRIENT_FIELDS:
            value = item.get(field)
            if value is not None:
                totals[field] += value * scale
    return {key: round(value, 2) for key, value in totals.items()}


def get_recipe_nutrition_per_serving(recipe: Recipe, current_servings: Optional[float] = None) -> Optional[dict]:
    """Return a recipe's nutrients for the requested serving count."""
    if not any(ingredient.has_nutrition for ingredient in recipe.ingredients):
        return None

    servings = current_servings or recipe.servings
    scale = (servings / recipe.servings) if recipe.servings else 1.0
    ingredient_nutrients = [
        ingredient.as_nutrient_dict()
        for ingredient in recipe.ingredients
        if ingredient.has_nutrition
    ]
    total = sum_nutrients(ingredient_nutrients, scale)

    if not total or servings == 0:
        return None

    return {key: round(value / servings, 2) for key, value in total.items()}


def calculate_smart_strategy(profile: UserProfile) -> Optional[dict]:
    """Compute a Katch-McArdle-based nutrition strategy."""
    if not profile.weight_kg or not profile.current_bf_pct or not profile.goal_bf_pct:
        return None

    lbm = profile.weight_kg * (1 - (profile.current_bf_pct / 100))
    bmr = 370 + (21.6 * lbm)
    tdee = bmr * ACTIVITY_MULTIPLIERS.get(profile.activity_level, 1.2)
    diff_bf = profile.current_bf_pct - profile.goal_bf_pct

    if diff_bf > 3:
        strategy, desc, kcal, protein, fat = "Seche (Cut)", "Deficit modere.", tdee - 400, lbm * 2.4, profile.weight_kg * 0.8
    elif diff_bf < -2:
        strategy, desc, kcal, protein, fat = "Prise de Masse Propre", "Leger surplus.", tdee + 250, lbm * 2.0, profile.weight_kg * 1.0
    elif diff_bf > 0:
        strategy, desc, kcal, protein, fat = "Recomposition Corporelle", "Mini deficit.", tdee - 150, lbm * 2.2, profile.weight_kg * 0.9
    else:
        strategy, desc, kcal, protein, fat = "Maintien Optimal", "Equilibre parfait.", tdee, lbm * 1.8, profile.weight_kg * 1.0

    carbs = max(0, (kcal - (protein * 4) - (fat * 9)) / 4)
    margin = {
        "sedentary": 0.05,
        "light": 0.10,
        "moderate": 0.15,
        "active": 0.20,
        "very_active": 0.25,
    }.get(profile.activity_level, 0.10)

    kcal_on, protein_on, fat_on = kcal * (1 + margin), protein, fat
    carbs_on = max(0, (kcal_on - (protein_on * 4) - (fat_on * 9)) / 4)

    kcal_off, protein_off, fat_off = kcal * (1 - margin), protein, fat * (1 + (margin / 2))
    carbs_off = max(0, (kcal_off - (protein_off * 4) - (fat_off * 9)) / 4)

    meals = max(1, profile.meals_per_day)
    protein_per_meal = round(protein / meals)

    if protein_per_meal > 45:
        status, advice = "warning", f"Lourd. Passez a {max(3, round(protein / 35))} repas."
    elif protein_per_meal < 25:
        status, advice = "warning", "Faible. Regroupez vos repas."
    else:
        status, advice = "success", "Assimilation parfaite !"

    return {
        "strategy": strategy,
        "description": desc,
        "lbm": round(lbm, 1),
        "tdee": round(tdee),
        "kcal": round(kcal),
        "protein_g": round(protein),
        "fat_g": round(fat),
        "carbs_g": round(carbs),
        "training": {
            "kcal": round(kcal_on),
            "protein_g": round(protein_on),
            "fat_g": round(fat_on),
            "carbs_g": round(carbs_on),
        },
        "rest": {
            "kcal": round(kcal_off),
            "protein_g": round(protein_off),
            "fat_g": round(fat_off),
            "carbs_g": round(carbs_off),
        },
        "meal_split": {
            "count": meals,
            "kcal": round(kcal / meals),
            "protein_g": protein_per_meal,
            "carbs_g": round(carbs / meals),
            "fat_g": round(fat / meals),
            "status": status,
            "advice": advice,
        },
    }


def get_effective_goals(profile: UserProfile) -> dict:
    """Return the smart strategy when available, otherwise a safe fallback."""
    smart = calculate_smart_strategy(profile)
    return smart if smart else {"kcal": 2000, "protein_g": 100, "carbs_g": 200, "fat_g": 60}


def sum_day_nutrition(entries: list[FoodLogEntry]) -> dict:
    """Add up all nutrients for a day's logged entries."""
    totals = {field: 0.0 for field in NUTRIENT_FIELDS}
    for entry in entries:
        for field in NUTRIENT_FIELDS:
            totals[field] += getattr(entry, field) or 0.0
    return {key: round(value, 2) for key, value in totals.items()}
