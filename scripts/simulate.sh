#!/usr/bin/env bash
# 시연 흐름을 3분할 화면에서 자동으로 재생하고 녹화한다.
# 사용법: bash scripts/simulate.sh <저장 폴더>
export MSYS2_ARG_CONV_EXCL="*"
OUT="${1:-.}"
A=/c/Users/user/AppData/Local/Android/Sdk/platform-tools/adb.exe
C=http://127.0.0.1:8088

hb() { curl -s -m 2 -X POST "$C/browser/session?client=gilmok" -o /dev/null; }
wait_s() { for _ in $(seq 1 "$1"); do hb; "$A" shell sleep 1; done; }
seat() { hb; curl -s -m 5 -X POST "$C/vehicle/seat?area=$1&kind=occupied&value=$2" -o /dev/null; }
soc() { hb; curl -s -m 5 -X POST "$C/vehicle/ev-battery?field=soc&value=$1" -o /dev/null; }
gear() { hb; curl -s -m 5 -X POST "$C/vehicle/gear?gear=$1" -o /dev/null; }
app() { "$A" shell am start --user 10 -n com.gilmok.app/.MainActivity "$@" >/dev/null 2>&1; }
shot() { "$A" exec-out screencap -p > "$OUT/$1.png"; }
scene() { echo "[$(date +%H:%M:%S)] $1"; }

wait_done() {
  for _ in $(seq 1 30); do
    hb
    "$A" logcat -d 2>/dev/null | grep -qE 'Gilmok +: done' && break
    "$A" shell sleep 1
  done
  "$A" logcat -d 2>/dev/null | grep -E 'Gilmok +: done' | tail -1 | sed -E 's/.*Gilmok +: //' | cut -c1-260
}

"$A" forward tcp:8088 tcp:8088 >/dev/null
gear Park
soc 80
seat passenger true
seat rear_left false
seat rear_right false
"$A" shell am force-stop --user 10 com.gilmok.app
app
scene "준비: 앱 실행과 경로 설정"
wait_s 12
"$A" shell input swipe 2547 720 1700 720 700
wait_s 3

"$A" shell screenrecord --time-limit 170 --size 1280x720 --bit-rate 6000000 /data/local/tmp/gilmok_sim.mp4 &
REC=$!
wait_s 3

scene "장면 1: 반려견 사용자, 음성 질문"
app --es cmd persona --es id dog
wait_s 3
shot s1_idle
"$A" logcat -c
app --es cmd sttfile
wait_s 5
shot s2_search
wait_done
wait_s 5
shot s3_list

scene "장면 2: 첫 번째 장소 선택, 내비 반영"
app --es cmd choose --ei n 0
wait_s 9
shot s4_added

scene "장면 3: 가족 사용자, 같은 흐름에서 다른 추천"
app --es cmd persona --es id family
seat rear_left true
seat rear_right true
wait_s 3
"$A" logcat -c
app --es cmd sample --ei n 0
wait_done
wait_s 5
shot s5_family

scene "장면 4: 사용자가 두 번째 장소를 고름"
app --es cmd choose --ei n 1
wait_s 8
shot s6_second

scene "장면 5: 배터리 28%, 주행 중 질문"
app --es cmd persona --es id ev
soc 28
wait_s 3
gear Drive
wait_s 2
"$A" logcat -c
app --es cmd sample --ei n 0
wait_done
wait_s 5
shot s7_drive
gear Park
soc 80
wait_s 2

"$A" shell pkill -INT screenrecord
wait "$REC" 2>/dev/null
"$A" shell sleep 2
"$A" pull /data/local/tmp/gilmok_sim.mp4 "$(cygpath -w "$OUT")\\gilmok_simulation.mp4" 2>&1 | tail -1 | cut -c1-100
scene "완료"
