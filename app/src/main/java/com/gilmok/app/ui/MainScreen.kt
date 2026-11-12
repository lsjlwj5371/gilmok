package com.gilmok.app.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.gilmok.app.DemoViewModel
import com.gilmok.app.Stage
import com.gilmok.app.Suggestion
import com.gilmok.app.UiState
import com.gilmok.app.navi.RouteState

val Background = Color(0xFF07090C)
val Surface = Color(0xFF0E1218)
val Hairline = Color(0xFF232A33)
val TextHigh = Color(0xFFF3F5F7)
val TextLow = Color(0xFF8B95A1)
val Accent = Color(0xFF2F8BFF)
val Glow = Color(0xFFAFD6FF)
val Warm = Color(0xFFFFD9B0)
val Warn = Color(0xFFE8A08C)

private val Sharp = RoundedCornerShape(3.dp)

@Composable
fun MainScreen(vm: DemoViewModel) {
    val ui by vm.ui.collectAsState()
    val route by vm.navi.state.collectAsState()
    val cabin by vm.vehicle.state.collectAsState()
    // 운전 중 애니메이션 금지 규칙에 따라 정차 중에만 연출을 켠다.
    val parked = cabin.gear == null || cabin.gear == "GEAR_PARK"
    Column(Modifier.fillMaxSize().background(Background).padding(horizontal = 26.dp, vertical = 18.dp)) {
        Header(route, vm.llmLabel)
        AnimatedContent(
            targetState = ui.stage == Stage.DONE,
            transitionSpec = { fadeIn(tween(600)) togetherWith fadeOut(tween(300)) },
            modifier = Modifier.weight(1f).fillMaxWidth(),
            label = "stage",
        ) { done ->
            if (done) Results(ui, route, vm, parked) else Home(ui, route, vm, parked)
        }
    }
}

@Composable
private fun Header(route: RouteState, llmLabel: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("길목", color = TextHigh, fontSize = 22.sp, fontWeight = FontWeight.Light, letterSpacing = 3.sp)
        Spacer(Modifier.width(14.dp))
        Box(Modifier.width(1.dp).height(18.dp).background(Hairline))
        Spacer(Modifier.width(14.dp))
        val text = when {
            route.remainSec > 0 -> "${route.destination} · ${route.distanceM / 1000}km · ${formatTime(route.remainSec)}"
            route.connected -> "경로를 확인하고 있어요"
            else -> "내비에 연결하고 있어요"
        }
        Text(text, color = TextLow, fontSize = 17.sp)
        Spacer(Modifier.weight(1f))
        if (llmLabel.isNotEmpty()) Text("시연 · $llmLabel", color = TextLow.copy(alpha = 0.55f), fontSize = 13.sp)
    }
    Spacer(Modifier.height(12.dp))
    Box(Modifier.fillMaxWidth().height(1.dp).background(Hairline))
}

@Composable
private fun Home(ui: UiState, route: RouteState, vm: DemoViewModel, parked: Boolean) {
    val network = ui.stage == Stage.SEARCHING && parked
    val veil = if (network) Background.copy(alpha = 0.75f) else Color.Transparent
    Box(Modifier.fillMaxSize()) {
        if (network) SearchNetwork(ui.excluded, route.destination, Modifier.fillMaxSize().padding(top = 10.dp, bottom = 84.dp))
        Column(
            Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = if (network) Arrangement.Bottom else Arrangement.Center,
        ) {
            if (!network) {
                val tap = remember { MutableInteractionSource() }
                VoiceRing(
                    360.dp, ui.stage == Stage.LISTENING, ui.level, parked,
                    Modifier.clickable(tap, null) { vm.toggleListening() },
                )
                Spacer(Modifier.height(18.dp))
            }
            Text(
                when (ui.stage) {
                    Stage.LISTENING -> ui.utterance.ifEmpty { "듣고 있어요" }
                    Stage.SEARCHING -> ui.utterance
                    else -> ui.speech.ifEmpty { "어디 들렀다 갈까요?" }
                },
                color = TextHigh, fontSize = if (network) 22.sp else 32.sp, fontWeight = FontWeight.Light,
                textAlign = TextAlign.Center, lineHeight = 42.sp,
                modifier = Modifier.background(veil).padding(horizontal = 12.dp),
            )
            Spacer(Modifier.height(4.dp))
            Text(
                when (ui.stage) {
                    Stage.LISTENING -> "말씀이 끝나면 바로 찾아 드릴게요"
                    Stage.SEARCHING -> "경로 위 장소를 살펴보고 있어요"
                    else -> "고리를 누르고 말씀해 주세요"
                },
                color = TextLow, fontSize = 18.sp,
                modifier = Modifier.background(veil).padding(horizontal = 12.dp),
            )
        }
    }
}

