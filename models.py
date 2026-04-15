"""
models.py — Dataclasses pures pour toutes les entités.
La logique métier (algorithmes) a été séparée pour garder ce fichier propre.
"""

from dataclasses import dataclass, field
from typing import Optional
from constants import NUTRIENT_FIELDS

# ── 1. Le Mixin Magique 

@dataclass(kw_only=True)
class NutritionalMixin:
    """
    Cette classe regroupe tous les champs nutritionnels.
    N'importe quelle autre classe peut en hériter pour obtenir ces 34 champs instantanément.
    """
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

    @property
    def has_nutrition(self) -> bool:
        return self.kcal is not None

    def as_nutrient_dict(self, scale: float = 1.0) -> dict:
        """Retourne un dictionnaire pur des nutriments présents, mis à l'échelle."""
        return {
            f: round(getattr(self, f) * scale, 3)
            for f in NUTRIENT_FIELDS
            if getattr(self, f) is not None
        }


# ── 2. Entités de Recettes ────────────────────────────────────────────────────

@dataclass
class Ingredient(NutritionalMixin):
    name: str
    quantity: float
    unit: str = ""
    library_id: Optional[int] = None
    id: Optional[int] = None
    recipe_id: Optional[int] = None

    def display(self, scale: float = 1.0) -> str:
        qty = self.quantity * scale
        qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.2f}".rstrip("0")
        unit_str = f" {self.unit}" if self.unit else ""
        return f"{qty_str}{unit_str} {self.name}"


@dataclass
class Recipe:
    name: str
    servings: float = 1.0
    instructions: str = ""
    ingredients: list[Ingredient] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    id: Optional[int] = None

    def scale_factor(self, desired_servings: float) -> float:
        return desired_servings / self.servings if self.servings else 1.0


# ── 3. Utilisateur et Profil ──────────────────────────────────────────────────

@dataclass
class UserProfile:
    id: int = 1
    name: str = ""
    weight_kg: float = 0.0
    height_cm: float = 0.0
    age: int = 0
    sex: str = "M"
    activity_level: str = "sedentary"
    goal: str = "maintain"
    meals_per_day: int = 3
    current_bf_pct: Optional[float] = None
    goal_weight_kg: Optional[float] = None
    goal_bf_pct: Optional[float] = None

@dataclass
class BodyTrackingEntry:
    log_date: str
    weight_kg: Optional[float] = None
    bf_pct: Optional[float] = None
    id: Optional[int] = None


# ── 4. Entités du Journal (Logs) ──────────────────────────────────────────────

@dataclass
class FoodLogEntry(NutritionalMixin):
    log_date: str  # Format ISO (YYYY-MM-DD)
    label: str
    servings: float = 1.0
    meal_type: str = "other"
    recipe_id: Optional[int] = None
    id: Optional[int] = None

    def nutrient_dict(self) -> dict:
        return {f: getattr(self, f) or 0.0 for f in NUTRIENT_FIELDS}


@dataclass
class ExerciseEntry:
    log_date: str
    name: str
    kcal_burned: float
    duration_min: Optional[int] = None
    rpe: int = 5                   # NOUVEAU : Intensité de 1 à 10
    exercise_type: str = "cardio"  # NOUVEAU : 'cardio', 'musculation', ou 'recuperation'
    id: Optional[int] = None
