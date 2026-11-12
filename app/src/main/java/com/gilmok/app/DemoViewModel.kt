package com.gilmok.app

import android.app.Application
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.gilmok.app.core.CabinContext
import com.gilmok.app.core.Candidate
import com.gilmok.app.core.CandidateFilter
import com.gilmok.app.core.ClaudeBridgeClient
import com.gilmok.app.core.Decision
import com.gilmok.app.core.DecisionAgent
import com.gilmok.app.core.Detour
import com.gilmok.app.core.Excluded
import com.gilmok.app.core.FallbackDecider
import com.gilmok.app.core.IntentAgent
import com.gilmok.app.core.LlmClient
import com.gilmok.app.core.Persona
import com.gilmok.app.core.Place
import com.gilmok.app.core.StopIntent
import com.gilmok.app.core.RuleIntentParser
import com.gilmok.app.core.withObjectParticle
import com.gilmok.app.gleo.GleoInterface
import org.json.JSONArray
import org.json.JSONObject
import com.gilmok.app.navi.NaviGateway
import com.gilmok.app.vehicle.VehicleGateway
import com.gilmok.app.voice.VoiceGateway
import com.gilmok.app.core.debugLog
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.Json

enum class Stage { IDLE, LISTENING, SEARCHING, DONE }

data class Suggestion(val candidate: Candidate, val why: String)

data class UiState(
    val stage: Stage = Stage.IDLE,
    val utterance: String = "",
    val level: Float = 0f,
    val speech: String = "",
    val suggestions: List<Suggestion> = emptyList(),
    val excluded: List<Excluded> = emptyList(),
    val addedId: String? = null,
    val usedFallback: Boolean = false,
    /** 추천 목록이 나온 뒤 사용자가 말한 문장. 화면에 잠깐 보여 준다. */
    val heard: String? = null,
)

class DemoViewModel(app: Application) : AndroidViewModel(app) {
    private val json = Json { ignoreUnknownKeys = true }
    val navi = NaviGateway(app)
    val vehicle = VehicleGateway(app)
    private val voice = VoiceGateway(app)
    private val llm: LlmClient = ClaudeBridgeClient()
    private val intentAgent = IntentAgent(llm)
    private val decisionAgent = DecisionAgent(llm)
    private val places: List<Place> = readAsset("demo/places.json")
    private val detours: Map<String, Detour> = readAsset<List<Detour>>("demo/detours.json").associateBy { it.id }
    private val personas: List<Persona> = readAsset("demo/personas.json")
    private var persona: Persona = personas.first()
    private val images = ConcurrentHashMap<String, Bitmap>()

    /** 진행 중인 탐색과 경유지 추가. 새 요청이 오면 이전 작업을 취소해 결과가 뒤섞이지 않게 한다. */
    private var searchJob: Job? = null
    private var chooseJob: Job? = null
    private var calibrateJob: Job? = null

    /** 탐색 중 예상하지 못한 오류가 나도 앱이 종료되지 않고 처음 화면으로 돌아간다. */
    private val searchErrors = CoroutineExceptionHandler { _, e ->
        Log.e(TAG, "search failed", e)
        _ui.update { it.copy(stage = Stage.IDLE, speech = "잠시 문제가 생겼어요. 다시 말씀해 주세요.") }
    }

    private val _ui = MutableStateFlow(UiState())
    val ui = _ui.asStateFlow()
    private val useClaude = BuildConfig.USE_CLAUDE

    /** 시연 빌드에서만 화면에 AI 출처를 표시한다. */
    val llmLabel get() = if (useClaude) llm.label else ""

    private val voiceListener = object : VoiceGateway.Listener {
        override fun onLevel(level: Float) = _ui.update { it.copy(level = level) }
        override fun onPartial(text: String) = _ui.update { it.copy(utterance = text) }
        override fun onFinal(text: String) {
            if (text.isBlank()) _ui.update { it.copy(stage = Stage.IDLE) } else handleSpeech(text)
        }

        override fun onFailed(reason: String) {
            _ui.update { it.copy(stage = Stage.IDLE, speech = "잘 듣지 못했어요. 다시 말씀해 주세요.") }
        }
    }

