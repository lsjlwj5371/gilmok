"""길목 데모 영상 합성기. 녹화 클립 위에 기능 설명과 실제 처리 데이터를 그려 MP4로 만든다.

사용법
  python scripts/make_demo.py preview <출력폴더> 12 40 75   # 지정한 초의 프레임만 PNG로
  python scripts/make_demo.py render <출력.mp4>              # 전체 영상
"""
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass, field

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r'C:\Users\user\Desktop\Pleos_공모전\05_데모영상'
CLIPS = os.path.join(BASE, 'clips')
BGM = os.path.join(BASE, 'bgm_잔잔한_150초.wav')
W, H, FPS = 1920, 1080, 30

BG = (7, 9, 12)
SURFACE = (14, 18, 24)
LINE = (35, 42, 51)
TEXT = (243, 245, 247)
MUTED = (139, 149, 161)
ACCENT = (47, 139, 255)
GLOW = (175, 214, 255)
WARN = (232, 160, 140)

FONT_PATH = r'C:\Windows\Fonts\NotoSansKR-VF.ttf'
_fonts = {}


def font(size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key not in _fonts:
        f = ImageFont.truetype(FONT_PATH, size)
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
        _fonts[key] = f
    return _fonts[key]


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def appear(t: float, start: float, dur: float = 0.5) -> float:
    return ease((t - start) / dur)


# ---------- 녹화 클립 ----------

# 녹화(1920x1080)는 에뮬레이터 2560x1440의 0.75배다. 길목과 내비 영역만 잘라 쓴다.
CROP = (640, 67, 1920, 975)
LEFT = (36, 36, 1265, 1044)


class Clip:
    def __init__(self, name: str):
        self.cap = cv2.VideoCapture(os.path.join(CLIPS, f'clip{name}.mp4'))
        self.cache: dict[int, np.ndarray] = {}

    def frame(self, sec: float) -> np.ndarray:
        key = int(sec * 20)
        if key not in self.cache:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, sec) * 1000)
            ok, f = self.cap.read()
            if not ok:
                f = np.zeros((1080, 1920, 3), np.uint8)
            if len(self.cache) > 400:
                self.cache.clear()
            self.cache[key] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        return self.cache[key]


clips = {k: Clip(k) for k in 'ABCD'}


def logs(name: str) -> dict:
    out = {}
    for line in open(os.path.join(CLIPS, f'clip{name}_log.jsonl'), encoding='utf8'):
        line = line.strip()
        if line.startswith('{'):
            d = json.loads(line)
            out[d['kind']] = d['data']
    return out


LOG = {k: logs(k) for k in 'ABCD'}


def place_frame(canvas: Image.Image, frame: np.ndarray, zoom: float = 1.0, full: bool = False) -> tuple:
    """녹화 프레임을 왼쪽 영역에 맞춰 넣는다. zoom 0이면 전체 화면, 1이면 길목·내비 영역."""
    x0, y0, x1, y1 = CROP
    if full:
        zoom = 0.0
    cx0, cy0 = 0 + (x0 - 0) * zoom, 0 + (y0 - 0) * zoom
    cx1, cy1 = 1920 + (x1 - 1920) * zoom, 1080 + (y1 - 1080) * zoom
    sub = Image.fromarray(frame).crop((int(cx0), int(cy0), int(cx1), int(cy1)))
    bw, bh = LEFT[2] - LEFT[0], LEFT[3] - LEFT[1]
    s = min(bw / sub.width, bh / sub.height)
    sub = sub.resize((int(sub.width * s), int(sub.height * s)), Image.LANCZOS)
    px = LEFT[0] + (bw - sub.width) // 2
    py = LEFT[1] + (bh - sub.height) // 2
    canvas.paste(sub, (px, py))
    d = ImageDraw.Draw(canvas)
    d.rectangle((px - 1, py - 1, px + sub.width, py + sub.height), outline=LINE)
    # 원본 녹화 좌표를 화면 좌표로 바꾸는 함수
    return lambda x, y: (px + (x - cx0) * s, py + (y - cy0) * s)


