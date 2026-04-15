package com.capynutri.app.data.repository

import com.capynutri.app.data.local.CapyDatabase
import com.capynutri.app.data.local.IngredientLibraryEntity
import com.capynutri.app.data.local.IngredientLibrarySeed
import com.capynutri.app.data.local.IngredientEntity
import com.capynutri.app.data.local.IngredientUnitEntity
import com.capynutri.app.data.local.MealPlanSeed
import com.capynutri.app.data.local.PantryItemEntity
import com.capynutri.app.data.local.ProfileEntity
import com.capynutri.app.data.local.RecipeEntity
import com.capynutri.app.data.local.RecipeSeed
import com.capynutri.app.data.local.TagEntity
import java.time.LocalDate

class CapyRepository(private val database: CapyDatabase) {
    private val dao = database.capyDao()

    fun observeRecipes() = dao.observeRecipes()
    fun observeLibrary() = dao.observeLibrary()
    fun observePantry() = dao.observePantry()
    fun observePlanForDate(date: String) = dao.observePlanForDate(date)
    fun observeProfile() = dao.observeProfile()

    suspend fun saveProfile(profile: ProfileEntity) {
        dao.upsertProfile(profile)
    }

    suspend fun seedDemoData() {
        val today = LocalDate.now()
        dao.replaceAll(
            profile = ProfileEntity(
                name = "Capy Local",
                weightKg = 78.0,
                heightCm = 178.0,
                age = 29,
                sex = "M",
                activityLevel = "moderate",
                goal = "maintain",
                mealsPerDay = 4,
                currentBfPct = 18.0,
                goalWeightKg = 75.0,
                goalBfPct = 12.0,
            ),
            library = sampleLibrary(),
            tags = defaultTags(),
            recipes = sampleRecipes(),
            pantry = samplePantry(),
            plan = listOf(
                MealPlanSeed(today.toString(), "lunch", "Salmon Power Bowl"),
                MealPlanSeed(today.toString(), "dinner", "Tomato Egg Noodles"),
            ),
        )
    }

    private fun defaultTags() = listOf(
        TagEntity(name = "breakfast", colorHex = "#F59F00", iconName = "wb_sunny", isDefault = true),
        TagEntity(name = "lunch", colorHex = "#0D6EFD", iconName = "light_mode", isDefault = true),
        TagEntity(name = "dinner", colorHex = "#6F42C1", iconName = "dark_mode", isDefault = true),
        TagEntity(name = "snack", colorHex = "#FD7E14", iconName = "coffee", isDefault = true),
        TagEntity(name = "high-protein", colorHex = "#E03131", iconName = "bolt", isDefault = true),
        TagEntity(name = "quick", colorHex = "#6C757D", iconName = "schedule", isDefault = true),
        TagEntity(name = "sauce", colorHex = "#B35C1E", iconName = "water_drop", isDefault = true),
        TagEntity(name = "soup", colorHex = "#A66A2C", iconName = "soup_kitchen", isDefault = true),
    )

