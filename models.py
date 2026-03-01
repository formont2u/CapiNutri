"""
models.py — Dataclasses for all entities.
"""

from dataclasses import dataclass, field
from typing import Optional
from db import NUTRIENT_FIELDS, NUTRIENT_LABELS, RDI, MACRO_FIELDS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sum_nutrients(items: list[dict], scale: float = 1.0) -> dict:
    """Sum a list of nutrient dicts, applying scale."""
    totals = {f: 0.0 for f in NUTRIENT_FIELDS}
    for item in items:
        for f in NUTRIENT_FIELDS:
            v = item.get(f)
            if v is not None:
                totals[f] += v * scale
    return {k: round(v, 2) for k, v in totals.items()}


# ── Ingredient ────────────────────────────────────────────────────────────────

@dataclass
class Ingredient:
    name: str
    quantity: float
    unit: str = ""
    # All nutrients (values for the stated quantity, not per 100g)
    kcal: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    sugars_g: Optional[float] = None
    fiber_g: Optional[float] = None
    saturated_g: Optional[float] = None
    monounsat_g: Optional[float] = None
    polyunsat_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    magnesium_mg: Optional[float] = None
    zinc_mg: Optional[float] = None
    vit_a_mcg: Optional[float] = None
    vit_c_mg: Optional[float] = None
    vit_d_mcg: Optional[float] = None
    vit_b1_mg: Optional[float] = None
    vit_b2_mg: Optional[float] = None
    vit_b3_mg: Optional[float] = None
    vit_b6_mg: Optional[float] = None
    vit_b9_mcg: Optional[float] = None
    vit_b12_mcg: Optional[float] = None
    # USDA-enhanced fields
    cholesterol_mg: Optional[float] = None
    trans_fat_g:    Optional[float] = None
    omega3_g:       Optional[float] = None
    omega6_g:       Optional[float] = None
    phosphorus_mg:  Optional[float] = None
    selenium_mcg:   Optional[float] = None
    copper_mg:      Optional[float] = None
    manganese_mg:   Optional[float] = None
    vit_e_mg:       Optional[float] = None
    vit_k_mcg:      Optional[float] = None
    id: Optional[int] = None
    recipe_id: Optional[int] = None

    @property
    def has_nutrition(self) -> bool:
        return self.kcal is not None

    def as_nutrient_dict(self, scale: float = 1.0) -> dict:
        return {
            f: round(getattr(self, f) * scale, 3)
            for f in NUTRIENT_FIELDS
            if getattr(self, f) is not None
        }

    def display(self, scale: float = 1.0) -> str:
        qty = self.quantity * scale
        qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.2f}".rstrip("0")
        unit_str = f" {self.unit}" if self.unit else ""
        return f"{qty_str}{unit_str} {self.name}"


# ── Recipe ────────────────────────────────────────────────────────────────────

@dataclass
class Recipe:
    name: str
    servings: float = 1.0
    instructions: str = ""
    category: Optional[str] = None
    category_id: Optional[int] = None
    ingredients: list[Ingredient] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)   # tag names
    id: Optional[int] = None

    def scale_factor(self, desired_servings: float) -> float:
        return desired_servings / self.servings if self.servings else 1.0

    @property
    def has_nutrition(self) -> bool:
        return any(i.has_nutrition for i in self.ingredients)

    def total_nutrition(self, scale: float = 1.0) -> Optional[dict]:
        if not self.has_nutrition:
            return None
        return _sum_nutrients(
            [i.as_nutrient_dict() for i in self.ingredients if i.has_nutrition],
            scale=scale
        )

    def nutrition_per_serving(self, current_servings: Optional[float] = None) -> Optional[dict]:
        servings = current_servings or self.servings
        scale = self.scale_factor(servings)
        total = self.total_nutrition(scale)
        if not total or servings == 0:
            return None
        return {k: round(v / servings, 2) for k, v in total.items()}

    def nutri_score(self) -> Optional[dict]:
        """
        Simplified Nutri-Score (A→E) based on per-serving nutrition.
        Returns {"grade": "A", "score": -3, "color": "#...", "text_color": "#..."}
        or None if no nutrition data.
        """
        nutr = self.nutrition_per_serving()
        if not nutr:
            return None

        # ── Negative points (higher = worse) ─────────────────────────────────
        def _pts(val, thresholds):
            """Score val against ascending threshold list (0-indexed = 1pt)."""
            if val is None:
                return 0
            for i, t in enumerate(thresholds):
                if val <= t:
                    return i
            return len(thresholds)

        kcal = nutr.get("kcal") or 0
        # Energy in kJ (1 kcal = 4.184 kJ), thresholds per serving ÷ ~2 (rough scale)
        kj = kcal * 4.184
        n_energy   = _pts(kj,           [335,670,1005,1340,1675,2010,2345,2680,3015,3350])
        n_sugars   = _pts(nutr.get("sugars_g"),    [4.5,9,13.5,18,22.5,27,31,36,40,45])
        n_saturated= _pts(nutr.get("saturated_g"), [1,2,3,4,5,6,7,8,9,10])
        n_sodium   = _pts(nutr.get("sodium_mg"),   [90,180,270,360,450,540,630,720,810,900])
        N = n_energy + n_sugars + n_saturated + n_sodium

        # ── Positive points (higher = better) ────────────────────────────────
        p_fiber   = _pts(nutr.get("fiber_g"),   [0.9,1.9,2.8,3.7,4.7])
        p_protein = _pts(nutr.get("protein_g"), [1.6,3.2,4.8,6.4,8.0])
        P = p_fiber + p_protein

        score = N - P

        # ── Grade ─────────────────────────────────────────────────────────────
        if   score <= -1: grade, bg, fg = "A", "#2e7d32", "#fff"
        elif score <=  2: grade, bg, fg = "B", "#7cb342", "#fff"
        elif score <= 10: grade, bg, fg = "C", "#f9a825", "#000"
        elif score <= 18: grade, bg, fg = "D", "#ef6c00", "#fff"
        else:             grade, bg, fg = "E", "#c62828", "#fff"

        return {"grade": grade, "score": score, "color": bg, "text_color": fg}