# 녹화 화면 안의 주요 위치 (녹화 1920x1080 좌표)
APP_BOX = (640, 67, 1270, 975)
NAVI_BOX = (1288, 67, 1919, 975)
DRIVE_BOX = (0, 0, 640, 975)
ROW1 = (659, 317, 1250, 435)
NAVI_PANEL = (1306, 85, 1741, 220)
GEAR = (500, 14, 630, 56)

# ---------- 그리기 도구 ----------


def overlay(base: Image.Image) -> tuple:
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


def text(d: ImageDraw.ImageDraw, xy, s: str, size: int, color=TEXT, weight=400, alpha=1.0, anchor='la'):
    d.text(xy, s, font=font(size, weight), fill=(*color, int(255 * alpha)), anchor=anchor)


def box(d, rect, color=ACCENT, alpha=1.0, width=3):
    x0, y0, x1, y1 = rect
    d.rounded_rectangle((x0, y0, x1, y1), radius=4, outline=(*color, int(255 * alpha)), width=width)


def label(d, xy, s, alpha=1.0, color=GLOW, size=20):
    x, y = xy
    f = font(size, 500)
    w = d.textlength(s, font=f)
    d.rounded_rectangle((x, y, x + w + 22, y + size + 16), radius=4, fill=(10, 14, 20, int(230 * alpha)),
                        outline=(*color, int(200 * alpha)), width=1)
    d.text((x + 11, y + 7), s, font=f, fill=(*color, int(255 * alpha)))


def mapped(m, rect):
    a = m(rect[0], rect[1])
    b = m(rect[2], rect[3])
    return (a[0], a[1], b[0], b[1])


def data_panel(d, xy, title: str, rows: list, alpha: float, width=560):
    x, y = xy
    h = 60 + 42 * len(rows)
    d.rounded_rectangle((x, y, x + width, y + h), radius=6, fill=(10, 14, 20, int(235 * alpha)),
                        outline=(*ACCENT, int(180 * alpha)), width=1)
    text(d, (x + 22, y + 16), title, 19, ACCENT, 500, alpha)
    for i, (k, v) in enumerate(rows):
        a = alpha * appear(alpha * 10, 1 + i * 0.6, 1.2) if alpha < 1 else alpha
        text(d, (x + 22, y + 56 + 42 * i), k, 22, MUTED, 400, a)
        text(d, (x + 190, y + 56 + 42 * i), v, 22, TEXT, 500, a)


# ---------- 오른쪽 기능 패널 ----------

PANEL_X = 1310


@dataclass
class Feature:
    no: str
    title: str
    body: list
    points: list = field(default_factory=list)
    tag: str = ''


def draw_panel(d, f: Feature, t: float, lit: set | None = None):
    y = 150
    text(d, (PANEL_X, y), f'FEATURE {f.no}', 20, ACCENT, 500, appear(t, 0.0))
    y += 46
    text(d, (PANEL_X, y), f.title, 44, TEXT, 300, appear(t, 0.15))
    y += 96
    for i, line in enumerate(f.body):
        text(d, (PANEL_X, y), line, 26, TEXT, 350, appear(t, 0.4 + 0.1 * i))
        y += 42
    y += 26
    for i, p in enumerate(f.points):
        on = lit is None or i in lit
        a = appear(t, 0.8 + 0.12 * i) * (1.0 if on else 0.35)
        d.ellipse((PANEL_X, y + 13, PANEL_X + 8, y + 21), fill=(*(ACCENT if on else MUTED), int(255 * a)))
        text(d, (PANEL_X + 22, y), p, 23, TEXT if on else MUTED, 400, a)
        y += 40
    if f.tag:
        text(d, (PANEL_X, 960), f.tag, 19, MUTED, 400, appear(t, 1.2))


def progress(d, scene: int, total: int = 10):
    x0, x1, y = PANEL_X, 1884, 1020
    seg = (x1 - x0) / total
    for i in range(total):
        c = ACCENT if i < scene else LINE
        d.line((x0 + i * seg + 3, y, x0 + (i + 1) * seg - 3, y), fill=(*c, 255), width=3)


