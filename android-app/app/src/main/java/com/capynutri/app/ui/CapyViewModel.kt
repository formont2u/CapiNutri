package com.capynutri.app.ui

import com.capynutri.app.data.local.IngredientLibraryWithUnits
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.capynutri.app.data.local.MealPlanWithRecipe
import com.capynutri.app.data.local.PantryItemEntity
import com.capynutri.app.data.local.ProfileEntity
import com.capynutri.app.data.local.RecipeWithDetails
import com.capynutri.app.data.repository.CapyRepository
import com.capynutri.app.domain.AdaptedRecipeCard
import com.capynutri.app.domain.NutritionStrategy
import com.capynutri.app.domain.adaptRecipesForProfile
import com.capynutri.app.domain.calculateNutritionStrategy
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class CapyUiState(
    val selectedDate: String = LocalDate.now().toString(),
    val profile: ProfileEntity? = null,
    val recipes: List<RecipeWithDetails> = emptyList(),
    val libraryItems: List<IngredientLibraryWithUnits> = emptyList(),
    val adaptedRecipes: List<AdaptedRecipeCard> = emptyList(),
    val pantryItems: List<PantryItemEntity> = emptyList(),
    val planEntries: List<MealPlanWithRecipe> = emptyList(),
    val strategy: NutritionStrategy? = null,
)

class CapyViewModel(
    private val repository: CapyRepository,
) : ViewModel() {
    private val selectedDate = MutableStateFlow(LocalDate.now().toString())

    val uiState: StateFlow<CapyUiState> = combine(
        selectedDate,
        repository.observeProfile(),
        repository.observeRecipes(),
        repository.observeLibrary(),
        repository.observePantry(),
    ) { date, profile, recipes, library, pantry ->
        InterimUiState(
            selectedDate = date,
            profile = profile,
            recipes = recipes,
            libraryItems = library,
            pantryItems = pantry,
        )
    }.combine(
        selectedDate.flatMapLatest { repository.observePlanForDate(it) },
    ) { base, plan ->
        val strategy = calculateNutritionStrategy(base.profile)
        CapyUiState(
            selectedDate = base.selectedDate,
            profile = base.profile,
            recipes = base.recipes,
            libraryItems = base.libraryItems,
            adaptedRecipes = adaptRecipesForProfile(base.recipes, base.profile, strategy),
            pantryItems = base.pantryItems,
            planEntries = plan,
            strategy = strategy,
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = CapyUiState(),
    )

    init {
        seedDemoData()
    }

    fun selectDay(date: String) {
        selectedDate.value = date
    }

    fun seedDemoData() {
        viewModelScope.launch {
            repository.seedDemoData()
        }
    }

    fun saveProfile(profile: ProfileEntity) {
        viewModelScope.launch {
            repository.saveProfile(profile)
        }
    }
}

private data class InterimUiState(
    val selectedDate: String,
    val profile: ProfileEntity?,
    val recipes: List<RecipeWithDetails>,
    val libraryItems: List<IngredientLibraryWithUnits>,
    val pantryItems: List<PantryItemEntity>,
)

class CapyViewModelFactory(
    private val repository: CapyRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return CapyViewModel(repository) as T
    }
}
