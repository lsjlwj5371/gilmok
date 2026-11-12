package com.gilmok.app.core

import android.util.Log
import com.gilmok.app.BuildConfig

/**
 * 발화 원문, 탑승 상태, 배터리처럼 개인 정보가 담긴 로그는 debug 빌드에서만 남긴다.
 * release 빌드에서는 문자열을 만들지도 않는다.
 */
inline fun debugLog(tag: String, message: () -> String) {
    if (BuildConfig.DEBUG) Log.i(tag, message())
}