def footnote(d, s: str, alpha=1.0):
    text(d, (LEFT[0] + 4, LEFT[3] + 6), s, 15, MUTED, 400, alpha * 0.8)


# ---------- 장면 ----------

TIMELINE = []


def scene(dur):
    def wrap(fn):
        TIMELINE.append((dur, fn))
        return fn
    return wrap


def blank():
    return Image.new('RGB', (W, H), BG)


def ribbon(d, cx, cy, r, t, alpha=1.0, draw_ratio=1.0):
    for k in range(12):
        f = k / 11
        pts = []
        steps = int(160 * draw_ratio)
        for i in range(steps + 1):
            a = 2 * math.pi * i / 160
            wave = math.sin(a * 3 + t * 0.6 + f * 1.1) + 0.5 * math.sin(a * 5 - t * 1.2 + f * 2.2)
            rr = r * (1 + 0.05 * wave * (0.35 + f))
            pts.append((cx + rr * math.cos(a - math.pi / 2), cy + rr * math.sin(a - math.pi / 2)))
        mix = [int(ACCENT[j] * (1 - f) + GLOW[j] * f) for j in range(3)]
        if len(pts) > 1:
            d.line(pts, fill=(*mix, int(255 * alpha * (0.2 + 0.6 * (1 - f) ** 2))), width=1)


@scene(6)
def s_title(t):
    img = blank()
    layer, d = overlay(img)
    ribbon(d, W / 2, 430, 130, t, 1.0, ease(t / 2.2))
    text(d, (W / 2, 640), '길목', 64, TEXT, 300, appear(t, 1.6, 0.8), 'mm')
    text(d, (W / 2, 712), '경로 위 맞춤 경유지 추천', 28, MUTED, 400, appear(t, 2.2, 0.8), 'mm')
    text(d, (W / 2, 820), '현대자동차그룹 차량용 앱 개발 공모전  ·  일단 브랜딩', 20, MUTED, 400, appear(t, 3.0, 0.8), 'mm')
    out = Image.alpha_composite(img.convert('RGBA'), layer)
    fade = min(1.0, (6 - t) / 0.6)
    return Image.blend(blank().convert('RGBA'), out, fade).convert('RGB')


F01 = Feature('01', '내비 옆 1/3 화면', ['Pleos Connect의 3분할 창 정책에 맞춰', '내비 옆 한 칸만 씁니다.', '경로 안내를 가리지 않습니다.'],
              ['세로 841dp 화면 기준으로 설계', '화면에서 빠져도 앱은 종료되지 않음'], 'Pleos Window Policy')


@scene(14)
def s_window(t):
    img = blank()
    zoom = ease((t - 6) / 3)
    m = place_frame(img, clips['A'].frame(2.0), zoom)
    layer, d = overlay(img)
    a = appear(t, 1.0) * (1 - ease((t - 5.5) / 0.6))
    for rect, name in ((DRIVE_BOX, '주행 화면'), (APP_BOX, '길목'), (NAVI_BOX, '내장 내비')):
        r = mapped(m, rect)
        box(d, r, ACCENT if name == '길목' else MUTED, a, 3 if name == '길목' else 2)
        label(d, (r[0] + 14, r[3] - 56), name, a, GLOW if name == '길목' else MUTED)
    if t > 9:
        r = mapped(m, APP_BOX)
        box(d, r, ACCENT, appear(t, 9.2), 3)
        label(d, (r[0] + 14, r[1] + 14), '화면의 1/3', appear(t, 9.4))
    draw_panel(d, F01, t)
    progress(d, 1)
    footnote(d, 'Pleos Connect Emulator v2.1.0 실제 화면')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


F02 = Feature('02', '음성 입력과 안내', ['차량 마이크로 듣고 차 안에서', '바로 글자로 바꿉니다.', '결과는 음성으로도 알려 줍니다.'],
              ['온디바이스 모드: 앱 등록·네트워크 불필요', '한국어 인식, 중간 결과 실시간 표시'], 'SpeechToText 3.3.1 · TextToSpeech 3.3.1')

UTTER = LOG['A']['intent']['utterance']


