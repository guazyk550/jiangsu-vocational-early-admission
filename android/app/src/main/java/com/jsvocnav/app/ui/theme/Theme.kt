package com.jsvocnav.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * 配色与桌面版 `src/ui/style.py` 的主题令牌保持一致（两套都通过 WCAG AA 对比度校验）。
 * 跟随系统深浅色，不需要用户手动切换。
 */
private val LightColors = lightColorScheme(
    primary = Color(0xFF2563EB),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE0EDFF),
    onPrimaryContainer = Color(0xFF1D4ED8),
    secondary = Color(0xFF0F766E),
    secondaryContainer = Color(0xFFE6FFFB),
    onSecondaryContainer = Color(0xFF0F766E),
    tertiary = Color(0xFFB45309),
    tertiaryContainer = Color(0xFFFFF7E6),
    onTertiaryContainer = Color(0xFFB45309),
    background = Color(0xFFF6F7F9),
    onBackground = Color(0xFF1F2937),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1F2937),
    surfaceVariant = Color(0xFFF3F4F6),
    onSurfaceVariant = Color(0xFF6B7280),
    outline = Color(0xFFE5E7EB),
    outlineVariant = Color(0xFFEEF0F3),
    error = Color(0xFFB91C1C),
    errorContainer = Color(0xFFFEE2E2),
    onErrorContainer = Color(0xFFB91C1C),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF3B82F6),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFF1C355F),
    onPrimaryContainer = Color(0xFF93C5FD),
    secondary = Color(0xFF4ADE80),
    secondaryContainer = Color(0xFF14311F),
    onSecondaryContainer = Color(0xFF4ADE80),
    tertiary = Color(0xFFFBBF24),
    tertiaryContainer = Color(0xFF3A2C12),
    onTertiaryContainer = Color(0xFFFBBF24),
    background = Color(0xFF15171C),
    onBackground = Color(0xFFE6E8EC),
    surface = Color(0xFF1E2128),
    onSurface = Color(0xFFE6E8EC),
    surfaceVariant = Color(0xFF262A33),
    onSurfaceVariant = Color(0xFFA3ADBB),
    outline = Color(0xFF333844),
    outlineVariant = Color(0xFF262A33),
    error = Color(0xFFFCA5A5),
    errorContainer = Color(0xFF3D1D1D),
    onErrorContainer = Color(0xFFFCA5A5),
)

@Composable
fun JsvocNavTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
