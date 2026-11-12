package com.gilmok.app.gleo

import android.content.Context
import android.content.Intent
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import com.gilmok.app.core.debugLog

/**
 * Gleo Interface 연동. Gleo는 assets/schema.json의 함수를 Intent로 호출하고,
 * 앱은 결과를 APP_ACTION_RESPONSE 브로드캐스트로 돌려준다.
 */
object GleoInterface {
    const val FIND_STOPS = "FIND_STOPS_ON_ROUTE"
    const val ADD_STOP = "ADD_STOP_TO_ROUTE"
    private const val RESPONSE_ACTION = "ai.pleos.playground.intent.action.APP_ACTION_RESPONSE"
    private const val TAG = "GilmokGleo"
    private const val MAX_PARAM_CHARS = 2000

    /** 발화로 받는 요청의 최대 길이. 이보다 길면 잘라서 쓴다. */
    const val MAX_REQUEST_CHARS = 200

    data class Call(val function: String, val params: JSONObject)

    fun parse(intent: Intent): Call? {
        val action = intent.action ?: return null
        if (action != FIND_STOPS && action != ADD_STOP) return null
        val raw = intent.getStringExtra("ACTION_PARAM").orEmpty().trim().removeSurrounding("\"")
        if (raw.length > MAX_PARAM_CHARS) {
            Log.w(TAG, "ACTION_PARAM이 너무 김 (${raw.length}자)")
            return Call(action, JSONObject())
        }
        val params = runCatching { JSONObject(raw) }.getOrElse {
            Log.w(TAG, "ACTION_PARAM 해석 실패 (${raw.length}자)")
            JSONObject()
        }
        return Call(action, params)
    }

    /** message는 Gleo 규칙에 따라 영어 문장으로 쓴다. 앱이 직접 음성으로 안내하므로 mode는 silent다. */
    fun respond(context: Context, function: String, status: String, message: String, data: JSONArray? = null) {
        val response = JSONObject().apply {
            put("functionName", function)
            put("status", status)
            put("message", message)
            put("mode", "silent")
            data?.let { put("data", it.toString()) }
        }
        context.sendBroadcast(
            Intent(RESPONSE_ACTION).apply {
                putExtra("packageName", context.packageName)
                putExtra("response", response.toString())
            },
        )
        Log.i(TAG, "callback $function $status")
        debugLog(TAG) { "callback $response" }
    }
}
