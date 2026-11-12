package com.gilmok.app.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CandidateFilterTest {
    private fun candidate(
        id: String,
        detour: Int = 3,
        eta: Int = 60,
        tags: List<String> = listOf("coffee"),
        category: String = "cafe",
        closesAt: String = "22:00",
        opposite: Boolean = false,
        passed: Boolean = false,
    ) = Candidate(
        Place(id, id, category, tags, 0.0, 0.0, 4.0, "", closesAt, opposite, passed),
        detour,
        eta,
    )

    private val now = CandidateFilter.parseClock("10:30")

    private fun reasonOf(c: Candidate, intent: StopIntent = StopIntent(), required: List<String> = emptyList()) =
        CandidateFilter.apply(listOf(c), intent, required, now).excluded.singleOrNull()?.reason

    @Test fun `지나친 곳을 제외한다`() = assertEquals("이미 지나친 구간", reasonOf(candidate("a", passed = true)))

    @Test fun `반대 차선을 제외한다`() = assertEquals("반대 차선 · U턴 필요", reasonOf(candidate("a", opposite = true)))

    @Test fun `도착 시각 기준으로 영업 종료를 판단한다`() {
        assertEquals("도착 시각엔 영업 종료", reasonOf(candidate("a", eta = 120, closesAt = "12:00")))
        assertEquals(null, reasonOf(candidate("a", eta = 60, closesAt = "12:00")))
    }

    @Test fun `시간 상한을 넘으면 제외한다`() =
        assertEquals("시간 상한 10분 초과", reasonOf(candidate("a", detour = 11), StopIntent(maxDetourMin = 10)))

    @Test fun `페르소나 필수 조건을 적용한다`() =
        assertEquals("반려견 동반 불가", reasonOf(candidate("a"), required = listOf("pet_ok")))

    @Test fun `종류가 맞지 않으면 제외한다`() =
        assertEquals("요청한 종류가 아님", reasonOf(candidate("a", tags = listOf("meal"), category = "restaurant"), StopIntent(category = "cafe")))

    @Test fun `남은 후보는 추가 시간순으로 정렬한다`() {
        val r = CandidateFilter.apply(listOf(candidate("b", detour = 7), candidate("a", detour = 2)), StopIntent(), emptyList(), now)
        assertEquals(listOf("a", "b"), r.kept.map { it.place.id })
        assertTrue(r.excluded.isEmpty())
    }
}
