package com.capynutri.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Inventory2
import androidx.compose.material.icons.rounded.MenuBook
import androidx.compose.material.icons.rounded.Person
import androidx.compose.material.icons.rounded.Science
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.capynutri.app.R
import com.capynutri.app.data.local.IngredientLibraryWithUnits
import com.capynutri.app.data.local.MealPlanWithRecipe
import com.capynutri.app.data.local.PantryItemEntity
import com.capynutri.app.data.local.ProfileEntity
import com.capynutri.app.domain.AdaptedRecipeCard
import com.capynutri.app.domain.NutritionStrategy
import com.capynutri.app.ui.theme.CapyGreen
import com.capynutri.app.ui.theme.CapyOrange
import com.capynutri.app.ui.theme.CapyOrangeDark
import com.capynutri.app.ui.theme.CapySoft
import java.time.LocalDate

private enum class CapyTab(val label: String) {
    Recipes("Recettes"),
    Plan("Planning"),
    Pantry("Stock"),
    Library("Biblio"),
    Profile("Profil"),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CapyNutriApp(
    state: CapyUiState,
    onSelectDay: (String) -> Unit,
    onSeedDemoData: () -> Unit,
    onSaveProfile: (ProfileEntity) -> Unit,
) {
    var currentTab by rememberSaveable { mutableStateOf(CapyTab.Recipes) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Image(
                            painter = painterResource(id = R.drawable.logo),
                            contentDescription = "Logo CapyNutri",
                            modifier = Modifier
                                .size(44.dp)
                                .clip(MaterialTheme.shapes.medium),
                            contentScale = ContentScale.Crop,
                        )
                        Column {
                            Text("CapyNutri", style = MaterialTheme.typography.headlineMedium)
                            Text(
                                text = state.profile?.name?.ifBlank { "Local device" } ?: "Local device",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                },
            )
        },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = currentTab == CapyTab.Recipes,
                    onClick = { currentTab = CapyTab.Recipes },
                    icon = { Icon(Icons.Rounded.MenuBook, contentDescription = null) },
                    label = { Text(CapyTab.Recipes.label) },
                )
                NavigationBarItem(
                    selected = currentTab == CapyTab.Plan,
                    onClick = { currentTab = CapyTab.Plan },
                    icon = { Icon(Icons.Rounded.CalendarMonth, contentDescription = null) },
                    label = { Text(CapyTab.Plan.label) },
                )
                NavigationBarItem(
                    selected = currentTab == CapyTab.Pantry,
                    onClick = { currentTab = CapyTab.Pantry },
                    icon = { Icon(Icons.Rounded.Inventory2, contentDescription = null) },
                    label = { Text(CapyTab.Pantry.label) },
                )
                NavigationBarItem(
                    selected = currentTab == CapyTab.Library,
                    onClick = { currentTab = CapyTab.Library },
                    icon = { Icon(Icons.Rounded.Science, contentDescription = null) },
                    label = { Text(CapyTab.Library.label) },
                )
                NavigationBarItem(
                    selected = currentTab == CapyTab.Profile,
                    onClick = { currentTab = CapyTab.Profile },
                    icon = { Icon(Icons.Rounded.Person, contentDescription = null) },
                    label = { Text(CapyTab.Profile.label) },
                )
            }
        },
    ) { innerPadding ->
        when (currentTab) {
            CapyTab.Recipes -> RecipesScreen(
                adaptedRecipes = state.adaptedRecipes,
                strategy = state.strategy,
                onSeedDemoData = onSeedDemoData,
                modifier = Modifier.padding(innerPadding),
            )
            CapyTab.Plan -> PlanScreen(
                selectedDate = state.selectedDate,
                planEntries = state.planEntries,
                onSelectDay = onSelectDay,
                modifier = Modifier.padding(innerPadding),
            )
            CapyTab.Pantry -> PantryScreen(
                pantryItems = state.pantryItems,
                modifier = Modifier.padding(innerPadding),
            )
            CapyTab.Library -> LibraryScreen(
                libraryItems = state.libraryItems,
                modifier = Modifier.padding(innerPadding),
            )
            CapyTab.Profile -> ProfileScreen(
                profile = state.profile,
                strategy = state.strategy,
                onSaveProfile = onSaveProfile,
                modifier = Modifier.padding(innerPadding),
            )
        }
    }
}

