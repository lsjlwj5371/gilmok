package com.gilmok.app.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RuleIntentParserTest {
    @Test fun `시간 상한을 읽는다`() {
        val i = RuleIntentParser.parse("잠깐 쉬었다 가자. 10분 넘게 늦으면 싫어")
        assertEquals("any", i.category)
        assertEquals(10, i.maxDetourMin)
    }

    @Test fun `커피는 카페로 본다`() = assertEquals("cafe", RuleIntentParser.parse("가는 길에 커피 한잔 할 데 있어?").category)

    @Test fun `식사는 식당으로 본다`() = assertEquals("restaurant", RuleIntentParser.parse("점심 먹고 가자").category)

    @Test fun `충전이 가장 우선이다`() = assertEquals("ev", RuleIntentParser.parse("충전하면서 밥 먹자").category)

    @Test fun `강아지는 필수 조건이 된다`() =
        assertEquals(listOf("pet_ok"), RuleIntentParser.parse("강아지랑 갈 수 있는 카페").requiredTags)

    @Test fun `터무니없이 큰 숫자는 무시한다`() {
        assertNull(RuleIntentParser.parse("999999999999분 안에 가자").maxDetourMin)
        assertNull(RuleIntentParser.parse("0분").maxDetourMin)
    }

    @Test fun `조건이 없으면 비워 둔다`() {
        val i = RuleIntentParser.parse("어디 들렀다 가자")
        assertNull(i.maxDetourMin)
        assertEquals(emptyList<String>(), i.requiredTags)
    }
}
