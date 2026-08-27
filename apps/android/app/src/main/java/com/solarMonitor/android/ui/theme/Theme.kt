package com.solarMonitor.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val SolarOrange = Color(0xFFC47B12)
private val SolarTeal = Color(0xFF2F6F7A)
private val Ink = Color(0xFF1C2430)
private val Cream = Color(0xFFF4EFE6)

private val LightColors = lightColorScheme(
    primary = SolarOrange,
    secondary = SolarTeal,
    background = Cream,
    surface = Color(0xFFFFFCF7),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onBackground = Ink,
    onSurface = Ink,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFE8A317),
    secondary = Color(0xFF6EB8C2),
    background = Color(0xFF0F1419),
    surface = Color(0xFF1A2332),
    onPrimary = Color(0xFF1C2430),
    onSecondary = Color(0xFF0F1419),
    onBackground = Color(0xFFEDF1F5),
    onSurface = Color(0xFFEDF1F5),
)

@Composable
fun SolarMonitorTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
