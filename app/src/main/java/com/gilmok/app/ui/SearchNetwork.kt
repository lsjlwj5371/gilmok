package com.gilmok.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathMeasure
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.sp
import com.gilmok.app.core.Excluded
import kotlin.random.Random

private class Node(val x: Float, val y: Float) {
    var fromStart = Int.MAX_VALUE
    var fromEnd = Int.MAX_VALUE
    val links = mutableListOf<Node>()
    val reach get() = minOf(fromStart, fromEnd)
}

private class Graph(val nodes: List<Node>, val route: List<Node>, val maxReach: Int)

private fun link(a: Node, b: Node) {
    a.links += b
    b.links += a
}

private fun spread(from: Node, write: (Node, Int) -> Unit, read: (Node) -> Int) {
    write(from, 0)
    val queue = ArrayDeque(listOf(from))
    while (queue.isNotEmpty()) {
        val n = queue.removeFirst()
        for (m in n.links) {
            if (read(m) == Int.MAX_VALUE) {
                write(m, read(n) + 1)
                queue += m
            }
        }
    }
}

/** 실제 도로가 아니라 탐색 느낌을 주는 시각 효과용 그래프다. 출발지는 아래, 목적지는 위에 둔다. */
private fun buildGraph(): Graph {
    val rnd = Random(7)
    val cols = 9
    val rows = 15
    val grid = List(rows) { r ->
        List(cols) { c ->
            Node(
                0.07f + 0.86f * c / (cols - 1) + (rnd.nextFloat() - 0.5f) * 0.07f,
                0.9f - 0.8f * r / (rows - 1) + (rnd.nextFloat() - 0.5f) * 0.035f,
            )
        }
    }
    for (r in 0 until rows) {
        for (c in 0 until cols) {
            if (r + 1 < rows) link(grid[r][c], grid[r + 1][c])
            if (c + 1 < cols && rnd.nextFloat() < 0.55f) link(grid[r][c], grid[r][c + 1])
            if (r + 1 < rows && c + 1 < cols && rnd.nextFloat() < 0.3f) link(grid[r][c], grid[r + 1][c + 1])
        }
    }
    val start = Node(0.5f, 0.96f)
    val end = Node(0.5f, 0.04f)
    for (c in 2..6) {
        link(start, grid[0][c])
        link(end, grid[rows - 1][c])
    }
    val nodes = grid.flatten() + start + end
    spread(start, { n, v -> n.fromStart = v }, { it.fromStart })
    spread(end, { n, v -> n.fromEnd = v }, { it.fromEnd })
    // 네트워크에 이미 있는 선을 따라가는 경로 하나를 고른다.
    val route = mutableListOf(start)
    var n = start
    while (n !== end) {
        val next = n.links.filter { it.fromEnd < n.fromEnd }.minBy { m -> kotlin.math.abs(m.x - (0.5f + 0.2f * kotlin.math.sin(m.y * 7f))) }
        route += next
        n = next
    }
    return Graph(nodes, route, nodes.maxOf { it.reach })
}

private val SLOTS = listOf(
    Offset(0.19f, 0.72f), Offset(0.81f, 0.6f), Offset(0.19f, 0.46f), Offset(0.81f, 0.34f), Offset(0.19f, 0.22f),
)

private val Ease = CubicBezierEasing(0.33f, 0f, 0.2f, 1f)

/**
 * 탐색 중 보여주는 연출. 출발지와 목적지에서 길이 번져 나가 만나고,
 * 그 네트워크 안의 한 줄기가 빛난다. 시각적 강조용이며 실제 위치나 경로가 아니다.
 */
@Composable
fun SearchNetwork(excluded: List<Excluded>, destination: String, modifier: Modifier = Modifier) {
    val graph = remember { buildGraph() }
    val measurer = rememberTextMeasurer()
    val spreadAnim = remember { Animatable(0f) }
    val tags = remember { Animatable(0f) }
    val glow = remember { Animatable(0f) }
    val transition = rememberInfiniteTransition(label = "pulse")
    val pulse by transition.animateFloat(
        0f, 1f, infiniteRepeatable(tween(1800, easing = LinearEasing), RepeatMode.Restart), label = "pulse",
    )
    LaunchedEffect(excluded.size) {
        if (excluded.isEmpty()) return@LaunchedEffect
        val shown = excluded.size.coerceAtMost(SLOTS.size)
        tags.animateTo(shown.toFloat(), tween(420 * shown, easing = LinearEasing))
    }
    LaunchedEffect(Unit) {
        spreadAnim.animateTo(1f, tween(3200, easing = Ease))
        glow.animateTo(1f, tween(1500, easing = Ease))
    }
    Canvas(modifier) {
        drawNetwork(graph, spreadAnim.value, glow.value)
        drawGlow(graph.route, glow.value, pulse)
        drawEnd(graph.route.first(), "현재 위치", measurer)
        drawEnd(graph.route.last(), destination.ifEmpty { "목적지" }, measurer)
        excluded.take(SLOTS.size).forEachIndexed { i, e ->
            val a = (tags.value - i).coerceIn(0f, 1f)
            if (a > 0f) drawTag(SLOTS[i], e, a * (1f - glow.value * 0.55f), measurer)
        }
    }
}

