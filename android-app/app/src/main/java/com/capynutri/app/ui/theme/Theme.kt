package com.capynutri.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = CapyOrange,
    onPrimary = Color.White,
    secondary = CapyGreen,
    tertiary = CapySoft,
    background = CapyBackground,
    surface = Color.White,
    onSurface = CapyInk,
    onSurfaceVariant = Color(0xFF6B7280),
)

private val DarkColors = darkColorScheme(
    primary = CapyOrange,
    secondary = CapyGreen,
    tertiary = CapySoft,
)

@Composable
fun CapyNutriTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = Typography,
        content = content,
    )
}