@scene(16)
def s_voice(t):
    img = blank()
    src = 3.0 if t < 11 else 3.0 + (t - 11) * 0.5
    m = place_frame(img, clips['A'].frame(src))
    layer, d = overlay(img)
    r = mapped(m, APP_BOX)
    shown = UTTER[:int(len(UTTER) * ease((t - 2) / 6))]
    if t > 1.5:
        cx = (r[0] + r[2]) / 2
        d.rounded_rectangle((r[0] + 30, r[3] - 230, r[2] - 30, r[3] - 120), radius=6, fill=(10, 14, 20, 235),
                            outline=(*ACCENT, 200), width=1)
        text(d, (r[0] + 52, r[3] - 218), '음성 인식 결과', 18, ACCENT, 500)
        text(d, (r[0] + 52, r[3] - 180), shown + ('|' if t < 8 and int(t * 3) % 2 else ''), 24, TEXT, 400)
    draw_panel(d, F02, t)
    progress(d, 2)
    footnote(d, '질문 장면은 음성 대신 문장을 직접 넣어 재현했습니다.')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


CAT = {'any': '휴식', 'cafe': '카페', 'restaurant': '식사', 'ev': '충전'}
TAGS = {'pet_ok': '반려견 동반', 'kids_chair': '유아 의자', 'vegan': '채식', 'drive_through': '드라이브스루'}
IA = LOG['A']['intent']
F03 = Feature('03', '의도 파악', ['평소 말투의 요청을 정해진 조건으로', '바꿉니다. 이 조건이 다음 단계의', '거르기 기준이 됩니다.'],
              ['장소 종류, 시간 상한, 필수 조건, 선호 조건', 'Gleo 연동 시 Gleo가 같은 값을 넘겨줌'], 'LLM · 규칙 기반 대체')


@scene(14)
def s_intent(t):
    img = blank()
    m = place_frame(img, clips['A'].frame(5.5 + t * 0.15))
    layer, d = overlay(img)
    r = mapped(m, APP_BOX)
    a = appear(t, 0.6, 0.8)
    x, y = r[0] + 40, r[1] + 120
    d.rounded_rectangle((x, y, x + 560, y + 70), radius=6, fill=(10, 14, 20, int(235 * a)), outline=(*LINE, int(255 * a)))
    text(d, (x + 20, y + 22), f'“{IA["utterance"]}”', 22, TEXT, 400, a)
    text(d, (x + 280, y + 108), '↓', 30, ACCENT, 400, appear(t, 1.6), 'mm')
    req = ', '.join(TAGS.get(k, k) for k in IA['requiredTags']) or '없음'
    rows = [('종류', CAT.get(IA['category'], IA['category'])),
            ('시간 상한', f'{IA["maxDetourMin"]}분' if IA['maxDetourMin'] else '없음'),
            ('필수 조건', req + (' (사용자 기록)' if 'pet_ok' in IA['requiredTags'] else '')),
            ('선호 조건', ', '.join(IA['preferredTags']) or '없음')]
    data_panel(d, (x, y + 140), '의도 파악 결과', rows, appear(t, 2.0, 0.8))
    draw_panel(d, F03, t)
    progress(d, 3)
    footnote(d, 'Pleos Connect Emulator v2.1.0 실제 화면 · 값은 앱 처리 로그')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


RULES = ['이미 지나친 곳', '반대 차선이라 U턴이 필요한 곳', '도착 시각에 문을 닫는 곳', '말한 시간 상한을 넘는 곳', '필수 조건이 맞지 않는 곳']
RULE_OF = {'이미 지나친 구간': 0, '반대 차선 · U턴 필요': 1, '도착 시각엔 영업 종료': 2}


def rule_index(reason: str) -> int:
    if reason in RULE_OF:
        return RULE_OF[reason]
    return 3 if '상한' in reason else 4


F04 = Feature('04', '경로 위 후보 거르기', ['경로와 영업시간처럼 규칙으로', '판정되는 조건은 AI가 아니라', '코드가 처리합니다.'], RULES, 'NaviHelper · CandidateFilter (단위 테스트 7개)')


