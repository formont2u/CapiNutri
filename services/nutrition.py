"""
services/nutrition.py — La Logique Métier (Le Cerveau).
Contient tous les algorithmes de calcul complexes détachés des modèles.
"""
from typing import Optional
from models import Recipe, UserProfile
from db import NUTRIENT_FIELDS
from constants import ACTIVITY_MULTIPLIERS
from models import FoodLogEntry

def sum_nutrients(items: list[dict], scale: float = 1.0) -> dict:
    """Additionne une liste de dictionnaires de nutriments en appliquant un ratio."""
    totals = {f: 0.0 for f in NUTRIENT_FIELDS}
    for item in items:
        for f in NUTRIENT_FIELDS:
            v = item.get(f)
            if v is not None:
                totals[f] += v * scale
    return {k: round(v, 2) for k, v in totals.items()}

def get_recipe_nutrition_per_serving(recipe: Recipe, current_servings: Optional[float] = None) -> Optional[dict]:
    """Calcule les nutriments d'une recette pour une portion donnée."""
    if not any(i.has_nutrition for i in recipe.ingredients):
        return None
        
    servings = current_servings or recipe.servings
    scale = (servings / recipe.servings) if recipe.servings else 1.0
    
    # On récupère les nutriments de tous les ingrédients
    ingredients_nutr = [i.as_nutrient_dict() for i in recipe.ingredients if i.has_nutrition]
    total = sum_nutrients(ingredients_nutr, scale)
    
    if not total or servings == 0:
        return None
        
    return {k: round(v / servings, 2) for k, v in total.items()}

def calculate_nutri_score(recipe: Recipe) -> Optional[dict]:
    """
    Calcule un Nutri-Score simplifié (A→E) basé sur la nutrition par portion.
    """
    nutr = get_recipe_nutrition_per_serving(recipe)
    if not nutr:
        return None

    def _pts(val, thresholds):
        if val is None: return 0
        for i, t in enumerate(thresholds):
            if val <= t: return i
        return len(thresholds)

    kcal = nutr.get("kcal") or 0
    kj = kcal * 4.184
    n_energy    = _pts(kj,                     [335,670,1005,1340,1675,2010,2345,2680,3015,3350])
    n_sugars    = _pts(nutr.get("sugars_g"),    [4.5,9,13.5,18,22.5,27,31,36,40,45])
    n_saturated = _pts(nutr.get("saturated_g"), [1,2,3,4,5,6,7,8,9,10])
    n_sodium    = _pts(nutr.get("sodium_mg"),   [90,180,270,360,450,540,630,720,810,900])
    N = n_energy + n_sugars + n_saturated + n_sodium

    p_fiber   = _pts(nutr.get("fiber_g"),   [0.9,1.9,2.8,3.7,4.7])
    p_protein = _pts(nutr.get("protein_g"), [1.6,3.2,4.8,6.4,8.0])
    P = p_fiber + p_protein

    score = N - P

    if   score <= -1: grade, bg, fg = "A", "#2e7d32", "#fff"
    elif score <=  2: grade, bg, fg = "B", "#7cb342", "#fff"
    elif score <= 10: grade, bg, fg = "C", "#f9a825", "#000"
    elif score <= 18: grade, bg, fg = "D", "#ef6c00", "#fff"
    else:             grade, bg, fg = "E", "#c62828", "#fff"

    return {"grade": grade, "score": score, "color": bg, "text_color": fg}

def calculate_smart_strategy(profile: UserProfile) -> Optional[dict]:
    """Algorithme de Katch-McArdle pour assigner une stratégie scientifique (Carb Cycling)."""
    if not profile.weight_kg or not profile.current_bf_pct or not profile.goal_bf_pct:
        return None
        
    lbm = profile.weight_kg * (1 - (profile.current_bf_pct / 100))
    bmr = 370 + (21.6 * lbm)
    
    tdee = bmr * ACTIVITY_MULTIPLIERS.get(profile.activity_level, 1.2)
    diff_bf = profile.current_bf_pct - profile.goal_bf_pct
    
    # Détermination de l'objectif
    if diff_bf > 3:
        strategy, desc, kcal, protein, fat = "Sèche (Cut)", "Déficit modéré.", tdee - 400, lbm * 2.4, profile.weight_kg * 0.8
    elif diff_bf < -2:
        strategy, desc, kcal, protein, fat = "Prise de Masse Propre", "Léger surplus.", tdee + 250, lbm * 2.0, profile.weight_kg * 1.0
    elif diff_bf > 0:
        strategy, desc, kcal, protein, fat = "Recomposition Corporelle", "Mini déficit.", tdee - 150, lbm * 2.2, profile.weight_kg * 0.9
    else:
        strategy, desc, kcal, protein, fat = "Maintien Optimal", "Équilibre parfait.", tdee, lbm * 1.8, profile.weight_kg * 1.0
        
    carbs = max(0, (kcal - (protein * 4) - (fat * 9)) / 4)
    
    # Carb Cycling Dynamique
    margin = {"sedentary": 0.05, "light": 0.10, "moderate": 0.15, "active": 0.20, "very_active": 0.25}.get(profile.activity_level, 0.10)

    kcal_on, protein_on, fat_on = kcal * (1 + margin), protein, fat
    carbs_on = max(0, (kcal_on - (protein_on * 4) - (fat_on * 9)) / 4)

    kcal_off, protein_off, fat_off = kcal * (1 - margin), protein, fat * (1 + (margin / 2))
    carbs_off = max(0, (kcal_off - (protein_off * 4) - (fat_off * 9)) / 4)

    # Meal Split
    meals = max(1, profile.meals_per_day)
    protein_per_meal = round(protein / meals)
    
    if protein_per_meal > 45:
        status, advice = "warning", f"Lourd. Passez à {max(3, round(protein / 35))} repas."
    elif protein_per_meal < 25:
        status, advice = "warning", "Faible. Regroupez vos repas."
    else:
        status, advice = "success", "Assimilation parfaite !"

    return {
        "strategy": strategy, "description": desc, "lbm": round(lbm, 1), "tdee": round(tdee),
        "kcal": round(kcal), "protein_g": round(protein), "fat_g": round(fat), "carbs_g": round(carbs),
        "training": {"kcal": round(kcal_on), "protein_g": round(protein_on), "fat_g": round(fat_on), "carbs_g": round(carbs_on)},
        "rest": {"kcal": round(kcal_off), "protein_g": round(protein_off), "fat_g": round(fat_off), "carbs_g": round(carbs_off)},
        "meal_split": {"count": meals, "kcal": round(kcal/meals), "protein_g": protein_per_meal, "carbs_g": round(carbs/meals), "fat_g": round(fat/meals), "status": status, "advice": advice}
    }

def get_effective_goals(profile: UserProfile) -> dict:
    """Récupère la stratégie intelligente ou renvoie un fallback classique."""
    smart = calculate_smart_strategy(profile)
    return smart if smart else {"kcal": 2000, "protein_g": 100, "carbs_g": 200, "fat_g": 60}

def sum_day_nutrition(entries: list[FoodLogEntry]) -> dict:
    """Additionne les nutriments de toutes les entrées du journal pour une journée."""
    totals = {f: 0.0 for f in NUTRIENT_FIELDS}
    for e in entries:
        for f in NUTRIENT_FIELDS:
            totals[f] += getattr(e, f) or 0.0
    return {k: round(v, 2) for k, v in totals.items()}