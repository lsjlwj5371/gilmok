package com.gilmok.app.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.Dp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** 음성 상태를 나타내는 빛의 리본. moving이 false이면 주행 중 규칙에 따라 정지한다. */
@Composable
fun VoiceRing(size: Dp, listening: Boolean, level: Float, moving: Boolean, modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition(label = "ring")
    val clock by transition.animateFloat(
        0f, 1f, infiniteRepeatable(tween(6000, easing = LinearEasing), RepeatMode.Restart), label = "clock",
    )
    val energy by animateFloatAsState(if (listening) 0.4f + level * 0.6f else 0f, tween(200), label = "energy")
    val t = if (moving) clock else 0.12f
    Canvas(modifier.size(size)) { drawRibbon(t, energy, moving) }
}

private fun DrawScope.drawRibbon(t: Float, energy: Float, moving: Boolean) {
    val phase = 2 * PI * t
    // 대기 중에도 숨 쉬듯 천천히 커졌다 작아진다.
    val breathe = if (moving) 1f + 0.035f * sin(phase).toFloat() else 1f
    val base = size.minDimension * 0.32f * breathe

    drawCircle(
        Brush.radialGradient(
            listOf(Accent.copy(alpha = 0.34f + 0.2f * energy), Accent.copy(alpha = 0.08f), Color.Transparent),
            center, base * 1.75f,
        ),
        base * 1.75f,
    )
    drawCircle(
        Brush.radialGradient(listOf(Color.Transparent, Glow.copy(alpha = 0.05f)), center, base),
        base,
    )

    val brush = Brush.sweepGradient(listOf(Accent, Glow, Warm, Glow, Accent, Accent.copy(alpha = 0.6f), Accent), center)
    val lines = 16
    rotate(t * 360f) {
        for (k in 0 until lines) {
            val f = k / (lines - 1f)
            val path = Path()
            val steps = 160
            val swell = 0.075f + 0.09f * energy
            for (i in 0..steps) {
                val a = 2 * PI * i / steps
                val wave = sin(a * 3 + phase * 2 + f * 1.3) + 0.55 * sin(a * 5 - phase * 3 + f * 2.4)
                val r = base * (1f + swell * wave.toFloat() * (0.3f + f))
                val p = Offset(center.x + r * cos(a).toFloat(), center.y + r * sin(a).toFloat())
                if (i == 0) path.moveTo(p.x, p.y) else path.lineTo(p.x, p.y)
            }
            path.close()
            val weight = (1f - f) * (1f - f)
            drawPath(path, brush, alpha = 0.32f + 0.6f * weight, style = Stroke(1.4f + 1.4f * weight, cap = StrokeCap.Round))
        }
    }
    // 가장 안쪽의 밝은 선
    drawCircle(Glow.copy(alpha = 0.55f), base * 0.985f, style = Stroke(1.2f))
}
