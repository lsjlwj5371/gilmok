package com.gilmok.app.core

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.net.HttpURLConnection
import java.net.URL

/** 에뮬레이터에서 호스트 PC는 10.0.2.2 로 보인다. */
class ClaudeBridgeClient(private val baseUrl: String = "http://10.0.2.2:8787") : LlmClient {
    override val label = "Claude (로컬)"

    override suspend fun complete(system: String, user: String): String = withContext(Dispatchers.IO) {
        val conn = URL("$baseUrl/complete").openConnection() as HttpURLConnection
        try {
            conn.requestMethod = "POST"
            conn.connectTimeout = 3000
            conn.readTimeout = 45000
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            val body = buildJsonObject {
                put("system", system)
                put("user", user)
            }.toString()
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            check(conn.responseCode == 200) { "중계 서버 오류 ${conn.responseCode}" }
            val text = conn.inputStream.bufferedReader(Charsets.UTF_8).readText()
            Json.parseToJsonElement(text).jsonObject.getValue("text").jsonPrimitive.content
        } finally {
            conn.disconnect()
        }
    }
}