private fun DrawScope.at(n: Node) = Offset(n.x * size.width, n.y * size.height)

private fun DrawScope.drawNetwork(g: Graph, progress: Float, glow: Float) {
    val front = progress * (g.maxReach + 4f)
    val dim = 1f - glow * 0.55f
    for (n in g.nodes) {
        val a = ((front - n.reach) / 4f).coerceIn(0f, 1f)
        if (a <= 0f) continue
        for (m in n.links) {
            if (m.reach < n.reach) continue
            val b = ((front - m.reach) / 4f).coerceIn(0f, 1f)
            drawLine(Accent.copy(alpha = 0.26f * minOf(a, b) * dim), at(n), at(m), 1f)
        }
        drawCircle(Accent.copy(alpha = 0.55f * a * dim), 1.8f, at(n))
    }
}

private fun DrawScope.drawGlow(route: List<Node>, glow: Float, pulse: Float) {
    if (glow <= 0f) return
    val path = Path().apply {
        moveTo(at(route.first()).x, at(route.first()).y)
        route.drop(1).forEach { lineTo(at(it).x, at(it).y) }
    }
    val measure = PathMeasure().apply { setPath(path, false) }
    val lit = Path()
    measure.getSegment(0f, measure.length * glow, lit, true)
    val round = StrokeCap.Round
    drawPath(lit, Accent.copy(alpha = 0.10f), style = Stroke(16f, cap = round, join = StrokeJoin.Round))
    drawPath(lit, Accent.copy(alpha = 0.22f), style = Stroke(7f, cap = round, join = StrokeJoin.Round))
    drawPath(lit, Glow, style = Stroke(2.5f, cap = round, join = StrokeJoin.Round))
    if (glow >= 1f) {
        val head = measure.length * pulse
        val spark = Path()
        measure.getSegment((head - 90f).coerceAtLeast(0f), head, spark, true)
        drawPath(spark, Color.White.copy(alpha = 0.9f), style = Stroke(3.5f, cap = round, join = StrokeJoin.Round))
    }
}

private fun DrawScope.drawEnd(n: Node, text: String, measurer: TextMeasurer) {
    val p = at(n)
    drawCircle(Glow, 5f, p)
    drawCircle(Glow.copy(alpha = 0.3f), 12f, p, style = Stroke(1f))
    val layout = measurer.measure(text, TextStyle(color = TextHigh, fontSize = 15.sp))
    drawText(layout, topLeft = Offset(p.x + 20f, p.y - layout.size.height / 2f))
}

private fun DrawScope.drawTag(slot: Offset, e: Excluded, alpha: Float, measurer: TextMeasurer) {
    val name = measurer.measure(e.candidate.place.name, TextStyle(color = TextHigh.copy(alpha = alpha), fontSize = 15.sp))
    val why = measurer.measure(e.reason, TextStyle(color = Warn.copy(alpha = alpha), fontSize = 14.sp, fontWeight = FontWeight.Medium))
    val w = maxOf(name.size.width, why.size.width) + 24f
    val h = name.size.height + why.size.height + 14f
    val x = (slot.x * size.width - w / 2f).coerceIn(6f, size.width - w - 6f)
    val y = slot.y * size.height - h / 2f
    drawRoundRect(Surface.copy(alpha = 0.9f * alpha), Offset(x, y), Size(w, h), CornerRadius(4f, 4f))
    drawRoundRect(Hairline.copy(alpha = alpha), Offset(x, y), Size(w, h), CornerRadius(4f, 4f), style = Stroke(1f))
    drawText(name, topLeft = Offset(x + 12f, y + 7f))
    drawText(why, topLeft = Offset(x + 12f, y + 7f + name.size.height))
}
