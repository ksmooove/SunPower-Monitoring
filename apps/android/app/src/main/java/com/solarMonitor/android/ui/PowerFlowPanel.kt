package com.solarMonitor.android.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.solarMonitor.android.R
import java.util.Locale
import kotlin.math.atan2
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

private val SolarColor = Color(0xFFE08A1A)
private val SolarCore = Color(0xFFFFC14D)
private val GridColor = Color(0xFF3CB043)
private val GridCore = Color(0xFF7DFF7A)

private data class FlowEdge(
    val id: String,
    val start: Offset,
    val control: Offset,
    val end: Offset,
    val color: Color,
    val core: Color,
    val durationMs: Int,
)

@Composable
fun PowerFlowPanel(
    pv: Double?,
    load: Double?,
    net: Double?,
    modifier: Modifier = Modifier,
) {
    val configuration = LocalConfiguration.current
    val landscape = configuration.screenWidthDp > configuration.screenHeightDp
    val sceneRes = if (landscape) R.drawable.power_flow_landscape else R.drawable.power_flow_portrait

    val solar = max(0.0, pv ?: 0.0)
    val home = max(0.0, load ?: 0.0)
    val gridAbs = kotlin.math.abs(net ?: 0.0)
    val exporting = (net ?: 0.0) < -0.005
    val importing = (net ?: 0.0) > 0.005

    val edges = remember(solar, home, gridAbs, exporting, importing, landscape) {
        buildEdges(solar, gridAbs, exporting, importing, landscape)
    }

    val aspect = if (landscape) 16f / 9f else 3f / 4f

    Box(
        modifier = modifier
            .fillMaxWidth()
            .aspectRatio(aspect)
            .background(Color(0xFFF3EEE6), RoundedCornerShape(16.dp)),
    ) {
        Image(
            painter = painterResource(sceneRes),
            contentDescription = "Home energy flow scene",
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize(),
        )
        FlowCanvas(
            edges = edges,
            landscape = landscape,
            modifier = Modifier.fillMaxSize(),
        )
        FlowBadges(
            solar = solar,
            home = home,
            gridAbs = gridAbs,
            exporting = exporting,
            importing = importing,
            landscape = landscape,
            modifier = Modifier.fillMaxSize(),
        )
    }
}

@Composable
private fun FlowCanvas(
    edges: List<FlowEdge>,
    landscape: Boolean,
    modifier: Modifier = Modifier,
) {
    val transition = rememberInfiniteTransition(label = "flow")
    val phase by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "dashPhase",
    )

    Canvas(modifier = modifier) {
        val vbW = if (landscape) 1350f else 750f
        val vbH = if (landscape) 900f else 1000f
        val sx = size.width / vbW
        val sy = size.height / vbH
        val scale = min(sx, sy)

        fun map(p: Offset) = Offset(p.x * sx, p.y * sy)

        for (edge in edges) {
            val start = map(edge.start)
            val control = map(edge.control)
            val end = map(edge.end)
            val path = Path().apply {
                moveTo(start.x, start.y)
                quadraticTo(control.x, control.y, end.x, end.y)
            }

            val strokeWidth = 10f * scale
            drawPath(
                path = path,
                color = edge.color.copy(alpha = 0.25f),
                style = Stroke(width = strokeWidth * 1.8f, cap = StrokeCap.Round),
            )
            drawPath(
                path = path,
                color = edge.color.copy(alpha = 0.35f),
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round),
            )

            val speed = 1000f / edge.durationMs.coerceAtLeast(300)
            val dashPhase = -phase * 76f * speed
            drawPath(
                path = path,
                color = edge.core,
                style = Stroke(
                    width = strokeWidth * 0.55f,
                    cap = StrokeCap.Butt,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(22f, 16f), dashPhase),
                ),
            )
            drawPath(
                path = path,
                color = edge.color.copy(alpha = 0.55f),
                style = Stroke(
                    width = strokeWidth * 0.9f,
                    cap = StrokeCap.Butt,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 28f), dashPhase * 0.75f),
                ),
            )

            val tipAngle = Math.toDegrees(
                atan2(
                    (end.y - control.y).toDouble(),
                    (end.x - control.x).toDouble(),
                ),
            ).toFloat()
            drawTechArrow(end, tipAngle, edge.color, edge.core, scale)
        }
    }
}

