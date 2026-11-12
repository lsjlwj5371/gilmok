package com.gilmok.app.core

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** AI 교체 지점. 시연은 Claude 중계 서버를 쓰고, 이후 현대차 스펙 구현으로 바꾼다. */
interface LlmClient {
    val label: String
    suspend fun complete(system: String, user: String): String
}

private val json = Json { ignoreUnknownKeys = true; coerceInputValues = true; isLenient = true }

private fun jsonBody(text: String): String {
    val start = text.indexOf('{')
    val end = text.lastIndexOf('}')
    require(start >= 0 && end > start) { "JSON 응답이 아닙니다" }
    return text.substring(start, end + 1)
}

class IntentAgent(private val llm: LlmClient) {
    suspend fun parse(utterance: String): StopIntent =
        json.decodeFromString(jsonBody(llm.complete(SYSTEM, utterance)))

    private companion object {
        const val SYSTEM = """차량 내 경유지 추천 앱의 의도 파악 단계다. 운전자 발화를 JSON 하나로만 변환한다. 설명을 붙이지 않는다.
형식: {"category":"cafe|restaurant|ev|any","maxDetourMin":숫자 또는 null,"requiredTags":[],"preferredTags":[]}
- category: 커피·카페는 cafe, 식사는 restaurant, 충전은 ev, 그 외 휴식이나 불명확하면 any
- maxDetourMin: 발화에 추가 시간 상한이 있을 때만 숫자
- requiredTags: 발화에서 반드시 지켜야 한다고 말한 조건만
- preferredTags: 발화에서 선호한다고 말한 조건
- 태그 목록: pet_ok, pet_indoor, kids_chair, nursing_room, drive_through, fast, ev_charging, vegan, quiet, parking, bakery, view, meal, coffee"""
    }
}

class DecisionAgent(private val llm: LlmClient) {
    suspend fun decide(utterance: String, persona: Persona, cabin: CabinContext, kept: List<Candidate>): Decision {
        val raw = llm.complete(SYSTEM, buildInput(utterance, persona, cabin, kept))
        val decision: Decision = json.decodeFromString(jsonBody(raw))
        val ids = kept.map { it.place.id }.toSet()
        // 후보 밖의 장소는 받아들이지 않는다.
        val picks = decision.picks.filter { it.id in ids }.distinctBy { it.id }.take(MAX_PICKS)
        require(picks.isNotEmpty()) { "후보에 있는 장소를 고르지 않았습니다" }
        return decision.copy(picks = picks)
    }

    private fun buildInput(utterance: String, persona: Persona, cabin: CabinContext, kept: List<Candidate>): String =
        json.encodeToString(
            buildJsonObject {
                put("utterance", utterance)
                put("persona", persona.summary.ifEmpty { "개인 기록 없음" })
                put("rearSeatsOccupied", cabin.rearOccupied)
                cabin.socPct?.let { put("batteryPct", it) }
                put("memories", buildJsonArray { persona.visits.forEach { add(JsonPrimitive(it)) } })
                put("candidates", buildJsonArray {
                    kept.forEach { c ->
                        add(buildJsonObject {
                            put("id", c.place.id)
                            put("name", c.place.name)
                            put("addedMinutes", c.detourMin)
                            put("rating", c.place.rating)
                            put("tags", c.place.tags.joinToString())
                            put("description", c.place.blurb)
                        })
                    }
                })
            },
        )

    private companion object {
        const val MAX_PICKS = 3
        const val SYSTEM = """차량 내 경유지 추천 앱의 결정 에이전트다. candidates는 경로와 영업시간 검증을 통과한 실제 장소다.
발화, 페르소나, 메모리, 탑승 인원, 배터리를 보고 이 사람에게 맞는 순서로 최대 3곳을 고른다.
- candidates의 id만 쓴다. 사실을 지어내지 않고, 메모리에 있는 내용만 언급한다.
- 개인 기록이 없으면 추가 시간이 적고 평점이 높은 곳을 앞에 둔다.
- why: 화면에 표시할 추천 이유다. 18자 이내의 자연스러운 명사형 구로 쓴다. 예: "자주 찾던 베이커리 분위기", "충전하며 식사 가능"
- speech: 운전 중 듣는 말이다. 차분한 존댓말 한 문장으로, 첫 번째 장소 이름과 이유만 말한다. 쉼표로 어색하게 잇지 않는다.
  좋은 예: "숲속정원 카페를 가장 추천드려요. 반려견과 실내에 함께 있을 수 있어요."
  나쁜 예: "숲속정원 카페입니다, 추가 시간이 0분이라 좋습니다."
JSON 하나로만 답한다: {"speech":"문장","picks":[{"id":"id","why":"이유"}]}"""
    }
}

/** 받침에 맞춰 목적격 조사를 붙인다. */
fun withObjectParticle(word: String): String {
    val last = word.last()
    val hasFinal = last in '가'..'힣' && (last - '가') % 28 != 0
    return word + if (hasFinal) "을" else "를"
}

/** LLM 지연이나 오류 시 쓰는 규칙 기반 결정. */
object FallbackDecider {
    private val TAG_REASONS = mapOf(
        "pet_indoor" to "실내 반려견 동반 가능",
        "quiet" to "조용하게 쉬기 좋은 곳",
        "bakery" to "자주 찾던 베이커리",
        "kids_chair" to "유아 의자 있음",
        "nursing_room" to "수유실 있음",
        "drive_through" to "내리지 않고 주문",
        "fast" to "빠르게 들르기 좋음",
        "ev_charging" to "초급속 충전 가능",
        "vegan" to "모든 메뉴가 채식",
        "meal" to "식사하기 좋은 곳",
        "coffee" to "커피 한잔하기 좋음",
        "parking" to "주차가 편함",
    )

    fun decide(persona: Persona, kept: List<Candidate>): Decision {
        val ranked = kept.sortedWith(
            compareByDescending<Candidate> { c -> persona.preferredTags.count { it in c.place.tags } }
                .thenBy { it.detourMin },
        ).take(3)
        val picks = ranked.map { c ->
            val tag = persona.preferredTags.firstOrNull { it in c.place.tags }
            Pick(c.place.id, TAG_REASONS[tag] ?: "추가 시간이 적은 곳")
        }
        val first = ranked.first().place
        return Decision(
            speech = "${withObjectParticle(first.name)} 가장 추천드려요. ${first.blurb.substringBefore('.')}.",
            picks = picks,
        )
    }
}