    init {
        navi.connect { navi.startRoute(DEST_NAME, DEST_LAT, DEST_LNG, DEST_ADDRESS) }
        vehicle.connect()
        voice.connect()
        viewModelScope.launch {
            delay(2500)
            runCatching { vehicle.subscribe() }.onFailure { Log.w(TAG, "vehicle subscribe failed", it) }
        }
        // 추천 카드 사진을 화면에 그리기 전에 미리 읽어 둔다. 메인 스레드에서 디코딩하지 않기 위해서다.
        viewModelScope.launch(Dispatchers.IO) { places.forEach { image(it.id) } }
    }

    private inline fun <reified T> readAsset(path: String): T {
        val text = getApplication<Application>().assets.open(path).bufferedReader().use { it.readText() }
        return json.decodeFromString(text)
    }

    fun image(id: String): Bitmap? = images[id] ?: runCatching {
        getApplication<Application>().assets.open("demo/images/$id.jpg").use(BitmapFactory::decodeStream)
    }.getOrNull()?.also { images[id] = it }

    /** 시연에서 프로필을 바꾼다. 운전자 화면에는 노출하지 않는다. */
    fun usePersona(id: String) {
        persona = personas.firstOrNull { it.id == id } ?: return
        reset()
    }

    fun reset() {
        searchJob?.cancel()
        chooseJob?.cancel()
        if (_ui.value.addedId != null) navi.clearStops()
        _ui.value = UiState()
    }

    fun toggleListening() {
        if (_ui.value.stage == Stage.LISTENING) {
            voice.stopListening()
            _ui.update { it.copy(stage = Stage.IDLE) }
            return
        }
        _ui.update { it.copy(stage = Stage.LISTENING, utterance = "", level = 0f) }
        voice.listen(voiceListener)
    }

    /** 저장된 음성으로 인식을 시험한다. */
    fun testRecognition() {
        _ui.update { it.copy(stage = Stage.LISTENING, utterance = "") }
        viewModelScope.launch(Dispatchers.IO) {
            val pcm = getApplication<Application>().assets.open("demo/test_voice.pcm").use { it.readBytes() }
            voice.recognizeFile(pcm, voiceListener)
        }
    }

    private fun handleSpeech(text: String) {
        val current = _ui.value
        val index = ORDINALS.indexOfFirst { it in text }
        if (current.suggestions.isNotEmpty() && index in current.suggestions.indices) {
            _ui.update { it.copy(stage = Stage.DONE, heard = text) }
            choose(current.suggestions[index])
            return
        }
        ask(text)
    }

