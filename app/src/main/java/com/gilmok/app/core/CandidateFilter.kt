package com.gilmok.app.core

/** 규칙으로 판정되는 후보 제외는 LLM이 아니라 여기서 처리한다. */
object CandidateFilter {
    private val TAG_LABELS = mapOf(
        "pet_ok" to "반려견 동반 불가",
        "pet_indoor" to "실내 반려견 동반 불가",
        "kids_chair" to "유아 의자 없음",
        "nursing_room" to "수유실 없음",
        "drive_through" to "드라이브스루 아님",
        "ev_charging" to "충전기 없음",
        "vegan" to "채식 메뉴 없음",
        "parking" to "주차 불가",
        "quiet" to "조용한 곳 아님",
    )

    fun apply(
        candidates: List<Candidate>,
        intent: StopIntent,
        personaRequired: List<String>,
        nowMin: Int,
    ): FilterResult {
        val required = (intent.requiredTags + personaRequired).distinct()
        val kept = mutableListOf<Candidate>()
        val excluded = mutableListOf<Excluded>()
        for (c in candidates) {
            val reason = reasonToExclude(c, intent, required, nowMin)
            if (reason == null) kept += c else excluded += Excluded(c, reason)
        }
        return FilterResult(kept.sortedBy { it.detourMin }, excluded)
    }

    private fun reasonToExclude(c: Candidate, intent: StopIntent, required: List<String>, nowMin: Int): String? {
        val p = c.place
        if (p.passed) return "이미 지나친 구간"
        if (p.oppositeLane) return "반대 차선 · U턴 필요"
        if (nowMin + c.etaMin >= parseClock(p.closesAt)) return "도착 시각엔 영업 종료"
        intent.maxDetourMin?.let { if (c.detourMin > it) return "시간 상한 ${it}분 초과" }
        if (!matchesCategory(p, intent.category)) return "요청한 종류가 아님"
        required.firstOrNull { it !in p.tags }?.let { return TAG_LABELS[it] ?: "조건 불일치" }
        return null
    }

    private fun matchesCategory(p: Place, category: String): Boolean = when (category) {
        "any" -> true
        "cafe" -> p.category == "cafe" || "coffee" in p.tags
        "restaurant" -> p.category == "restaurant" || "meal" in p.tags
        "ev" -> "ev_charging" in p.tags
        else -> p.category == category
    }

    fun parseClock(hhmm: String): Int {
        val (h, m) = hhmm.split(":").map { it.toInt() }
        return h * 60 + m
    }
}
