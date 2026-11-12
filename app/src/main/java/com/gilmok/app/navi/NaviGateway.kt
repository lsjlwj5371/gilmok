package com.gilmok.app.navi

import ai.pleos.playground.navi.constants.NaviErrorCode
import ai.pleos.playground.navi.constants.WaypointIndex
import ai.pleos.playground.navi.data.DrivingInfo
import ai.pleos.playground.navi.data.RequestWaypointInfo
import ai.pleos.playground.navi.data.RouteInfo
import ai.pleos.playground.navi.helper.NaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener
import android.content.Context
import android.util.Log
import com.gilmok.app.core.Place
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class StopState(val name: String, val remainSec: Int, val distanceM: Int)

data class RouteState(
    val connected: Boolean = false,
    val destination: String = "",
    val remainSec: Int = 0,
    val distanceM: Int = 0,
    val stops: List<StopState> = emptyList(),
    val error: String? = null,
)

/** 내장 내비와의 연결. 경로 안내 자체는 Pleos Connect 내비가 맡는다. */
class NaviGateway(context: Context) {
    private val helper = NaviHelper(context.applicationContext)
    private val _state = MutableStateFlow(RouteState())
    val state: StateFlow<RouteState> = _state.asStateFlow()

    private val listener = object : NaviHelperEventListener {
        override fun onDrivingInfo(drivingInfo: DrivingInfo) {
            val d = drivingInfo.destination ?: return
            // 재탐색 중에는 시간이 0으로 들어오므로 이전 값을 유지한다.
            if (d.duration == 0) return
            _state.update {
                it.copy(
                    destination = d.name,
                    remainSec = d.duration,
                    distanceM = d.distance,
                    stops = drivingInfo.waypoints.map { w -> StopState(w.name, w.duration, w.distance) },
                    error = null,
                )
            }
        }

        override fun onError(errorCode: NaviErrorCode) {
            Log.w(TAG, "navi error $errorCode")
            _state.update { it.copy(error = errorCode.name) }
        }
    }

    fun connect(onReady: () -> Unit) {
        helper.initialize(
            onConnected = {
                helper.addListener(listener)
                _state.update { it.copy(connected = true) }
                onReady()
            },
            onFailed = { e ->
                Log.e(TAG, "connect failed", e)
                _state.update { it.copy(error = "내비 연결 실패") }
            },
        )
    }

    fun startRoute(name: String, lat: Double, lng: Double, address: String) {
        _state.update { it.copy(stops = emptyList()) }
        helper.requestRoute(
            RouteInfo(
                latitude = lat, longitude = lng, displayLongitude = null, displayLatitude = null,
                poiName = name, poiId = "", poiSubId = "0", address = address,
            ),
        )
    }

    fun addStop(place: Place) {
        helper.addWaypoint(
            RequestWaypointInfo(
                latitude = place.lat, longitude = place.lng, waypointIndex = WaypointIndex.FIRST,
                poiId = "", poiName = place.name, poiSubId = "0", address = place.name,
            ),
        )
    }

    fun clearStops() {
        _state.update { it.copy(stops = emptyList()) }
        helper.removeWaypoint(WaypointIndex.ALL)
    }

    fun release() {
        helper.removeListener(listener)
        helper.release()
    }

    private companion object {
        const val TAG = "GilmokNavi"
    }
}
