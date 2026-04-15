package com.capynutri.app.domain

data class MacroTargets(
    val kcal: Int,
    val proteinG: Int,
    val carbsG: Int,
    val fatG: Int,
)

data class MealSplit(
    val count: Int,
    val kcal: Int,
    val proteinG: Int,
    val carbsG: Int,
    val fatG: Int,
    val status: String,
    val advice: String,
)

data class NutritionStrategy(
    val strategy: String,
    val description: String,
    val lbm: Double,
    val tdee: Int,
    val kcal: Int,
    val proteinG: Int,
    val carbsG: Int,
    val fatG: Int,
    val training: MacroTargets,
    val rest: MacroTargets,
    val mealSplit: MealSplit,
)

data class AdaptedRecipeCard(
    val recipeId: Long,
    val name: String,
    val tags: List<String>,
    val baseServings: Double,
    val kcalPerServing: Double,
    val recommendedServings: Double?,
    val adaptedKcal: Int?,
    val adaptedProteinG: Int?,
)