@scene(18)
def s_filter(t):
    img = blank()
    m = place_frame(img, clips['A'].frame(4.5 + t * 0.5))
    layer, d = overlay(img)
    ex = IA['excluded']
    shown = int(len(ex) * ease((t - 3) / 9))
    lit = {rule_index(e['reason']) for e in ex[:shown]}
    r = mapped(m, APP_BOX)
    x, y = r[0] + 24, r[1] + 20
    total, kept = IA['reviewed'], IA['kept']
    cur = total - shown
    if shown:
        d.rounded_rectangle((x, y + 72, x + 590, y + 92 + shown * 40), radius=6, fill=(10, 14, 20, 225), outline=(*LINE, 255))
    d.rounded_rectangle((x, y, x + 590, y + 64), radius=6, fill=(10, 14, 20, 235), outline=(*ACCENT, 180))
    text(d, (x + 20, y + 18), f'경로 위 {total}곳  →  제외 {shown}곳  →  후보 {cur}곳', 24, TEXT, 500)
    for i, e in enumerate(ex[:shown]):
        yy = y + 86 + i * 40
        a = appear(t, 3 + 9 * i / max(1, len(ex)), 0.4)
        text(d, (x + 4, yy), '×', 24, WARN, 500, a)
        text(d, (x + 34, yy), e['name'], 21, MUTED, 400, a)
        text(d, (x + 300, yy), e['reason'], 21, WARN, 500, a)
    label(d, (r[0] + 14, r[3] - 60), '탐색 화면은 시각 효과이며 실제 도로가 아닙니다', appear(t, 1), MUTED, 17)
    draw_panel(d, F04, t, lit)
    progress(d, 4)
    footnote(d, f'남은 후보 {kept}곳은 다음 단계에서 AI가 순서를 정합니다.')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


def pick(name):
    p = LOG[name]['decision']['picks'][0]
    return p['name'], p['why']


F05 = Feature('05', '개인 맞춤 추천', ['걸러진 후보 중에서 이 사람에게', '맞는 순서로 최대 3곳을 고릅니다.'],
              ['입력: 방문 기록, 선호, 뒷좌석 인원, 배터리', '후보에 없는 장소는 고를 수 없게 막음'], 'Vehicle 2.3.2 · Decision Agent')


@scene(18)
def s_personal(t):
    img = blank()
    seq = [('A', 15.0, '반려견 동승 기록'), ('B', 12.0, '뒷좌석 2명 탑승'), ('C', 13.0, '배터리 28%')]
    if t < 9:
        i = min(2, int(t / 3))
        name, src, tag = seq[i]
        m = place_frame(img, clips[name].frame(src + (t - i * 3) * 0.3))
        layer, d = overlay(img)
        r = mapped(m, APP_BOX)
        label(d, (r[0] + 16, r[1] + 16), tag, 1.0)
    else:
        layer, d = overlay(img)
        a = appear(t, 9.0, 0.8)
        text(d, (LEFT[0] + 40, 140), f'같은 질문  “{UTTER}”', 26, MUTED, 400, a)
        cols = [(tag, *pick(n)) for n, _, tag in seq]
        cw = 370
        for i, (tag, nm, why) in enumerate(cols):
            ca = appear(t, 9.6 + i * 0.6, 0.7)
            x = LEFT[0] + 40 + i * (cw + 24)
            d.rounded_rectangle((x, 230, x + cw, 760), radius=6, fill=(*SURFACE, int(255 * ca)), outline=(*LINE, int(255 * ca)))
            text(d, (x + 26, 262), '입력', 18, MUTED, 400, ca)
            text(d, (x + 26, 294), tag, 26, GLOW, 500, ca)
            d.line((x + 26, 362, x + cw - 26, 362), fill=(*LINE, int(255 * ca)), width=1)
            text(d, (x + 26, 390), '1순위', 18, MUTED, 400, ca)
            words, line, lines = nm.split(' '), '', []
            for w_ in words:
                if d.textlength(line + ' ' + w_, font=font(30, 400)) > cw - 52:
                    lines.append(line)
                    line = w_
                else:
                    line = (line + ' ' + w_).strip()
            lines.append(line)
            for k, ln in enumerate(lines):
                text(d, (x + 26, 424 + k * 42), ln, 30, TEXT, 400, ca)
            text(d, (x + 26, 560), '이유', 18, MUTED, 400, ca)
            text(d, (x + 26, 592), why, 22, TEXT, 400, ca)
    draw_panel(d, F05, t)
    progress(d, 5)
    footnote(d, '같은 질문에 사용자별로 받은 실제 결과입니다.')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


