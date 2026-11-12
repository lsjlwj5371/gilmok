package com.gilmok.app.core

import kotlinx.serialization.Serializable

@Serializable
data class Place(
    val id: String,
    val name: String,
    val category: String,
    val tags: List<String>,
    val lat: Double,
    val lng: Double,
    val rating: Double,
    val blurb: String,
    val closesAt: String,
    val oppositeLane: Boolean,
    val passed: Boolean,
)

/** 시연용 사용자 프로필. 앱이 쌓는 개인 메모리를 대신한다. */
@Serializable
data class Persona(
    val id: String,
    val summary: String,
    val requiredTags: List<String>,
    val preferredTags: List<String>,
    val visits: List<String>,
)

/** 경유지를 실제 내비에 넣어 측정한 값. demo/detours.json */
@Serializable
data class Detour(val id: String, val detourMin: Int, val etaMin: Int)

@Serializable
data class StopIntent(
    val category: String = "any",
    val maxDetourMin: Int? = null,
    val requiredTags: List<String> = emptyList(),
    val preferredTags: List<String> = emptyList(),
)

@Serializable
data class Pick(val id: String, val why: String)

@Serializable
data class Decision(val speech: String, val picks: List<Pick>)

/** 차량 센서로 실제 읽을 수 있는 값. */
data class CabinContext(val rearOccupied: Int, val socPct: Int?)

data class Candidate(val place: Place, val detourMin: Int, val etaMin: Int)

data class Excluded(val candidate: Candidate, val reason: String)

data class FilterResult(val kept: List<Candidate>, val excluded: List<Excluded>)
