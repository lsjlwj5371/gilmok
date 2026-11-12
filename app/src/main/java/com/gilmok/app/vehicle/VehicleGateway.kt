package com.gilmok.app.vehicle

import ai.pleos.playground.vehicle.Vehicle
import ai.pleos.playground.vehicle.api.model.area.SeatArea
import ai.pleos.playground.vehicle.constant.area.SeatValue
import ai.pleos.playground.vehicle.constant.control.VehicleGear
import ai.pleos.playground.vehicle.listener.EvBatteryStateOfChargeListener
import ai.pleos.playground.vehicle.listener.GearSelectionListener
import ai.pleos.playground.vehicle.listener.SeatOccupancyListener
import android.content.Context
import android.util.Log
import com.gilmok.app.core.debugLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class CabinState(
    val passenger: Boolean? = null,
    val rearLeft: Boolean? = null,
    val rearRight: Boolean? = null,
    val socPct: Int? = null,
    val gear: String? = null,
) {
    val rearCount get() = listOf(rearLeft, rearRight).count { it == true }
    val known get() = passenger != null || rearLeft != null || rearRight != null
}

/** 좌석 탑승, 배터리, 기어를 읽는다. 값은 탑승 여부(참/거짓)만 제공되며 무게는 제공되지 않는다. */
class VehicleGateway(context: Context) {
    private val vehicle = Vehicle(context.applicationContext)
    private val _state = MutableStateFlow(CabinState())
    val state: StateFlow<CabinState> = _state.asStateFlow()

    private fun seatListener(apply: CabinState.(Boolean?) -> CabinState) = object : SeatOccupancyListener {
        override fun onSeatOccupancyUpdated(value: Boolean?) {
            debugLog(TAG) { "seat update $value" }
            _state.update { it.apply(occupied(value)) }
        }

        override fun onFailed(e: Exception) = Log.w(TAG, "seat failed", e).let { }
    }

    private val socListener = object : EvBatteryStateOfChargeListener {
        override fun onEvBatteryStateOfChargeUpdated(value: Int?) {
            debugLog(TAG) { "soc $value" }
            _state.update { it.copy(socPct = value) }
        }

        override fun onFailed(e: Exception) = Log.w(TAG, "soc failed", e).let { }
    }

    private val gearListener = object : GearSelectionListener {
        override fun onSelected(gear: VehicleGear?) {
            debugLog(TAG) { "gear $gear" }
            _state.update { it.copy(gear = gear?.name) }
        }

        override fun onFailed(e: Exception) = Log.w(TAG, "gear failed", e).let { }
    }

    /** 에뮬레이터 v2.1.0은 Virtual Console의 탑승 값과 반대로 전달한다. 실차에서 재확인이 필요하다. */
    private fun occupied(raw: Boolean?): Boolean? = raw?.not()

    fun connect() {
        vehicle.initialize()
    }

    fun subscribe() {
        val seat = vehicle.getSeat()
        watch(SeatValue.ROW_1_RIGHT) { copy(passenger = it) }
        watch(SeatValue.ROW_2_LEFT) { copy(rearLeft = it) }
        watch(SeatValue.ROW_2_RIGHT) { copy(rearRight = it) }
        seat.checkSeatOccupancyCapabilities(
            { areas: List<SeatArea> -> Log.i(TAG, "seat areas ${areas.map { it.values.toList() }}") },
            { e: Exception -> Log.w(TAG, "seat capability failed", e) },
        )
        vehicle.getEvBattery().registerEvBatteryStateOfCharge(socListener)
        vehicle.getGear().registerGearSelection(gearListener)
    }

    private fun watch(value: SeatValue, apply: CabinState.(Boolean?) -> CabinState) {
        val area = SeatArea(value)
        val seat = vehicle.getSeat()
        seat.getCurrentSeatOccupancy(
            area,
            { v: Boolean? ->
                debugLog(TAG) { "seat $value = $v" }
                _state.update { it.apply(occupied(v)) }
            },
            { e: Exception -> Log.w(TAG, "seat get failed $value", e) },
        )
        seat.registerSeatOccupancy(area, seatListener(apply))
    }

    fun release() {
        vehicle.release()
    }

    private companion object {
        const val TAG = "GilmokVehicle"
    }
}
