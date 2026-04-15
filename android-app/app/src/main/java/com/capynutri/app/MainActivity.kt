package com.capynutri.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.capynutri.app.ui.CapyNutriApp
import com.capynutri.app.ui.CapyViewModel
import com.capynutri.app.ui.CapyViewModelFactory
import com.capynutri.app.ui.theme.CapyNutriTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val repository = (application as CapyNutriApplication).repository

        setContent {
            CapyNutriTheme {
                CapyNutriRoot(factory = CapyViewModelFactory(repository))
            }
        }
    }
}

@Composable
private fun CapyNutriRoot(factory: CapyViewModelFactory) {
    val viewModel: CapyViewModel = viewModel(factory = factory)
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    CapyNutriApp(
        state = state,
        onSelectDay = viewModel::selectDay,
        onSeedDemoData = viewModel::seedDemoData,
        onSaveProfile = viewModel::saveProfile,
    )
}