@Composable
private fun RecipesScreen(
    adaptedRecipes: List<AdaptedRecipeCard>,
    strategy: NutritionStrategy?,
    onSeedDemoData: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CapyOrange),
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Image(
                            painter = painterResource(id = R.drawable.logo),
                            contentDescription = "Logo CapyNutri",
                            modifier = Modifier
                                .size(56.dp)
                                .clip(MaterialTheme.shapes.large),
                            contentScale = ContentScale.Crop,
                        )
                        Column {
                            Text("CapyNutri", style = MaterialTheme.typography.headlineMedium, color = Color.White)
                            Text("Recettes adaptees a ton profil", color = Color.White.copy(alpha = 0.92f))
                        }
                    }
                    Text(
                        strategy?.let {
                            "Objectif courant: ${it.kcal} kcal/jour, soit environ ${it.mealSplit.kcal} kcal par repas."
                        } ?: "Renseigne ton profil pour obtenir des portions conseillees et des macros adaptees.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color.White,
                    )
                    AssistChip(
                        onClick = onSeedDemoData,
                        label = { Text("Recharger les donnees demo") },
                    )
                }
            }
        }

        items(adaptedRecipes, key = { it.recipeId }) { recipe ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(recipe.name, style = MaterialTheme.typography.titleMedium)
                    Text(
                        "${recipe.baseServings.toInt()} portions de base - ${recipe.kcalPerServing.toInt()} kcal/portion",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        recipe.tags.take(3).forEach { tag ->
                            AssistChip(onClick = {}, label = { Text(tag) })
                        }
                    }
                    if (recipe.recommendedServings != null) {
                        Card(colors = CardDefaults.cardColors(containerColor = CapySoft)) {
                            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("Suggestion CapyNutri", color = CapyOrangeDark, style = MaterialTheme.typography.labelLarge)
                                Text(
                                    "${recipe.recommendedServings} portion(s) conseillee(s) - ${recipe.adaptedKcal} kcal - ${recipe.adaptedProteinG} g proteines",
                                    style = MaterialTheme.typography.bodyMedium,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PlanScreen(
    selectedDate: String,
    planEntries: List<MealPlanWithRecipe>,
    onSelectDay: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val dateOptions = listOf(
        LocalDate.parse(selectedDate).minusDays(1).toString(),
        selectedDate,
        LocalDate.parse(selectedDate).plusDays(1).toString(),
    )

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CapySoft),
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Planning du jour", style = MaterialTheme.typography.titleMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        dateOptions.forEach { date ->
                            AssistChip(onClick = { onSelectDay(date) }, label = { Text(date) })
                        }
                    }
                }
            }
        }

        items(planEntries, key = { it.entry.id }) { item ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        item.entry.mealType.replaceFirstChar { it.uppercase() },
                        style = MaterialTheme.typography.labelLarge,
                        color = CapyOrangeDark,
                    )
                    Text(item.recipe.name, style = MaterialTheme.typography.titleMedium)
                    Text(
                        if (item.entry.isLogged) "Deja journalise" else "Prevu pour aujourd'hui",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun PantryScreen(
    pantryItems: List<PantryItemEntity>,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CapyGreen.copy(alpha = 0.12f)),
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Stock local", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Le prototype Android stocke tout en SQLite locale sur l'appareil via Room.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }

        items(pantryItems, key = { it.id }) { item ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(item.name, style = MaterialTheme.typography.titleSmall)
                    Text("${item.quantity} ${item.unit}", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

@Composable
private fun LibraryScreen(
    libraryItems: List<IngredientLibraryWithUnits>,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = CapySoft),
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Bibliotheque ingredients", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Nutrition, densite g/ml et unites intelligentes vivent ici pour preparer la vraie migration du web vers l'APK.",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }

        items(libraryItems, key = { it.ingredient.id }) { item ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(item.ingredient.name, style = MaterialTheme.typography.titleMedium)
                            Text(
                                "Unite de base: ${item.ingredient.defaultUnit}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        item.ingredient.densityGPerMl?.let { density ->
                            AssistChip(onClick = {}, label = { Text("densite ${density} g/ml") })
                        }
                    }

                    val macros = buildList {
                        item.ingredient.kcalPer100?.let { add("${it.toInt()} kcal") }
                        item.ingredient.proteinPer100?.let { add("${it}g prot") }
                        item.ingredient.carbsPer100?.let { add("${it}g gluc") }
                        item.ingredient.fatPer100?.let { add("${it}g lip") }
                    }
                    if (macros.isNotEmpty()) {
                        Text(
                            "Pour 100 g/ml: ${macros.joinToString(" - ")}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        item.units.forEach { unit ->
                            val label = when {
                                unit.gramsPerUnit != null -> "${unit.unitName} = ${unit.gramsPerUnit} g"
                                unit.mlPerUnit != null -> "${unit.unitName} = ${unit.mlPerUnit} ml"
                                else -> unit.unitName
                            }
                            AssistChip(onClick = {}, label = { Text(label) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ProfileScreen(
    profile: ProfileEntity?,
    strategy: NutritionStrategy?,
    onSaveProfile: (ProfileEntity) -> Unit,
    modifier: Modifier = Modifier,
) {
    var name by remember(profile?.name) { mutableStateOf(profile?.name.orEmpty()) }
    var weight by remember(profile?.weightKg) { mutableStateOf(profile?.weightKg?.toString().orEmpty()) }
    var height by remember(profile?.heightCm) { mutableStateOf(profile?.heightCm?.toString().orEmpty()) }
    var age by remember(profile?.age) { mutableStateOf(profile?.age?.toString().orEmpty()) }
    var meals by remember(profile?.mealsPerDay) { mutableStateOf((profile?.mealsPerDay ?: 3).toString()) }
    var activity by remember(profile?.activityLevel) { mutableStateOf(profile?.activityLevel ?: "moderate") }
    var currentBf by remember(profile?.currentBfPct) { mutableStateOf(profile?.currentBfPct?.toString().orEmpty()) }
    var goalBf by remember(profile?.goalBfPct) { mutableStateOf(profile?.goalBfPct?.toString().orEmpty()) }
    var goalWeight by remember(profile?.goalWeightKg) { mutableStateOf(profile?.goalWeightKg?.toString().orEmpty()) }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Mon profil", style = MaterialTheme.typography.titleLarge)
                    OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Prenom") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = weight, onValueChange = { weight = it }, label = { Text("Poids (kg)") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = height, onValueChange = { height = it }, label = { Text("Taille (cm)") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = age, onValueChange = { age = it }, label = { Text("Age") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = meals, onValueChange = { meals = it }, label = { Text("Repas par jour") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(
                        value = activity,
                        onValueChange = { activity = it },
                        label = { Text("Activite (sedentary/light/moderate/active/very_active)") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(value = currentBf, onValueChange = { currentBf = it }, label = { Text("Gras actuel (%)") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = goalBf, onValueChange = { goalBf = it }, label = { Text("Gras cible (%)") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = goalWeight, onValueChange = { goalWeight = it }, label = { Text("Poids cible (kg)") }, modifier = Modifier.fillMaxWidth())
                    Button(
                        onClick = {
                            onSaveProfile(
                                ProfileEntity(
                                    id = 1,
                                    name = name,
                                    weightKg = weight.toDoubleOrNull(),
                                    heightCm = height.toDoubleOrNull(),
                                    age = age.toIntOrNull(),
                                    sex = profile?.sex ?: "M",
                                    activityLevel = activity,
                                    goal = profile?.goal ?: "maintain",
                                    mealsPerDay = meals.toIntOrNull() ?: 3,
                                    currentBfPct = currentBf.toDoubleOrNull(),
                                    goalWeightKg = goalWeight.toDoubleOrNull(),
                                    goalBfPct = goalBf.toDoubleOrNull(),
                                ),
                            )
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Sauvegarder et recalculer")
                    }
                }
            }
        }

        if (strategy != null) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CapySoft),
                ) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(strategy.strategy, style = MaterialTheme.typography.titleMedium, color = CapyOrangeDark)
                        Text(strategy.description)
                        Text("Maintenance estimee: ${strategy.tdee} kcal")
                        Text("Objectif: ${strategy.kcal} kcal - ${strategy.proteinG}g P - ${strategy.carbsG}g G - ${strategy.fatG}g L")
                        Text("Par repas: ${strategy.mealSplit.kcal} kcal - ${strategy.mealSplit.proteinG}g proteines")
                        Text(
                            strategy.mealSplit.advice,
                            color = if (strategy.mealSplit.status == "success") CapyGreen else CapyOrangeDark,
                        )
                    }
                }
            }
        }
    }
}