    fun ask(utterance: String, maxDetourMin: Int? = null, onDecided: ((List<Suggestion>) -> Unit)? = null) {
        searchJob?.cancel()
        chooseJob?.cancel()
        if (_ui.value.addedId != null) navi.clearStops()
        _ui.value = UiState(stage = Stage.SEARCHING, utterance = utterance)
        searchJob = viewModelScope.launch(searchErrors) {
            val started = System.currentTimeMillis()
            val parsed = if (!useClaude) {
                RuleIntentParser.parse(utterance)
            } else {
                runCatching { intentAgent.parse(utterance) }.getOrElse {
                    Log.w(TAG, "intent failed", it)
                    RuleIntentParser.parse(utterance)
                }
            }
            val intent = maxDetourMin?.let { parsed.copy(maxDetourMin = it) } ?: parsed
            val candidates = places.map { p ->
                val d = detours[p.id]
                Candidate(p, d?.detourMin ?: 0, d?.etaMin ?: 0)
            }
            val filtered = CandidateFilter.apply(candidates, intent, persona.requiredTags, DEMO_NOW_MIN)
            _ui.update { it.copy(excluded = filtered.excluded) }
            demoLog(
                "intent",
                JSONObject()
                    .put("utterance", utterance)
                    .put("category", intent.category)
                    .put("maxDetourMin", intent.maxDetourMin ?: JSONObject.NULL)
                    .put("requiredTags", JSONArray(intent.requiredTags + persona.requiredTags))
                    .put("preferredTags", JSONArray(intent.preferredTags))
                    .put("reviewed", candidates.size)
                    .put("kept", filtered.kept.size)
                    .put(
                        "excluded",
                        JSONArray(filtered.excluded.map { JSONObject().put("name", it.candidate.place.name).put("reason", it.reason) }),
                    ),
            )
            if (filtered.kept.isEmpty()) {
                finish("조건에 맞는 곳을 찾지 못했어요. 조건을 조금 바꿔서 다시 말씀해 주세요.")
                onDecided?.invoke(emptyList())
                return@launch
            }
            val cabin = vehicle.state.value
            val context = CabinContext(cabin.rearCount, cabin.socPct)
            var usedFallback = false
            val decision: Decision = if (!useClaude) FallbackDecider.decide(persona, filtered.kept) else runCatching {
                withTimeoutOrNull(DECIDE_TIMEOUT_MS) { decisionAgent.decide(utterance, persona, context, filtered.kept) }
                    ?: error("결정 시간 초과")
            }.getOrElse {
                Log.w(TAG, "decision fallback", it)
                usedFallback = true
                FallbackDecider.decide(persona, filtered.kept)
            }
            val byId = filtered.kept.associateBy { it.place.id }
            val suggestions = decision.picks.map { Suggestion(byId.getValue(it.id), it.why) }
            // Gleo는 7초 안에 응답을 받아야 하므로 연출을 기다리지 않고 먼저 알린다.
            onDecided?.invoke(suggestions)
            // 탐색 연출이 끝까지 보이도록 최소 시간을 지킨다.
            delay((MIN_SEARCH_MS - (System.currentTimeMillis() - started)).coerceAtLeast(0))
            _ui.update { it.copy(suggestions = suggestions, usedFallback = usedFallback) }
            demoLog(
                "decision",
                JSONObject()
                    .put("persona", persona.id)
                    .put("rearOccupied", context.rearOccupied)
                    .put("batteryPct", context.socPct ?: JSONObject.NULL)
                    .put("speech", decision.speech)
                    .put(
                        "picks",
                        JSONArray(
                            suggestions.map {
                                JSONObject().put("name", it.candidate.place.name).put("why", it.why).put("addedMinutes", it.candidate.detourMin)
                            },
                        ),
                    ),
            )
            finish(decision.speech)
            Log.i(TAG, "done picks=${suggestions.size} fallback=$usedFallback ${System.currentTimeMillis() - started}ms")
        }
    }

    /** 영상 그래픽에 쓸 실제 처리 결과를 한 줄 JSON으로 남긴다. */
    private fun demoLog(kind: String, data: JSONObject) {
        debugLog(DEMO_TAG) { JSONObject().put("kind", kind).put("data", data).toString() }
    }

    /** 음성 인식 결과가 들어온 것처럼 문장을 처리한다. 시연 녹화용. */
    fun say(text: String) {
        if (text.isBlank()) return
        _ui.update { it.copy(utterance = text) }
        handleSpeech(text)
    }

