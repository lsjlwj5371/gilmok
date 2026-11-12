package com.gilmok.app.voice

import ai.pleos.playground.stt.SpeechToText
import ai.pleos.playground.stt.listener.ResultListener
import ai.pleos.playground.tts.TextToSpeech
import ai.pleos.playground.tts.listener.EventListener
import android.content.Context
import android.util.Log
import com.gilmok.app.core.debugLog
import java.util.Locale
import ai.pleos.playground.stt.constant.ErrorType as SttError
import ai.pleos.playground.stt.constant.Mode as SttMode
import ai.pleos.playground.stt.listener.OnInitializeListener as SttInit
import ai.pleos.playground.tts.constant.ErrorType as TtsError
import ai.pleos.playground.tts.constant.Mode as TtsMode
import ai.pleos.playground.tts.listener.OnInitializeListener as TtsInit

/** 음성 입출력. 앱 등록 없이 동작하는 온디바이스 모드를 쓴다. */
class VoiceGateway(context: Context) {
    private val stt = SpeechToText(context.applicationContext, SttMode.ON_DEVICE)
    private val tts = TextToSpeech(context.applicationContext, TtsMode.ON_DEVICE)
    @Volatile private var ttsReady = false
    @Volatile private var handler: Listener? = null

    interface Listener {
        fun onLevel(level: Float)
        fun onPartial(text: String)
        fun onFinal(text: String)
        fun onFailed(reason: String)
    }

    private val resultListener = object : ResultListener {
        override fun onReady() = Log.i(TAG, "stt ready").let { }
        override fun onStartedRecognition() = Log.i(TAG, "stt started").let { }
        override fun onUpdated(stt: String, completed: Boolean) {
            debugLog(TAG) { "stt update completed=$completed $stt" }
            if (completed) handler?.onFinal(stt) else handler?.onPartial(stt)
        }

        override fun onUpdatedEpdData(on: Long, off: Long) = Unit
        override fun onUpdatedRms(rms: Double) {
            handler?.onLevel((rms / RMS_MAX).toFloat().coerceIn(0f, 1f))
        }

        override fun onEndedRecognition() = Log.i(TAG, "stt ended").let { }
        override fun onError(errorType: SttError) {
            Log.w(TAG, "stt error $errorType")
            handler?.onFailed(errorType.name)
        }
    }

    private val ttsListener = object : EventListener {
        override fun onStart() = Log.i(TAG, "tts start").let { }
        override fun onReady() = Unit
        override fun onDone() = Log.i(TAG, "tts done").let { }
        override fun onError(errorType: TtsError) = Log.w(TAG, "tts error $errorType").let { }
        override fun onStop() = Unit
        override fun onUpdatedRms(rms: Double) = Unit
    }

    fun connect() {
        stt.initialize(object : SttInit {
            override fun onSuccess() {
                Log.i(TAG, "stt initialized")
                stt.addListener(resultListener)
                stt.setLocale(Locale.KOREA)
            }

            override fun onFailure(errorType: SttError) = Log.w(TAG, "stt init failed $errorType").let { }
        })
        tts.initialize(object : TtsInit {
            override fun onSuccess() {
                Log.i(TAG, "tts initialized")
                tts.addEventListener(ttsListener)
                tts.setLocale(Locale.KOREA)
                ttsReady = true
            }

            override fun onFailure(errorType: TtsError) = Log.w(TAG, "tts init failed $errorType").let { }
        })
    }

    fun listen(listener: Listener) {
        handler = listener
        tts.stop()
        stt.request()
    }

    /** 마이크 없이 인식을 시험한다. 16kHz 16bit mono PCM을 쓴다. */
    fun recognizeFile(pcm: ByteArray, listener: Listener) {
        handler = listener
        // 0.1초(3200바이트)씩 나눠 보낸다. 바이트 배열을 그대로 잘라 불필요한 복사를 줄였다.
        for (start in pcm.indices step 3200) stt.sendAudio(pcm.copyOfRange(start, minOf(start + 3200, pcm.size)))
        stt.completeAudioSend()
    }

    fun stopListening() {
        stt.stop()
    }

    fun speak(text: String) {
        if (ttsReady) tts.speak(text, true)
    }

    fun release() {
        stt.removeListener(resultListener)
        stt.release()
        tts.release()
    }

    private companion object {
        const val TAG = "GilmokVoice"
        const val RMS_MAX = 60.0
    }
}
