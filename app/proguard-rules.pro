# Pleos SDK는 내부적으로 서비스 바인딩과 리플렉션을 쓸 수 있으므로 통째로 보존한다.
-keep class ai.pleos.** { *; }
-keep interface ai.pleos.** { *; }
-dontwarn ai.pleos.**

# AIDL로 넘어가는 Parcelable
-keepclassmembers class * implements android.os.Parcelable {
    public static final ** CREATOR;
}

# assets JSON을 읽는 데이터 모델 (kotlinx.serialization)
-keep,includedescriptorclasses class com.gilmok.app.core.**$$serializer { *; }
-keepclassmembers class com.gilmok.app.core.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}

# 오류 로그에서 줄 번호를 볼 수 있게 남긴다.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# Pleos SDK가 내부에서 Gson으로 응답을 해석한다. 제네릭 타입 정보가 지워지면 TypeToken이 실패한다.
-keepattributes Signature,InnerClasses,EnclosingMethod,*Annotation*
-keep class com.google.gson.reflect.TypeToken { *; }
-keep class * extends com.google.gson.reflect.TypeToken
-keep class com.google.gson.** { *; }
-dontwarn com.google.gson.**