    /** Gleo가 schema.json의 함수를 호출했을 때 처리하고 결과를 돌려준다. */
    fun handleGleo(call: GleoInterface.Call) {
        val app = getApplication<Application>()
        when (call.function) {
            GleoInterface.FIND_STOPS -> {
                val request = call.params.optString("userRequest").trim().take(GleoInterface.MAX_REQUEST_CHARS).ifBlank {
                    GleoInterface.respond(app, call.function, "asking", "Please tell me what kind of place you want to stop at.")
                    return
                }
                val maxDetour = call.params.optInt("maxDetourMinutes", 0).takeIf { it in 1..MAX_DETOUR_LIMIT }
                ask(request, maxDetour) { found ->
                    if (found.isEmpty()) {
                        GleoInterface.respond(app, call.function, "success", "The search was completed, but no matching places were found along the route.")
                    } else {
                        val data = JSONArray()
                        found.forEachIndexed { i, s ->
                            data.put(
                                JSONObject()
                                    .put("rank", i + 1)
                                    .put("name", s.candidate.place.name)
                                    .put("addedMinutes", s.candidate.detourMin)
                                    .put("reason", s.why),
                            )
                        }
                        GleoInterface.respond(
                            app, call.function, "success",
                            "Found ${found.size} places along the route. The best match is ${found.first().candidate.place.name}.", data,
                        )
                    }
                }
            }
            GleoInterface.ADD_STOP -> {
                val rank = call.params.optInt("rank", 0)
                val s = _ui.value.suggestions.getOrNull(rank - 1)
                if (s == null) {
                    GleoInterface.respond(app, call.function, "fail", "There is no recommended place at rank $rank.")
                    return
                }
                choose(s)
                GleoInterface.respond(app, call.function, "success", "Added ${s.candidate.place.name} to the route as a waypoint.")
            }
        }
    }

    private fun finish(speech: String) {
        _ui.update { it.copy(stage = Stage.DONE, speech = speech) }
        voice.speak(speech)
    }

    fun choose(s: Suggestion) {
        val hadStop = _ui.value.addedId != null
        if (hadStop) navi.clearStops()
        val speech = "${withObjectParticle(s.candidate.place.name)} 경유지로 추가했어요."
        _ui.update { it.copy(addedId = s.candidate.place.id, speech = speech) }
        voice.speak(speech)
        chooseJob?.cancel()
        chooseJob = viewModelScope.launch {
            // 이전 경유지 제거가 끝난 뒤에 넣어야 내비가 처리한다.
            if (hadStop) delay(1500)
            navi.addStop(s.candidate.place)
        }
    }

    /** 후보를 실제 내비에 넣어 추가 시간을 측정한다. 시연 데이터 생성용. */
    fun calibrate(only: List<String>? = null) {
        if (calibrateJob?.isActive == true) return
        calibrateJob = viewModelScope.launch {
            withTimeoutOrNull(60_000) { navi.state.first { it.remainSec > 0 } } ?: run {
                Log.w(TAG, "CAL 경로 없음")
                return@launch
            }
            delay(3000)
            val rows = mutableListOf<String>()
            for (p in places.filter { only == null || it.id in only }) {
                val base = navi.state.value
                navi.addStop(p)
                val s = withTimeoutOrNull(30000) { navi.state.first { st -> st.stops.firstOrNull()?.name == p.name } }
                if (s != null) {
                    val raw = (s.remainSec - base.remainSec) / 60
                    rows += """{"id":"${p.id}","detourMin":${raw.coerceAtLeast(0)},"etaMin":${s.stops.first().remainSec / 60}}"""
                    Log.i(TAG, "CAL ${p.id} ${p.name} detour=$raw")
                }
                navi.clearStops()
                delay(14000)
            }
            Log.i(TAG, "CAL JSON [" + rows.joinToString(",") + "]")
        }
    }

    override fun onCleared() {
        voice.release()
        vehicle.release()
        navi.release()
    }

    companion object {
        private const val TAG = "Gilmok"
        private const val DEMO_TAG = "GilmokDemo"
        private const val MIN_SEARCH_MS = 6000L
        private const val DECIDE_TIMEOUT_MS = 20000L
        private const val MAX_DETOUR_LIMIT = 180
        private val ORDINALS = listOf("첫 번째", "두 번째", "세 번째")
        const val DEST_NAME = "강릉역"
        const val DEST_LAT = 37.7519
        const val DEST_LNG = 128.8761
        const val DEST_ADDRESS = "강원 강릉시 용지로 176"

        /** 시연 시각 10:30 */
        const val DEMO_NOW_MIN = 630

        /** 시연 스크립트가 음성 입력을 대신할 때 쓰는 문장. */
        val SAMPLES = listOf(
            "잠깐 쉬었다 가자. 10분 넘게 늦으면 싫어",
            "가는 길에 커피 한잔 할 데 있어?",
            "점심 먹고 가자",
        )
    }
}