@Composable
private fun Results(ui: UiState, route: RouteState, vm: DemoViewModel, parked: Boolean) {
    val tap = remember { MutableInteractionSource() }
    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
        VoiceRing(190.dp, false, 0f, parked, Modifier.clickable(tap, null) { vm.toggleListening() })
        ui.heard?.let {
            Text(
                "“$it”", color = Glow, fontSize = 20.sp,
                modifier = Modifier.border(1.dp, Hairline, Sharp).padding(horizontal = 14.dp, vertical = 6.dp),
            )
            Spacer(Modifier.height(10.dp))
        }
        Text(
            ui.speech, color = TextHigh, fontSize = 24.sp, fontWeight = FontWeight.Light,
            textAlign = TextAlign.Center, lineHeight = 34.sp,
        )
        Spacer(Modifier.height(18.dp))
        Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())) {
            ui.suggestions.forEachIndexed { i, s ->
                SuggestionRow(s, i == 0 && ui.addedId == null, s.candidate.place.id == ui.addedId, route, vm) { vm.choose(s) }
            }
            Spacer(Modifier.height(12.dp))
            if (ui.usedFallback) Text("AI 응답이 늦어 기본 기준으로 골랐어요", color = Warn, fontSize = 15.sp)
        }
        Text(
            if (ui.addedId == null) "눌러서 고르거나 “첫 번째로 가자”라고 말씀해 주세요" else "다른 곳으로 바꾸려면 목록에서 골라 주세요",
            color = TextLow, fontSize = 16.sp,
        )
    }
}

@Composable
private fun SuggestionRow(s: Suggestion, top: Boolean, added: Boolean, route: RouteState, vm: DemoViewModel, onClick: () -> Unit) {
    val place = s.candidate.place
    val focus = added || top
    val shape = Modifier.clip(Sharp).then(
        if (focus) Modifier
            .background(Brush.horizontalGradient(listOf(Accent.copy(alpha = 0.16f), Surface)))
            .border(1.dp, if (added) Glow else Accent, Sharp)
        else Modifier,
    )
    Row(
        Modifier.fillMaxWidth().height(158.dp).then(shape).clickable(onClick = onClick).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        vm.image(place.id)?.let { bmp ->
            Image(
                remember(bmp) { bmp.asImageBitmap() }, place.name, contentScale = ContentScale.Crop,
                modifier = Modifier.width(186.dp).fillMaxHeight().clip(Sharp),
            )
        }
        Spacer(Modifier.width(18.dp))
        Column(Modifier.weight(1f)) {
            Text(place.name, color = TextHigh, fontSize = 24.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(5.dp))
            Text(s.why, color = Glow, fontSize = 17.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(5.dp))
            Text(place.blurb, color = TextLow, fontSize = 15.sp, lineHeight = 21.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        Spacer(Modifier.width(14.dp))
        Box(Modifier.width(1.dp).height(84.dp).background(Hairline))
        Spacer(Modifier.width(14.dp))
        Column(Modifier.width(92.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(detourText(s.candidate.detourMin), color = TextHigh, fontSize = 22.sp, fontWeight = FontWeight.Light, textAlign = TextAlign.Center)
            Spacer(Modifier.height(4.dp))
            val status = when {
                !added -> "★ ${place.rating}"
                route.stops.any { it.name == place.name } -> "추가됨"
                else -> "추가 중"
            }
            Text(status, color = if (added) Glow else TextLow, fontSize = 15.sp)
        }
    }
    if (!focus) Box(Modifier.fillMaxWidth().height(1.dp).background(Hairline))
}

private fun detourText(min: Int) = if (min <= 0) "+0분" else "+${min}분"

private fun formatTime(sec: Int): String {
    val h = sec / 3600
    val m = sec % 3600 / 60
    return if (h > 0) "${h}시간 ${m}분" else "${m}분"
}
