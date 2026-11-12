#!/usr/bin/env bash
# 데모 영상용 클립 A~D를 녹화하고, 그래픽에 쓸 처리 로그를 함께 저장한다.
# 사용법: bash scripts/record_clips.sh <저장 폴더> [클립...]   예: bash scripts/record_clips.sh out A B
export MSYS2_ARG_CONV_EXCL="*"
OUT="${1:-.}"
shift
CLIPS="${*:-A B C D}"
mkdir -p "$OUT"
A=/c/Users/user/AppData/Local/Android/Sdk/platform-tools/adb.exe
C=http://127.0.0.1:8088
Q="잠깐 쉬었다 가자. 10분 넘게 늦으면 싫어"

hb() { curl -s -m 2 -X POST "$C/browser/session?client=gilmok" -o /dev/null; }
wait_s() { for _ in $(seq 1 "$1"); do hb; "$A" shell sleep 1; done; }
seat() { hb; curl -s -m 5 -X POST "$C/vehicle/seat?area=$1&kind=occupied&value=$2" -o /dev/null; }
soc() { hb; curl -s -m 5 -X POST "$C/vehicle/ev-battery?field=soc&value=$1" -o /dev/null; }
gear() { hb; curl -s -m 5 -X POST "$C/vehicle/gear?gear=$1" -o /dev/null; }
app() { "$A" shell am start --user 10 -n com.gilmok.app/.MainActivity "$@" >/dev/null 2>&1; }
say() { "$A" shell "am start --user 10 -n com.gilmok.app/.MainActivity --es cmd say --es text '$1'" >/dev/null 2>&1; }
log() { echo "[$(date +%H:%M:%S)] $*"; }

wait_done() {
  for _ in $(seq 1 30); do
    hb
    "$A" logcat -d -s GilmokDemo:I 2>/dev/null | grep -q '"kind":"decision"' && return
    "$A" shell sleep 1
  done
  log "결정 로그를 받지 못함"
}

rec_start() {
  "$A" logcat -c
  "$A" shell screenrecord --size 1920x1080 --bit-rate 12000000 "/data/local/tmp/clip$1.mp4" &
  REC=$!
  wait_s 1
}

rec_stop() {
  "$A" shell pkill -INT screenrecord
  wait "$REC" 2>/dev/null
  "$A" shell sleep 2
  "$A" pull "/data/local/tmp/clip$1.mp4" "$(cygpath -w "$OUT")\\clip$1.mp4" 2>&1 | tail -1 | cut -c1-80
  "$A" logcat -d -s GilmokDemo:I 2>/dev/null | sed -E 's/^.*GilmokDemo *: //' > "$OUT/clip$1_log.jsonl"
  log "clip$1 저장, 로그 $(wc -l < "$OUT/clip$1_log.jsonl")줄"
}

prepare() {
  "$A" forward tcp:8088 tcp:8088 >/dev/null
  gear Park
  soc 80
  seat passenger false
  seat rear_left false
  seat rear_right false
  "$A" shell am force-stop --user 10 com.gilmok.app
  app
  wait_s 14
  "$A" shell input swipe 2547 720 1700 720 700
  wait_s 3
}

prepare
for clip in $CLIPS; do
  case $clip in
    A)
      app --es cmd persona --es id dog
      wait_s 3
      rec_start A
      wait_s 4
      say "$Q"
      wait_done
      wait_s 6
      say "첫 번째로 가자"
      wait_s 9
      rec_stop A
      ;;
    B)
      app --es cmd persona --es id family
      seat rear_left true
      seat rear_right true
      wait_s 4
      rec_start B
      wait_s 2
      say "$Q"
      wait_done
      wait_s 5
      app --es cmd choose --ei n 1
      wait_s 8
      rec_stop B
      seat rear_left false
      seat rear_right false
      ;;
    C)
      app --es cmd persona --es id ev
      soc 28
      wait_s 4
      rec_start C
      wait_s 2
      say "$Q"
      wait_done
      wait_s 6
      rec_stop C
      ;;
    D)
      app --es cmd persona --es id ev
      soc 28
      gear Park
      wait_s 4
      rec_start D
      wait_s 3
      gear Drive
      wait_s 3
      say "$Q"
      wait_done
      wait_s 6
      rec_stop D
      gear Park
      soc 80
      ;;
  esac
done
log "완료"
