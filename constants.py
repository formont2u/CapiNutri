"""
constants.py — Toute la configuration statique de l'application.
"""

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

MEAL_TYPES = {
    "breakfast": "Petit-déjeuner",
    "lunch":     "Déjeuner",
    "dinner":    "Dîner",
    "snack":     "Collation",
    "other":     "Autre",
}

# --- NUTRITION & MACROS ---

NUTRIENT_FIELDS = [
    "kcal", "protein_g", "carbs_g", "fat_g",
    "sugars_g", "fiber_g",
    "saturated_g", "monounsat_g", "polyunsat_g",
    "sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "magnesium_mg", "zinc_mg",
    "vit_a_mcg", "vit_c_mg", "vit_d_mcg",
    "vit_b1_mg", "vit_b2_mg", "vit_b3_mg", "vit_b6_mg", "vit_b9_mcg", "vit_b12_mcg",
    "cholesterol_mg", "trans_fat_g", "omega3_g", "omega6_g",
    "phosphorus_mg", "selenium_mcg", "copper_mg", "manganese_mg",
    "vit_e_mg", "vit_k_mcg",
]

MACRO_FIELDS   = ["kcal", "protein_g", "carbs_g", "fat_g"]
CARB_FIELDS    = ["sugars_g", "fiber_g"]
FAT_FIELDS     = ["saturated_g", "monounsat_g", "polyunsat_g"]
MICRO_FIELDS   = ["sodium_mg", "calcium_mg", "iron_mg", "potassium_mg", "magnesium_mg", "zinc_mg"]
VITAMIN_FIELDS = ["vit_a_mcg", "vit_c_mg", "vit_d_mcg", "vit_e_mg", "vit_k_mcg",
                  "vit_b1_mg", "vit_b2_mg", "vit_b3_mg", "vit_b6_mg", "vit_b9_mcg", "vit_b12_mcg"]
USDA_FIELDS    = ["cholesterol_mg", "trans_fat_g", "omega3_g", "omega6_g",
                  "phosphorus_mg", "selenium_mcg", "copper_mg", "manganese_mg"]

NUTRIENT_LABELS = {
    "kcal": ("Calories", "kcal"), "protein_g": ("Protéines", "g"),
    "carbs_g": ("Glucides", "g"), "fat_g": ("Lipides", "g"),
    "sugars_g": ("Sucres", "g"), "fiber_g": ("Fibres", "g"),
    "saturated_g": ("Saturés", "g"), "monounsat_g": ("Mono-insaturés", "g"),
    "polyunsat_g": ("Poly-insaturés", "g"), "sodium_mg": ("Sodium", "mg"),
    "calcium_mg": ("Calcium", "mg"), "iron_mg": ("Fer", "mg"),
    "potassium_mg": ("Potassium", "mg"), "magnesium_mg": ("Magnésium", "mg"),
    "zinc_mg": ("Zinc", "mg"), "vit_a_mcg": ("Vit. A", "µg"),
    "vit_c_mg": ("Vit. C", "mg"), "vit_d_mcg": ("Vit. D", "µg"),
    "vit_e_mg": ("Vit. E", "mg"), "vit_k_mcg": ("Vit. K", "µg"),
    "vit_b1_mg": ("Vit. B1", "mg"), "vit_b2_mg": ("Vit. B2", "mg"),
    "vit_b3_mg": ("Vit. B3", "mg"), "vit_b6_mg": ("Vit. B6", "mg"),
    "vit_b9_mcg": ("Vit. B9 (Folate)", "µg"), "vit_b12_mcg": ("Vit. B12", "µg"),
    "cholesterol_mg": ("Cholestérol", "mg"), "trans_fat_g": ("Acides gras trans","g"),
    "omega3_g": ("Oméga-3", "g"), "omega6_g": ("Oméga-6", "g"),
    "phosphorus_mg": ("Phosphore", "mg"), "selenium_mcg": ("Sélénium", "µg"),
    "copper_mg": ("Cuivre", "mg"), "manganese_mg": ("Manganèse", "mg"),
}

RDI = {
    "kcal": 2000, "protein_g": 50, "carbs_g": 260, "fat_g": 70,
    "sugars_g": 50, "fiber_g": 30, "saturated_g": 20, "sodium_mg": 2300,
    "calcium_mg": 1000, "iron_mg": 14, "potassium_mg": 3500, "magnesium_mg": 375,
    "zinc_mg": 11, "vit_a_mcg": 800, "vit_c_mg": 80, "vit_d_mcg": 15,
    "vit_e_mg": 15, "vit_k_mcg": 120, "vit_b1_mg": 1.1, "vit_b2_mg": 1.4,
    "vit_b3_mg": 16, "vit_b6_mg": 1.4, "vit_b9_mcg": 200, "vit_b12_mcg": 2.4,
    "cholesterol_mg": 300, "trans_fat_g": 2, "omega3_g": 1.6, "omega6_g": 17,
    "phosphorus_mg": 700, "selenium_mcg": 55, "copper_mg": 0.9, "manganese_mg": 2.3,
}

MEAL_ICONS = {
    "breakfast": "bi-sunrise", 
    "lunch": "bi-sun",
    "dinner": "bi-moon-stars", 
    "snack": "bi-apple",
    "other": "bi-cup-hot"
}