F06 = Feature('06', '추천 카드', ['고르는 데 필요한 정보만', '한 줄에 모았습니다.', '1순위는 음성으로도 안내합니다.'],
              ['사진, 추천 이유, 설명, 추가 시간, 평점', '추가 시간은 내비에 넣어 측정한 실측값'], 'NaviHelper 실측 데이터')

CARD_PARTS = [((666, 324, 810, 429), '사진'), ((818, 333, 1030, 383), '장소 이름 · 추천 이유'),
              ((818, 383, 1150, 418), '설명'), ((1168, 345, 1242, 402), '추가 시간 · 평점')]


@scene(14)
def s_card(t):
    img = blank()
    frame = clips['A'].frame(16.0)
    # 1순위 카드 쪽으로 확대한다.
    z = ease((t - 0.5) / 2.0)
    x0, y0, x1, y1 = CROP
    tx0, ty0, tx1, ty1 = 646, 236, 1262, 566
    rect = (x0 + (tx0 - x0) * z, y0 + (ty0 - y0) * z, x1 + (tx1 - x1) * z, y1 + (ty1 - y1) * z)
    sub = Image.fromarray(frame).crop(tuple(int(v) for v in rect))
    bw, bh = LEFT[2] - LEFT[0], LEFT[3] - LEFT[1]
    s = min(bw / sub.width, bh / sub.height)
    sub = sub.resize((int(sub.width * s), int(sub.height * s)), Image.LANCZOS)
    px, py = LEFT[0] + (bw - sub.width) // 2, LEFT[1] + (bh - sub.height) // 2
    img.paste(sub, (px, py))
    m = lambda X, Y: (px + (X - rect[0]) * s, py + (Y - rect[1]) * s)
    layer, d = overlay(img)
    for i, (rc, name) in enumerate(CARD_PARTS):
        a = appear(t, 3 + i * 1.8, 0.35) * (1 - appear(t, 3 + i * 1.8 + 1.5, 0.3))
        if a <= 0:
            continue
        rr = mapped(m, rc)
        box(d, rr, ACCENT, a)
        label(d, (rr[0], rr[3] + 10) if name == '설명' else (rr[0], rr[1] - 50), name, a)
    if t > 10:
        rr = mapped(m, CARD_PARTS[3][0])
        box(d, rr, GLOW, appear(t, 10.2))
        label(d, (rr[2] - 330, rr[3] + 16), '내장 내비에 넣어 측정한 값', appear(t, 10.2))
    draw_panel(d, F06, t)
    progress(d, 6)
    footnote(d, '장소 이름, 사진, 평점은 시연용 가상 데이터입니다.')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


F07 = Feature('07', '선택하면 내비에 반영', ['말이나 터치로 고르면 내장 내비에', '바로 경유지로 들어갑니다.', '다시 고르면 이전 경유지를 바꿉니다.'],
              ['“첫 번째”, “두 번째” 같은 음성 선택', '내비 경로 변경을 이벤트로 받아 표시'], 'NaviHelper addWaypoint()')


@scene(16)
def s_select(t):
    img = blank()
    if t < 10:
        m = place_frame(img, clips['A'].frame(18.0 + t))
        layer, d = overlay(img)
        if t < 3.5:
            r = mapped(m, APP_BOX)
            label(d, (r[0] + 30, r[3] - 120), '“첫 번째로 가자”', appear(t, 0.3), GLOW, 26)
        a1 = appear(t, 1.0) * (1 - appear(t, 4.0, 0.4))
        box(d, mapped(m, ROW1), ACCENT, a1)
        a2 = appear(t, 4.4)
        rn = mapped(m, NAVI_PANEL)
        box(d, rn, GLOW, a2)
        label(d, (rn[0], rn[3] + 12), '내장 내비: 경유지 1개 포함', a2)
    else:
        m = place_frame(img, clips['B'].frame(12.6 + (t - 10) * 2))
        layer, d = overlay(img)
        r = mapped(m, APP_BOX)
        label(d, (r[0] + 16, r[1] + 16), '터치로 2순위 선택', appear(t, 10.2))
    draw_panel(d, F07, t)
    progress(d, 7)
    footnote(d, 'Pleos Connect Emulator v2.1.0 실제 화면')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


