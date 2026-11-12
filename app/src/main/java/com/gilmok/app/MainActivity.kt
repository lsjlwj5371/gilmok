package com.gilmok.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import com.gilmok.app.gleo.GleoInterface
import com.gilmok.app.ui.MainScreen

class MainActivity : ComponentActivity() {
    private val vm: DemoViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MainScreen(vm) }
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private fun handle(i: Intent) {
        GleoInterface.parse(i)?.let {
            vm.handleGleo(it)
            return
        }
        // adb로 시연을 재현하는 명령. 외부 앱이 내비를 조작하지 못하도록 release 빌드에서는 받지 않는다.
        if (!BuildConfig.DEBUG) return
        when (i.getStringExtra("cmd")) {
            "calibrate" -> vm.calibrate(i.getStringExtra("ids")?.split(","))
            "persona" -> i.getStringExtra("id")?.let(vm::usePersona)
            "sample" -> DemoViewModel.SAMPLES.getOrNull(i.getIntExtra("n", 0))?.let { vm.ask(it) }
            "listen" -> vm.toggleListening()
            "choose" -> vm.ui.value.suggestions.getOrNull(i.getIntExtra("n", 0))?.let(vm::choose)
            "reset" -> vm.reset()
            "sttfile" -> vm.testRecognition()
            "say" -> i.getStringExtra("text")?.let(vm::say)
        }
    }
}
