# 길목

**가는 길 위에서, 지금 우리에게 맞는 들를 곳을 찾아 주는 Pleos Connect 앱**

운전 중에 "반려견이랑 쉴 만한 곳, 20분 안쪽으로"라고 말하면, 길목은 현재 경로 주변의 후보를 찾습니다. 이어서 차량 상태(탑승 좌석, 배터리, 기어)와 지난 방문 기록을 함께 따져 세 곳을 추천하고, 고른 곳을 내장 내비에 경유지로 바로 넣습니다.

- 팀: 일단 브랜딩
- 패키지: `com.gilmok.app`
- 대상: Pleos Connect (Android Automotive, minSdk 28, targetSdk 34)

## 주요 기능

| # | 기능 | 쓰는 SDK |
|---|---|---|
| 1 | 화면 3분할 중 1/3 창에서 동작 | - |
| 2 | 온디바이스 음성 인식과 음성 안내 | SpeechToText, TextToSpeech |
| 3 | 말에서 조건 파악 (동반자, 허용 추가 시간, 선호) | - |
| 4 | 규칙으로 맞지 않는 후보 제외 (동반 불가, 시간 초과, 영업 종료) | - |
| 5 | 차량 상태에 따른 개인 맞춤 추천 (뒷좌석 탑승, 배터리 잔량) | Vehicle |
| 6 | 사진, 추천 이유, 추가 시간을 담은 추천 카드 | - |
| 7 | 고른 곳을 내장 내비 경유지로 추가 | NaviHelper |
| 8 | 주행 중(기어 D)에는 움직이는 연출을 멈추고 글자 위주 화면 | Vehicle |
| 9 | Gleo 음성 비서에서 바로 호출 (`FIND_STOPS_ON_ROUTE`, `ADD_STOP_TO_ROUTE`) | - |

## 빌드 종류

| 빌드 | 추천 결정 | 비고 |
|---|---|---|
| release | 규칙 기반 (외부 AI 없음) | 제출 APK. R8 축소·난독화, 디버그 명령 차단 |
| debug | 개발용 외부 LLM (PC 중계 서버) | 시연 영상 제작용. 본선에서 Pleos LLM SDK로 교체 예정 |

추천 결정은 `core/Agents.kt`의 `LlmClient` 인터페이스 뒤에 있으므로, 구현만 바꾸면 다른 모델로 교체할 수 있습니다.

## 빌드와 실행

JDK 17과 Pleos Playground SDK 저장소 접근 권한이 필요합니다.

```
gradlew.bat :app:assembleRelease      # 서명 정보가 없으면 서명 없이 빌드됨
gradlew.bat :app:testDebugUnitTest

adb install -r app/build/outputs/apk/release/app-release.apk
adb shell am start --user 10 -n com.gilmok.app/.MainActivity
```

에뮬레이터에서 앱을 켠 뒤 화면 오른쪽 핸들을 왼쪽으로 끌면 주행 화면, 길목, 내비로 3분할됩니다.

```
adb shell input swipe 2547 720 1700 720 700
```

Gleo 호출 시험:

```
adb shell am start --user 10 -a FIND_STOPS_ON_ROUTE -n com.gilmok.app/.MainActivity \
  --es ACTION_PARAM '{"userRequest":"반려견이랑 쉴 곳 20분 안쪽"}'
adb shell am start --user 10 -a ADD_STOP_TO_ROUTE -n com.gilmok.app/.MainActivity \
  --es ACTION_PARAM '{"rank":1}'
```

## 구조

| 위치 | 역할 |
|---|---|
| `core/RuleIntentParser.kt` | 말에서 조건 추출 |
| `core/CandidateFilter.kt` | 규칙으로 판정되는 후보 제외 |
| `core/Agents.kt` | 의도 파악, 결정 에이전트, 규칙 기반 폴백 |
| `core/ClaudeBridgeClient.kt` | debug 빌드 전용 개발용 AI 연결 |
| `voice/VoiceGateway.kt` | 온디바이스 음성 인식과 음성 출력 |
| `vehicle/VehicleGateway.kt` | 좌석, 배터리, 기어 읽기 |
| `navi/NaviGateway.kt` | 내장 내비 경유지 추가 |
| `gleo/GleoInterface.kt` | Gleo 요청 처리와 응답 |
| `ui/` | 화면, 음성 고리, 탐색 연출 |
| `bridge/server.mjs` | debug 빌드용 PC 중계 서버 |
| `scripts/` | 시연 영상 녹화·합성 스크립트 |

## 시연 데이터

- `assets/demo/places.json`: 시연용 가상 장소입니다. 이름, 평점, 리뷰는 실제 정보가 아닙니다.
- `assets/demo/detours.json`: 내장 내비에 경유지를 넣어 실제로 잰 추가 시간입니다.

## 보안과 안정성

- release 빌드에는 INTERNET 권한을 직접 선언하지 않습니다. Pleos 음성 SDK가 선언한 권한만 남습니다.
- 백업 비활성화, 평문 통신 차단. debug 빌드만 로컬 중계 서버(10.0.2.2)와의 평문 통신을 허용합니다.
- Gleo 입력 길이 제한, 허용 시간 1~180분 검증, 민감한 값은 debug 빌드에서만 기록합니다.