F08 = Feature('08', '주행 중 화면', ['기어가 D에 있으면 움직이는 연출을', '멈추고 필요한 정보만 남깁니다.'],
              ['Pleos 디자인 가이드의 주행 중 규칙 반영', '주행 중에도 앱이 차단되지 않도록 설정'], 'Vehicle 기어 상태 · distractionOptimized')


@scene(12)
def s_drive(t):
    img = blank()
    m = place_frame(img, clips['D'].frame(2.0 + t * 1.1), full=True)
    layer, d = overlay(img)
    g = mapped(m, GEAR)
    a = appear(t, 1.5)
    d.ellipse((g[0] - 10, g[1] - 10, g[2] + 10, g[3] + 10), outline=(*GLOW, int(255 * a)), width=3)
    label(d, (g[0] - 40, g[3] + 18), '기어 P → D', a)
    if t > 5:
        r = mapped(m, APP_BOX)
        label(d, (r[0] + 14, r[1] + 14), '연출 정지 · 정보만 표시', appear(t, 5.2))
    draw_panel(d, F08, t)
    progress(d, 8)
    footnote(d, 'Pleos Connect Emulator v2.1.0 실제 화면')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


F09 = Feature('09', 'Gleo 연동', ['Gleo가 앱의 함수를 직접 부를 수', '있게 스키마와 응답을 구현했습니다.'],
              ['함수 2개: 장소 찾기, 경유지 추가', 'Gleo 7초 제한에 맞춰 즉시 응답', '실제 연동은 스키마 승인 후 가능'], 'Gleo Interface · assets/schema.json')

GLEO = [
    ('Gleo → 길목', 'FIND_STOPS_ON_ROUTE', '{"userRequest": "강아지랑 커피 마실 데 있어?"}'),
    ('길목 → Gleo', 'success', '"Found 3 places along the route. The best match is 숲속정원 카페."'),
    ('Gleo → 길목', 'ADD_STOP_TO_ROUTE', '{"rank": 2}'),
    ('길목 → Gleo', 'success', '"Added 횡성 급속충전 라운지 to the route as a waypoint."'),
]


@scene(12)
def s_gleo(t):
    img = blank()
    layer, d = overlay(img)
    text(d, (LEFT[0] + 40, 130), 'Gleo 호출 시험 로그', 22, MUTED, 400, appear(t, 0.2))
    for i, (who, fn, body) in enumerate(GLEO):
        a = appear(t, 1.0 + i * 1.6, 0.6)
        y = 200 + i * 190
        to_app = who.startswith('Gleo')
        d.rounded_rectangle((LEFT[0] + 40, y, LEFT[2] - 40, y + 150), radius=6, fill=(*SURFACE, int(255 * a)),
                            outline=(*(ACCENT if to_app else LINE), int(255 * a)))
        text(d, (LEFT[0] + 70, y + 24), who, 20, ACCENT if to_app else GLOW, 500, a)
        text(d, (LEFT[0] + 250, y + 22), fn, 24, TEXT, 500, a)
        text(d, (LEFT[0] + 70, y + 82), body, 22, MUTED, 400, a)
    draw_panel(d, F09, t)
    progress(d, 9)
    footnote(d, 'Gleo가 보내는 형식으로 앱을 호출한 실제 응답입니다.')
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')


FLOW = ['음성·Gleo', '의도 파악', '맥락 수집', '후보 거르기', '추천 결정', '내비 반영']


