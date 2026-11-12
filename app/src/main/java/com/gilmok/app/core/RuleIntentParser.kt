package com.gilmok.app.core

/** 외부 AI 없이 발화에서 의도를 뽑는다. 제출용 빌드와 AI 장애 시에 쓴다. */
object RuleIntentParser {
    private val MINUTES = Regex("""(\d{1,4})\s*분""")
    private const val MAX_MINUTES = 180

    private val CATEGORY = listOf(
        "ev" to listOf("충전", "배터리"),
        "cafe" to listOf("커피", "카페", "라떼", "음료"),
        "restaurant" to listOf("밥", "점심", "저녁", "아침", "식사", "먹"),
    )

    private val REQUIRED = listOf(
        "pet_ok" to listOf("강아지", "반려견", "반려동물", "댕댕"),
        "kids_chair" to listOf("아이", "애기", "아기", "유아"),
        "vegan" to listOf("채식", "비건"),
        "drive_through" to listOf("드라이브스루", "드라이브 스루", "안 내리"),
    )

    private val PREFERRED = listOf(
        "quiet" to listOf("조용"),
        "parking" to listOf("주차"),
        "view" to listOf("경치", "전망", "뷰"),
        "bakery" to listOf("빵", "베이커리"),
        "fast" to listOf("빨리", "금방", "간단"),
    )

    fun parse(utterance: String): StopIntent {
        val text = utterance.replace(" ", "")
        fun match(words: List<String>) = words.any { it.replace(" ", "") in text }
        return StopIntent(
            category = CATEGORY.firstOrNull { (_, words) -> match(words) }?.first ?: "any",
            maxDetourMin = MINUTES.find(utterance)?.groupValues?.get(1)?.toIntOrNull()?.takeIf { it in 1..MAX_MINUTES },
            requiredTags = REQUIRED.filter { (_, words) -> match(words) }.map { it.first },
            preferredTags = PREFERRED.filter { (_, words) -> match(words) }.map { it.first },
        )
    }
}
