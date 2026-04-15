package com.capynutri.app.domain

import com.capynutri.app.data.local.ProfileEntity
import com.capynutri.app.data.local.RecipeWithDetails
import kotlin.math.max
import kotlin.math.roundToInt

private val activityMultipliers = mapOf(
    "sedentary" to 1.2,
    "light" to 1.375,
    "moderate" to 1.55,
    "active" to 1.725,
    "very_active" to 1.9,
)

fun calculateNutritionStrategy(profile: ProfileEntity?): NutritionStrategy? {
    if (profile?.weightKg == null || profile.currentBfPct == null || profile.goalBfPct == null) {
        return null
    }

    val lbm = profile.weightKg * (1 - (profile.currentBfPct / 100.0))
    val bmr = 370 + (21.6 * lbm)
    val tdee = bmr * (activityMultipliers[profile.activityLevel] ?: 1.2)
    val diffBf = profile.currentBfPct - profile.goalBfPct

    val strategyData = when {
        diffBf > 3 -> StrategySeed("Seche (Cut)", "Deficit modere.", tdee - 400, lbm * 2.4, profile.weightKg * 0.8)
        diffBf < -2 -> StrategySeed("Prise de masse propre", "Leger surplus.", tdee + 250, lbm * 2.0, profile.weightKg * 1.0)
        diffBf > 0 -> StrategySeed("Recomposition corporelle", "Mini deficit.", tdee - 150, lbm * 2.2, profile.weightKg * 0.9)
        else -> StrategySeed("Maintien optimal", "Equilibre parfait.", tdee, lbm * 1.8, profile.weightKg * 1.0)
    }

    val carbs = max(0.0, (strategyData.kcal - (strategyData.protein * 4) - (strategyData.fat * 9)) / 4)
    val margin = when (profile.activityLevel) {
        "sedentary" -> 0.05
        "light" -> 0.10
        "moderate" -> 0.15
        "active" -> 0.20
        "very_active" -> 0.25
        else -> 0.10
    }

    val trainingKcal = strategyData.kcal * (1 + margin)
    val trainingCarbs = max(0.0, (trainingKcal - (strategyData.protein * 4) - (strategyData.fat * 9)) / 4)
    val restKcal = strategyData.kcal * (1 - margin)
    val restFat = strategyData.fat * (1 + margin / 2)
    val restCarbs = max(0.0, (restKcal - (strategyData.protein * 4) - (restFat * 9)) / 4)
    val meals = max(1, profile.mealsPerDay)
    val proteinPerMeal = (strategyData.protein / meals).roundToInt()

    val mealAdvice = when {
        proteinPerMeal > 45 -> "Lourd. Passe a ${max(3, (strategyData.protein / 35).roundToInt())} repas."
        proteinPerMeal < 25 -> "Faible. Regroupe un peu tes repas."
        else -> "Assimilation parfaite."
    }
    val mealStatus = if (proteinPerMeal in 25..45) "success" else "warning"

    return NutritionStrategy(
        strategy = strategyData.name,
        description = strategyData.description,
        lbm = (lbm * 10.0).roundToInt() / 10.0,
        tdee = tdee.roundToInt(),
        kcal = strategyData.kcal.roundToInt(),
        proteinG = strategyData.protein.roundToInt(),
        carbsG = carbs.roundToInt(),
        fatG = strategyData.fat.roundToInt(),
        training = MacroTargets(
            kcal = trainingKcal.roundToInt(),
            proteinG = strategyData.protein.roundToInt(),
            carbsG = trainingCarbs.roundToInt(),
            fatG = strategyData.fat.roundToInt(),
        ),
        rest = MacroTargets(
            kcal = restKcal.roundToInt(),
            proteinG = strategyData.protein.roundToInt(),
            carbsG = restCarbs.roundToInt(),
            fatG = restFat.roundToInt(),
        ),
        mealSplit = MealSplit(
            count = meals,
            kcal = (strategyData.kcal / meals).roundToInt(),
            proteinG = proteinPerMeal,
            carbsG = (carbs / meals).roundToInt(),
            fatG = (strategyData.fat / meals).roundToInt(),
            status = mealStatus,
            advice = mealAdvice,
        ),
    )
}

fun adaptRecipesForProfile(
    recipes: List<RecipeWithDetails>,
    profile: ProfileEntity?,
    strategy: NutritionStrategy?,
): List<AdaptedRecipeCard> {
    val targetMealKcal = strategy?.mealSplit?.kcal?.toDouble()
    return recipes.map { recipe ->
        val totalKcal = recipe.ingredients.sumOf { it.kcal ?: 0.0 }
        val totalProtein = recipe.ingredients.sumOf { it.proteinG ?: 0.0 }
        val baseServings = if (recipe.recipe.servings <= 0.0) 1.0 else recipe.recipe.servings
        val kcalPerServing = totalKcal / baseServings
        val proteinPerServing = totalProtein / baseServings
        val recommendedServings = if (targetMealKcal != null && kcalPerServing > 0) {
            ((targetMealKcal / kcalPerServing) * 10.0).roundToInt() / 10.0
        } else {
            null
        }

        AdaptedRecipeCard(
            recipeId = recipe.recipe.id,
            name = recipe.recipe.name,
            tags = recipe.tags.map { it.name },
            baseServings = baseServings,
            kcalPerServing = kcalPerServing,
            recommendedServings = recommendedServings,
            adaptedKcal = recommendedServings?.let { (kcalPerServing * it).roundToInt() },
            adaptedProteinG = recommendedServings?.let { (proteinPerServing * it).roundToInt() },
        )
    }
}

private data class StrategySeed(
    val name: String,
    val description: String,
    val kcal: Double,
    val protein: Double,
    val fat: Double,
)