# ── User Profile ──────────────────────────────────────────────────────────────

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light":     1.375,
    "moderate":  1.55,
    "active":    1.725,
    "very_active": 1.9,
}
ACTIVITY_LABELS = {
    "sedentary":   "Sédentaire (peu ou pas d'exercice)",
    "light":       "Légèrement actif (1–3 j/semaine)",
    "moderate":    "Modérément actif (3–5 j/semaine)",
    "active":      "Très actif (6–7 j/semaine)",
    "very_active": "Extrêmement actif (sport + travail physique)",
}
GOAL_LABELS = {
    "maintain": "Maintien du poids",
    "cut":      "Perte de poids (−20%)",
    "bulk":     "Prise de masse (+15%)",
}
GOAL_MODIFIERS = {"maintain": 1.0, "cut": 0.80, "bulk": 1.15}


@dataclass
class UserProfile:
    id: int = 1
    name: str = ""
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    sex: str = "M"  # 'M' or 'F'
    activity_level: str = "moderate"
    goal: str = "maintain"
    # Manual overrides (None = use calculated)
    goal_kcal: Optional[float] = None
    goal_protein_g: Optional[float] = None
    goal_carbs_g: Optional[float] = None
    goal_fat_g: Optional[float] = None
    meals_per_day: int = 3  # 3 or 4 — drives meal plan slots

    def bmr(self) -> Optional[float]:
        """Mifflin-St Jeor BMR."""
        if not all([self.weight_kg, self.height_cm, self.age]):
            return None
        base = 10 * self.weight_kg + 6.25 * self.height_cm - 5 * self.age
        return base + 5 if self.sex == "M" else base - 161

    def tdee(self) -> Optional[float]:
        bmr = self.bmr()
        if bmr is None:
            return None
        mult = ACTIVITY_MULTIPLIERS.get(self.activity_level, 1.55)
        return round(bmr * mult, 0)

    def suggested_goal_kcal(self) -> Optional[float]:
        tdee = self.tdee()
        if tdee is None:
            return None
        return round(tdee * GOAL_MODIFIERS.get(self.goal, 1.0), 0)

    def effective_goals(self) -> dict:
        """Return active goals — manual override or calculated defaults."""
        kcal = self.goal_kcal or self.suggested_goal_kcal() or 2000
        # Default macro split: 30% protein, 40% carbs, 30% fat
        protein = self.goal_protein_g or round(kcal * 0.30 / 4, 0)
        carbs   = self.goal_carbs_g   or round(kcal * 0.40 / 4, 0)
        fat     = self.goal_fat_g     or round(kcal * 0.30 / 9, 0)
        return {
            "kcal": kcal,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
        }


# ── Food Log ──────────────────────────────────────────────────────────────────

MEAL_TYPES = {
    "breakfast": "Petit-déjeuner",
    "lunch":     "Déjeuner",
    "dinner":    "Dîner",
    "snack":     "Collation",
    "other":     "Autre",
}


@dataclass
class FoodLogEntry:
    log_date: str          # ISO date string
    label: str
    servings: float = 1.0
    meal_type: str = "other"
    recipe_id: Optional[int] = None
    id: Optional[int] = None
    # Cached nutrition
    kcal: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    sugars_g: Optional[float] = None
    fiber_g: Optional[float] = None
    saturated_g: Optional[float] = None
    monounsat_g: Optional[float] = None
    polyunsat_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    potassium_mg: Optional[float] = None
    magnesium_mg: Optional[float] = None
    zinc_mg: Optional[float] = None
    vit_a_mcg: Optional[float] = None
    vit_c_mg: Optional[float] = None
    vit_d_mcg: Optional[float] = None
    vit_b1_mg: Optional[float] = None
    vit_b2_mg: Optional[float] = None
    vit_b3_mg: Optional[float] = None
    vit_b6_mg: Optional[float] = None
    vit_b9_mcg: Optional[float] = None
    vit_b12_mcg: Optional[float] = None
    # USDA-enhanced
    cholesterol_mg: Optional[float] = None
    trans_fat_g:    Optional[float] = None
    omega3_g:       Optional[float] = None
    omega6_g:       Optional[float] = None
    phosphorus_mg:  Optional[float] = None
    selenium_mcg:   Optional[float] = None
    copper_mg:      Optional[float] = None
    manganese_mg:   Optional[float] = None
    vit_e_mg:       Optional[float] = None
    vit_k_mcg:      Optional[float] = None

    def nutrient_dict(self) -> dict:
        return {f: getattr(self, f) or 0.0 for f in NUTRIENT_FIELDS}


@dataclass
class ExerciseEntry:
    log_date: str
    name: str
    kcal_burned: float
    duration_min: Optional[int] = None
    id: Optional[int] = None