package com.capynutri.app.data.local

import androidx.room.Embedded
import androidx.room.Entity
import androidx.room.Junction
import androidx.room.PrimaryKey
import androidx.room.Relation

@Entity(tableName = "recipes")
data class RecipeEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val servings: Double = 1.0,
    val instructions: String = "",
)

@Entity(tableName = "ingredients")
data class IngredientEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val recipeId: Long,
    val libraryId: Long? = null,
    val name: String,
    val quantity: Double,
    val unit: String = "",
    val kcal: Double? = null,
    val proteinG: Double? = null,
    val carbsG: Double? = null,
    val fatG: Double? = null,
)

@Entity(tableName = "ingredient_library")
data class IngredientLibraryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val defaultUnit: String = "g",
    val kcalPer100: Double? = null,
    val proteinPer100: Double? = null,
    val carbsPer100: Double? = null,
    val fatPer100: Double? = null,
    val densityGPerMl: Double? = null,
)

@Entity(tableName = "ingredient_units")
data class IngredientUnitEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val ingredientId: Long,
    val unitName: String,
    val gramsPerUnit: Double? = null,
    val mlPerUnit: Double? = null,
    val isDefault: Boolean = false,
)

@Entity(tableName = "tags")
data class TagEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val colorHex: String,
    val iconName: String,
    val isDefault: Boolean = false,
)

@Entity(primaryKeys = ["recipeId", "tagId"], tableName = "recipe_tags")
data class RecipeTagCrossRef(
    val recipeId: Long,
    val tagId: Long,
)

@Entity(tableName = "pantry_items")
data class PantryItemEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val quantity: Double,
    val unit: String,
)

@Entity(tableName = "meal_plan_entries")
data class MealPlanEntryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val planDate: String,
    val mealType: String,
    val recipeId: Long,
    val isLogged: Boolean = false,
)

@Entity(tableName = "profile")
data class ProfileEntity(
    @PrimaryKey val id: Long = 1,
    val name: String = "",
    val weightKg: Double? = null,
    val heightCm: Double? = null,
    val age: Int? = null,
    val sex: String = "M",
    val activityLevel: String = "moderate",
    val goal: String = "maintain",
    val mealsPerDay: Int = 3,
    val currentBfPct: Double? = null,
    val goalWeightKg: Double? = null,
    val goalBfPct: Double? = null,
)

data class RecipeWithDetails(
    @Embedded val recipe: RecipeEntity,
    @Relation(parentColumn = "id", entityColumn = "recipeId")
    val ingredients: List<IngredientEntity>,
    @Relation(
        parentColumn = "id",
        entityColumn = "id",
        associateBy = Junction(
            value = RecipeTagCrossRef::class,
            parentColumn = "recipeId",
            entityColumn = "tagId",
        ),
    )
    val tags: List<TagEntity>,
)

data class IngredientLibraryWithUnits(
    @Embedded val ingredient: IngredientLibraryEntity,
    @Relation(parentColumn = "id", entityColumn = "ingredientId")
    val units: List<IngredientUnitEntity>,
)

data class MealPlanWithRecipe(
    @Embedded val entry: MealPlanEntryEntity,
    @Relation(parentColumn = "recipeId", entityColumn = "id")
    val recipe: RecipeEntity,
)
