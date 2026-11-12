import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.gilmok.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.gilmok.app"
        minSdk = 28
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    // 서명 정보는 저장소에 올리지 않는 keystore.properties에서 읽는다.
    val keystoreFile = rootProject.file("keystore.properties")
    if (keystoreFile.exists()) {
        val props = Properties().apply { keystoreFile.inputStream().use(::load) }
        signingConfigs {
            create("release") {
                storeFile = rootProject.file(props.getProperty("storeFile"))
                storePassword = props.getProperty("storePassword")
                keyAlias = props.getProperty("keyAlias")
                keyPassword = props.getProperty("keyPassword")
            }
        }
    }

    packaging {
        // 차량과 에뮬레이터에서 쓰지 않는 오래된 CPU용 라이브러리는 뺀다.
        jniLibs.excludes += listOf("lib/mips/**", "lib/mips64/**", "lib/armeabi/**")
    }

    buildTypes {
        // 시연용: 이 PC의 Claude를 중계 서버로 쓴다.
        debug {
            buildConfigField("boolean", "USE_CLAUDE", "true")
        }
        // 제출용: 외부 AI 없이 규칙 기반으로 동작한다. 이후 현대차 스펙으로 교체한다.
        release {
            buildConfigField("boolean", "USE_CLAUDE", "false")
            // 쓰지 않는 코드와 리소스를 빼서 APK를 줄이고 코드 이름을 난독화한다.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }
}

dependencies {
    implementation("ai.pleos.playground:NaviHelper:3.0.5")
    implementation("ai.pleos.playground:Vehicle:2.3.2")
    implementation("ai.pleos.playground:SpeechToText:3.3.1")
    implementation("ai.pleos.playground:TextToSpeech:3.3.1")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
    implementation("androidx.activity:activity-ktx:1.9.3")
    testImplementation("junit:junit:4.13.2")
}