@scene(10)
def s_end(t):
    img = blank()
    layer, d = overlay(img)
    if t < 6.5:
        a_all = 1 - appear(t, 6.0, 0.5)
        n = len(FLOW)
        bw, gap = 250, 50
        x0 = (W - (n * bw + (n - 1) * gap)) / 2
        for i, s in enumerate(FLOW):
            a = appear(t, 0.3 + i * 0.35, 0.4) * a_all
            x = x0 + i * (bw + gap)
            d.rounded_rectangle((x, 380, x + bw, 470), radius=6, fill=(*SURFACE, int(255 * a)), outline=(*ACCENT, int(200 * a)))
            text(d, (x + bw / 2, 425), s, 26, TEXT, 400, a, 'mm')
            if i < n - 1:
                text(d, (x + bw + gap / 2, 425), '→', 26, ACCENT, 400, a, 'mm')
        text(d, (W / 2, 560), 'AI는 걸러진 후보 안에서만 고르고, 응답이 없으면 규칙으로 대신 고릅니다.', 26, TEXT, 350, appear(t, 2.6) * a_all, 'mm')
        text(d, (W / 2, 610), '제출용 APK는 외부 AI 없이 동작합니다.', 26, TEXT, 350, appear(t, 3.0) * a_all, 'mm')
    else:
        ribbon(d, W / 2, 420, 110, t)
        text(d, (W / 2, 600), '길목', 60, TEXT, 300, appear(t, 6.6), 'mm')
        text(d, (W / 2, 668), '일단 브랜딩', 26, MUTED, 400, appear(t, 7.0), 'mm')
    notes = ['장소 이름, 사진, 평점은 시연용 가상 데이터입니다.',
             '이 영상의 추천 AI는 외부 LLM으로 시연했으며, 이후 Pleos LLM SDK로 바꿀 계획입니다.',
             '질문 장면은 음성 대신 문장을 직접 넣어 재현했습니다.']
    for i, s in enumerate(notes):
        text(d, (W / 2, 900 + i * 30), s, 17, MUTED, 400, appear(t, 1.0) * 0.85, 'mm')
    out = Image.alpha_composite(img.convert('RGBA'), layer)
    fade = min(1.0, (10 - t) / 0.8)
    return Image.blend(blank().convert('RGBA'), out, fade).convert('RGB')


# ---------- 출력 ----------

def frame_at(sec: float) -> Image.Image:
    start = 0.0
    for dur, fn in TIMELINE:
        if sec < start + dur:
            local = sec - start
            img = fn(local)
            # 장면 사이를 0.4초 페이드로 잇는다.
            if local < 0.4 and start > 0:
                img = Image.blend(blank(), img, local / 0.4)
            return img
        start += dur
    return blank()


TOTAL = sum(d for d, _ in TIMELINE)


def preview(out_dir, secs):
    os.makedirs(out_dir, exist_ok=True)
    for s in secs:
        frame_at(float(s)).save(os.path.join(out_dir, f'f{float(s):06.1f}.png'))
    print('total', TOTAL, 's')


def render(out_mp4):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    # 메일 첨부 한도(25MB)를 넘지 않도록 평균 비트레이트를 정한다.
    cmd = [ff, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', BGM, '-map', '0:v', '-map', '1:a', '-shortest',
           '-c:v', 'libx264', '-preset', 'slow', '-b:v', '1050k', '-maxrate', '1800k', '-bufsize', '3600k',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-af', f'afade=t=out:st={TOTAL - 4}:d=4,volume=0.8',
           '-map_metadata', '-1', '-metadata', 'title=길목 데모', '-movflags', '+faststart', out_mp4]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = int(TOTAL * FPS)
    for i in range(n):
        p.stdin.write(np.asarray(frame_at(i / FPS), dtype=np.uint8).tobytes())
        if i % 300 == 0:
            print(f'{i / FPS:.0f}s / {TOTAL}s', flush=True)
    p.stdin.close()
    p.wait()
    print('done', out_mp4, f'{os.path.getsize(out_mp4) / 1e6:.1f}MB')


if __name__ == '__main__':
    if sys.argv[1] == 'preview':
        preview(sys.argv[2], sys.argv[3:])
    else:
        render(sys.argv[2])