    private fun sampleLibrary(): List<IngredientLibrarySeed> = listOf(
        IngredientLibrarySeed(
            ingredient = IngredientLibraryEntity(
                name = "Tomato",
                defaultUnit = "piece",
                kcalPer100 = 18.0,
                carbsPer100 = 3.9,
                proteinPer100 = 0.9,
                densityGPerMl = 0.95,
            ),
            units = listOf(
                IngredientUnitEntity(ingredientId = 0, unitName = "piece", gramsPerUnit = 120.0, isDefault = true),
                IngredientUnitEntity(ingredientId = 0, unitName = "small piece", gramsPerUnit = 90.0),
            ),
        ),
        IngredientLibrarySeed(
            ingredient = IngredientLibraryEntity(
                name = "Egg",
                defaultUnit = "piece",
                kcalPer100 = 143.0,
                proteinPer100 = 12.6,
                fatPer100 = 9.5,
            ),
            units = listOf(
                IngredientUnitEntity(ingredientId = 0, unitName = "piece", gramsPerUnit = 55.0, isDefault = true),
            ),
        ),
        IngredientLibrarySeed(
            ingredient = IngredientLibraryEntity(
                name = "Salmon fillet",
                defaultUnit = "piece",
                kcalPer100 = 208.0,
                proteinPer100 = 20.0,
                fatPer100 = 13.0,
            ),
            units = listOf(
                IngredientUnitEntity(ingredientId = 0, unitName = "piece", gramsPerUnit = 140.0, isDefault = true),
            ),
        ),
        IngredientLibrarySeed(
            ingredient = IngredientLibraryEntity(
                name = "Soy sauce",
                defaultUnit = "tbsp",
                kcalPer100 = 53.0,
                proteinPer100 = 8.1,
                carbsPer100 = 4.9,
                densityGPerMl = 1.16,
            ),
            units = listOf(
                IngredientUnitEntity(ingredientId = 0, unitName = "tbsp", mlPerUnit = 15.0, isDefault = true),
                IngredientUnitEntity(ingredientId = 0, unitName = "tsp", mlPerUnit = 5.0),
            ),
        ),
        IngredientLibrarySeed(
            ingredient = IngredientLibraryEntity(
                name = "Milk",
                defaultUnit = "ml",
                kcalPer100 = 46.0,
                proteinPer100 = 3.4,
                carbsPer100 = 4.8,
                fatPer100 = 1.5,
                densityGPerMl = 1.03,
            ),
            units = listOf(
                IngredientUnitEntity(ingredientId = 0, unitName = "cup", mlPerUnit = 250.0, isDefault = true),
            ),
        ),
        IngredientLibrarySeed(
            ingredient = IngredientLibraryEntity(
                name = "Olive oil",
                defaultUnit = "ml",
                kcalPer100 = 884.0,
                fatPer100 = 100.0,
                densityGPerMl = 0.92,
            ),
            units = listOf(
                IngredientUnitEntity(ingredientId = 0, unitName = "tbsp", mlPerUnit = 15.0, isDefault = true),
                IngredientUnitEntity(ingredientId = 0, unitName = "tsp", mlPerUnit = 5.0),
            ),
        ),
    )

    private fun sampleRecipes() = listOf(
        RecipeSeed(
            recipe = RecipeEntity(
                name = "Salmon Power Bowl",
                servings = 2.0,
                instructions = "Roast salmon. Cook rice. Assemble with cucumber and yogurt sauce.",
            ),
            ingredients = listOf(
                IngredientEntity(recipeId = 0, name = "Salmon fillet", quantity = 280.0, unit = "g", kcal = 580.0, proteinG = 56.0, fatG = 36.0),
                IngredientEntity(recipeId = 0, name = "Rice", quantity = 150.0, unit = "g", kcal = 540.0, carbsG = 120.0, proteinG = 10.0),
                IngredientEntity(recipeId = 0, name = "Cucumber", quantity = 1.0, unit = "piece", kcal = 30.0, carbsG = 6.0),
                IngredientEntity(recipeId = 0, name = "Yogurt sauce", quantity = 120.0, unit = "g", kcal = 90.0, proteinG = 6.0, fatG = 4.0),
            ),
            tagNames = listOf("lunch", "high-protein"),
        ),
        RecipeSeed(
            recipe = RecipeEntity(
                name = "Tomato Egg Noodles",
                servings = 2.0,
                instructions = "Saute tomato base. Cook noodles. Fold in eggs and finish with sauce.",
            ),
            ingredients = listOf(
                IngredientEntity(recipeId = 0, name = "Egg noodles", quantity = 180.0, unit = "g", kcal = 640.0, carbsG = 110.0, proteinG = 20.0),
                IngredientEntity(recipeId = 0, name = "Egg", quantity = 2.0, unit = "piece", kcal = 140.0, proteinG = 12.0, fatG = 10.0),
                IngredientEntity(recipeId = 0, name = "Tomato", quantity = 3.0, unit = "piece", kcal = 60.0, carbsG = 12.0),
                IngredientEntity(recipeId = 0, name = "Soy sauce", quantity = 1.0, unit = "tbsp", kcal = 10.0),
            ),
            tagNames = listOf("dinner", "quick", "sauce"),
        ),
    )

    private fun samplePantry() = listOf(
        PantryItemEntity(name = "Salmon fillet", quantity = 2.0, unit = "piece"),
        PantryItemEntity(name = "Egg", quantity = 6.0, unit = "piece"),
        PantryItemEntity(name = "Rice", quantity = 500.0, unit = "g"),
        PantryItemEntity(name = "Soy sauce", quantity = 250.0, unit = "ml"),
        PantryItemEntity(name = "Tomato", quantity = 4.0, unit = "piece"),
    )
}
