package com.capynutri.app.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface CapyDao {
    @Transaction
    @Query("SELECT * FROM recipes ORDER BY name")
    fun observeRecipes(): Flow<List<RecipeWithDetails>>

    @Transaction
    @Query("SELECT * FROM ingredient_library ORDER BY name")
    fun observeLibrary(): Flow<List<IngredientLibraryWithUnits>>

    @Query("SELECT * FROM pantry_items ORDER BY name")
    fun observePantry(): Flow<List<PantryItemEntity>>

    @Transaction
    @Query("SELECT * FROM meal_plan_entries WHERE planDate = :date ORDER BY mealType")
    fun observePlanForDate(date: String): Flow<List<MealPlanWithRecipe>>

    @Query("SELECT * FROM profile WHERE id = 1")
    fun observeProfile(): Flow<ProfileEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertProfile(profile: ProfileEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertRecipe(recipe: RecipeEntity): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertIngredients(ingredients: List<IngredientEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLibraryIngredients(ingredients: List<IngredientLibraryEntity>): List<Long>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertIngredientUnits(units: List<IngredientUnitEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTags(tags: List<TagEntity>): List<Long>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertRecipeTags(crossRefs: List<RecipeTagCrossRef>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPantryItems(items: List<PantryItemEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPlanEntries(entries: List<MealPlanEntryEntity>)

    @Query("DELETE FROM pantry_items")
    suspend fun clearPantry()

    @Query("DELETE FROM meal_plan_entries")
    suspend fun clearPlan()

    @Query("DELETE FROM recipe_tags")
    suspend fun clearRecipeTags()

    @Query("DELETE FROM ingredients")
    suspend fun clearIngredients()

    @Query("DELETE FROM ingredient_units")
    suspend fun clearIngredientUnits()

    @Query("DELETE FROM ingredient_library")
    suspend fun clearLibraryIngredients()

    @Query("DELETE FROM recipes")
    suspend fun clearRecipes()

    @Query("DELETE FROM tags")
    suspend fun clearTags()

    @Transaction
    suspend fun replaceAll(
        profile: ProfileEntity,
        library: List<IngredientLibrarySeed>,
        tags: List<TagEntity>,
        recipes: List<RecipeSeed>,
        pantry: List<PantryItemEntity>,
        plan: List<MealPlanSeed>,
    ) {
        clearPlan()
        clearRecipeTags()
        clearIngredients()
        clearIngredientUnits()
        clearLibraryIngredients()
        clearRecipes()
        clearTags()
        clearPantry()
        upsertProfile(profile)

        val libraryIdMap = mutableMapOf<String, Long>()
        val insertedLibraryIds = insertLibraryIngredients(library.map { it.ingredient })
        library.forEachIndexed { index, seed ->
            val ingredientId = insertedLibraryIds[index]
            libraryIdMap[seed.ingredient.name] = ingredientId
            insertIngredientUnits(
                seed.units.map { unit ->
                    unit.copy(ingredientId = ingredientId)
                },
            )
        }

        val insertedTagIds = insertTags(tags)
        val tagNameToId = tags.mapIndexed { index, tag -> tag.name to insertedTagIds[index] }.toMap()
        val recipeIdMap = mutableMapOf<String, Long>()

        recipes.forEach { seed ->
            val recipeId = insertRecipe(seed.recipe)
            recipeIdMap[seed.recipe.name] = recipeId
            insertIngredients(
                seed.ingredients.map { ingredient ->
                    ingredient.copy(
                        recipeId = recipeId,
                        libraryId = ingredient.libraryId ?: libraryIdMap[ingredient.name],
                    )
                },
            )
            insertRecipeTags(
                seed.tagNames.mapNotNull { name ->
                    tagNameToId[name]?.let { tagId ->
                        RecipeTagCrossRef(recipeId = recipeId, tagId = tagId)
                    }
                },
            )
        }

        insertPantryItems(pantry)
        insertPlanEntries(
            plan.mapNotNull { seed ->
                recipeIdMap[seed.recipeName]?.let { recipeId ->
                    MealPlanEntryEntity(
                        planDate = seed.planDate,
                        mealType = seed.mealType,
                        recipeId = recipeId,
                        isLogged = seed.isLogged,
                    )
                }
            },
        )
    }
}

data class RecipeSeed(
    val recipe: RecipeEntity,
    val ingredients: List<IngredientEntity>,
    val tagNames: List<String>,
)

data class IngredientLibrarySeed(
    val ingredient: IngredientLibraryEntity,
    val units: List<IngredientUnitEntity>,
)

data class MealPlanSeed(
    val planDate: String,
    val mealType: String,
    val recipeName: String,
    val isLogged: Boolean = false,
)
