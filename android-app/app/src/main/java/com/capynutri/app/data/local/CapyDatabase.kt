package com.capynutri.app.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        RecipeEntity::class,
        IngredientEntity::class,
        IngredientLibraryEntity::class,
        IngredientUnitEntity::class,
        TagEntity::class,
        RecipeTagCrossRef::class,
        PantryItemEntity::class,
        MealPlanEntryEntity::class,
        ProfileEntity::class,
    ],
    version = 3,
    exportSchema = false,
)
abstract class CapyDatabase : RoomDatabase() {
    abstract fun capyDao(): CapyDao

    companion object {
        fun create(context: Context): CapyDatabase =
            Room.databaseBuilder(
                context,
                CapyDatabase::class.java,
                "capynutri-local.db",
            ).fallbackToDestructiveMigration()
                .build()
    }
}