private fun DrawScope.drawTechArrow(
    tip: Offset,
    angleDeg: Float,
    color: Color,
    core: Color,
    scale: Float,
) {
    val s = 1.35f * scale
    translate(left = tip.x, top = tip.y) {
        rotate(degrees = angleDeg, pivot = Offset.Zero) {
            drawCircle(
                color = color.copy(alpha = 0.22f),
                radius = 22f * s,
                center = Offset(-4f * s, 0f),
            )
            val outer = Path().apply {
                moveTo(-28f * s, -24f * s)
                lineTo(32f * s, 0f)
                lineTo(-28f * s, 24f * s)
                lineTo(-14f * s, 0f)
                close()
            }
            drawPath(outer, color = color)
            val inner = Path().apply {
                moveTo(-18f * s, -12f * s)
                lineTo(22f * s, 0f)
                lineTo(-18f * s, 12f * s)
                lineTo(-8f * s, 0f)
                close()
            }
            drawPath(inner, color = core)
        }
    }
}

@Composable
private fun FlowBadges(
    solar: Double,
    home: Double,
    gridAbs: Double,
    exporting: Boolean,
    importing: Boolean,
    landscape: Boolean,
    modifier: Modifier = Modifier,
) {
    Box(modifier = modifier) {
        FlowBadge(
            title = "Solar production",
            value = formatPowerKw(solar),
            valueColor = SolarColor,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(top = if (landscape) 12.dp else 10.dp)
                .padding(start = if (landscape) 72.dp else 48.dp),
        )

        FlowBadge(
            title = "Home usage",
            value = formatPowerKw(home),
            valueColor = Color(0xFF111827),
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(start = if (landscape) 16.dp else 10.dp),
        )

        val gridTitle = when {
            exporting -> "Grid export"
            importing -> "Grid import"
            else -> "Grid"
        }
        FlowBadge(
            title = gridTitle,
            value = formatPowerKw(gridAbs),
            valueColor = GridColor,
            modifier = Modifier
                .align(if (landscape) Alignment.BottomCenter else Alignment.BottomEnd)
                .padding(
                    bottom = if (landscape) 14.dp else 18.dp,
                    end = if (landscape) 0.dp else 10.dp,
                    start = if (landscape) 72.dp else 0.dp,
                ),
        )
    }
}

@Composable
private fun FlowBadge(
    title: String,
    value: String,
    valueColor: Color,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .background(Color(0xF0FFFCF7), RoundedCornerShape(12.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = title.uppercase(),
            style = MaterialTheme.typography.labelSmall.copy(
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.6.sp,
                color = Color(0xFF5C6778),
            ),
        )
        Text(
            text = value,
            style = MaterialTheme.typography.titleMedium.copy(
                fontWeight = FontWeight.Bold,
                color = valueColor,
            ),
        )
    }
}

private fun buildEdges(
    solar: Double,
    gridAbs: Double,
    exporting: Boolean,
    importing: Boolean,
    landscape: Boolean,
): List<FlowEdge> {
    val durationFor = { kw: Double ->
        (max(0.45, min(1.8, 1.35 / sqrt(kw + 0.08))) * 1000).toInt()
    }

    val solarStart: Offset
    val solarCtrl: Offset
    val solarEnd: Offset
    val gridHouse: Offset
    val gridCtrl: Offset
    val gridPole: Offset

    if (landscape) {
        solarStart = Offset(1125f, 175f)
        solarCtrl = Offset(880f, 45f)
        solarEnd = Offset(705f, 350f)
        gridHouse = Offset(790f, 545f)
        gridCtrl = Offset(1010f, 800f)
        gridPole = Offset(1175f, 640f)
    } else {
        solarStart = Offset(620f, 140f)
        solarCtrl = Offset(480f, 60f)
        solarEnd = Offset(360f, 320f)
        gridHouse = Offset(320f, 620f)
        gridCtrl = Offset(520f, 820f)
        gridPole = Offset(640f, 720f)
    }

    val out = mutableListOf<FlowEdge>()
    if (solar > 0.005) {
        out += FlowEdge(
            id = "solar-home",
            start = solarStart,
            control = solarCtrl,
            end = solarEnd,
            color = SolarColor,
            core = SolarCore,
            durationMs = durationFor(solar),
        )
    }
    if (exporting && gridAbs > 0.005) {
        out += FlowEdge(
            id = "home-grid",
            start = gridHouse,
            control = gridCtrl,
            end = gridPole,
            color = GridColor,
            core = GridCore,
            durationMs = durationFor(gridAbs),
        )
    }
    if (importing && gridAbs > 0.005) {
        out += FlowEdge(
            id = "grid-home",
            start = gridPole,
            control = gridCtrl,
            end = gridHouse,
            color = GridColor,
            core = GridCore,
            durationMs = durationFor(gridAbs),
        )
    }
    return out
}

internal fun formatPowerKw(n: Double?): String {
    if (n == null) return "—"
    val v = kotlin.math.abs(n)
    return if (v < 1) "${(n * 1000).toInt()} W" else String.format(Locale.US, "%.2f kW", n)
}
