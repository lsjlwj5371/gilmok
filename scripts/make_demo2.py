"""길목 데모 영상 v2. 녹화 화면을 기울어진 기기 화면처럼 띄우고, 기능마다 화면을 멈춰 해당 부분을 강조한다.

사용법
  python scripts/make_demo2.py preview <출력폴더> 10 30 50
  python scripts/make_demo2.py render <출력.mp4>
"""
import json
import math
import os
import subprocess
import sys

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r'C:\Users\user\Desktop\Pleos_공모전\05_데모영상'
CLIPS = os.path.join(BASE, 'clips')
BGM = os.path.join(BASE, 'bgm_100bpm_150초.wav')
W, H, FPS = 1920, 1080, 30

TEXT = (243, 245, 247)
MUTED = (150, 160, 172)
ACCENT = (47, 139, 255)
GLOW = (175, 214, 255)
WARN = (238, 166, 146)


# ---------- 글꼴 (페이퍼로지) ----------

def _font_dir():
    for d in (os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Windows\Fonts'), r'C:\Windows\Fonts'):
        if os.path.exists(os.path.join(d, 'Paperlogy-4Regular.ttf')):
            return d
    raise SystemExit('페이퍼로지 글꼴을 찾지 못했습니다.')


FONT_DIR = _font_dir()
WEIGHTS = {200: '2ExtraLight', 300: '3Light', 400: '4Regular', 500: '5Medium', 600: '6SemiBold', 700: '7Bold'}
_fonts = {}


def font(size, weight=400):
    key = (size, weight)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, f'Paperlogy-{WEIGHTS[weight]}.ttf'), size)
    return _fonts[key]


# ---------- 시간 함수 ----------

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def win(t, a, b, fade=0.45):
    """a~b 구간에서 1, 앞뒤 fade 동안 부드럽게 0으로."""
    return ease_io((t - a) / fade) * (1 - ease_io((t - (b - fade)) / fade))


def lerp(a, b, x):
    return a + (b - a) * x


def lerp_t(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


# ---------- 녹화 클립과 로그 ----------

class Clip:
    def __init__(self, name):
        self.cap = cv2.VideoCapture(os.path.join(CLIPS, f'clip{name}.mp4'))
        self.cache = {}

    def frame(self, sec):
        key = round(max(0.0, sec) * 30)
        if key not in self.cache:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, key / 30 * 1000)
            ok, f = self.cap.read()
            if not ok:
                f = np.zeros((1080, 1920, 3), np.uint8)
            if len(self.cache) > 240:
                self.cache.clear()
            self.cache[key] = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        return self.cache[key]


clips = {k: Clip(k) for k in 'ABCD'}


def read_log(name):
    out = {}
    for line in open(os.path.join(CLIPS, f'clip{name}_log.jsonl'), encoding='utf8'):
        if line.strip().startswith('{'):
            d = json.loads(line)
            out[d['kind']] = d['data']
    return out


LOG = {k: read_log(k) for k in 'ABCD'}
IA = LOG['A']['intent']
UTTER = IA['utterance']

# 녹화(1920x1080) 안의 위치
FULL = (0, 0, 1920, 1080)
APP = (640, 67, 1270, 975)
NAVI = (1288, 67, 1919, 975)
DRIVE = (0, 0, 640, 975)
ROW1 = (659, 317, 1250, 435)
ROW2 = (659, 452, 1250, 570)
NAVI_PANEL = (1306, 85, 1741, 220)
GEAR = (497, 10, 632, 60)
CAPTION = (670, 900, 1240, 975)
CARD_PARTS = [((666, 324, 810, 429), '사진'), ((818, 333, 1030, 383), '장소 이름 · 추천 이유'),
              ((818, 383, 1150, 418), '설명'), ((1168, 345, 1242, 402), '추가 시간 · 평점')]


def around(rect, pad_x=0.0, aspect=16 / 9, min_w=0):
    """rect를 감싸는 16:9 카메라 영역."""
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = max(x1 - x0 + 2 * pad_x, (y1 - y0) * aspect * 1.08, min_w)
    w = min(w, 1920)
    h = w / aspect
    cx = clamp(cx, w / 2, 1920 - w / 2)
    cy = clamp(cy, h / 2, 1080 - h / 2)
    return (cx, cy, w)


CAM_FULL = (960, 540, 1920)
CAM_APP = around(APP, 260)
CAM_APP_NAVI = around((640, 67, 1919, 975), 30)

# ---------- 배경 ----------


def make_background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.zeros((H, W, 3), np.float32)
    base[:] = (6, 8, 12)
    for (cx, cy, r, col, k) in ((520, 260, 900, (20, 52, 110), 0.55), (1650, 900, 800, (40, 30, 60), 0.25)):
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
        glow = np.clip(1 - d, 0, 1) ** 2 * k
        base += glow[..., None] * np.array(col, np.float32)
    vign = 1 - 0.35 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    return np.clip(base * vign[..., None], 0, 255)


BG = make_background()

# ---------- 기기 화면 카드 ----------

CW, CH = 1240, 698
CARD_CENTER = (700, 548)
RADIUS = 22


def rounded_mask(w, h, r):
    m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (r, 0), (w - r, h), 255, -1)
    cv2.rectangle(m, (0, r), (w, h - r), 255, -1)
    for cx, cy in ((r, r), (w - r - 1, r), (r, h - r - 1), (w - r - 1, h - r - 1)):
        cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m.astype(np.float32) / 255


CARD_MASK = rounded_mask(CW, CH, RADIUS)


def camera_crop(frame, cam):
    cx, cy, w = cam
    h = w * 9 / 16
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    sub = frame[max(0, y0):max(0, y0) + int(h), max(0, x0):max(0, x0) + int(w)]
    return cv2.resize(sub, (CW, CH), interpolation=cv2.INTER_AREA if w > CW else cv2.INTER_CUBIC)


def to_card(rect, cam):
    """녹화 좌표의 사각형을 카드 좌표로."""
    cx, cy, w = cam
    h = w * 9 / 16
    s = CW / w
    x0, y0 = cx - w / 2, cy - h / 2
    return ((rect[0] - x0) * s, (rect[1] - y0) * s, (rect[2] - x0) * s, (rect[3] - y0) * s)


def spotlight(card, rect, strength):
    if strength <= 0.001:
        return card
    small = np.zeros((CH // 4, CW // 4), np.float32)
    x0, y0, x1, y1 = [int(v / 4) for v in rect]
    cv2.rectangle(small, (x0, y0), (x1, y1), 1.0, -1)
    small = cv2.GaussianBlur(small, (0, 0), 6)
    hole = cv2.resize(small, (CW, CH), interpolation=cv2.INTER_LINEAR)
    dim = 1 - strength * 0.7 * (1 - hole)
    out = card * dim[..., None]
    # 강조 영역 테두리의 빛
    glow = np.zeros((CH, CW), np.float32)
    cv2.rectangle(glow, (int(rect[0]), int(rect[1])), (int(rect[2]), int(rect[3])), 1.0, 2, cv2.LINE_AA)
    soft = cv2.GaussianBlur(glow, (0, 0), 7) * 2.2
    edge = np.clip(glow + soft, 0, 1) * strength
    out = out * (1 - edge[..., None] * 0.6) + edge[..., None] * np.array(GLOW, np.float32) * 0.6 + glow[..., None] * strength * np.array(GLOW, np.float32) * 0.35
    return np.clip(out, 0, 255)


def card_quad(tilt_deg, scale, center):
    """세로축으로 tilt만큼 돌린 카드의 화면 네 꼭짓점 (원근 적용)."""
    a = math.radians(tilt_deg)
    d = 2600.0
    hw, hh = CW * scale / 2, CH * scale / 2
    pts = []
    for x, y in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        X, Z = x * math.cos(a), x * math.sin(a)
        k = d / (d + Z)
        pts.append((center[0] + X * k, center[1] + y * k))
    return np.array(pts, np.float32)


def composite_card(canvas, card, quad, alpha=1.0):
    src = np.array([(0, 0), (CW, 0), (CW, CH), (0, CH)], np.float32)
    M = cv2.getPerspectiveTransform(src, quad)
    rgba = np.dstack([card, CARD_MASK * 255]).astype(np.float32)
    warped = cv2.warpPerspective(rgba, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    a = warped[..., 3:4] / 255 * alpha
    # 그림자: 아래로 떨어진 부드러운 그늘
    sh = cv2.resize(warped[..., 3], (W // 4, H // 4))
    sh = cv2.GaussianBlur(sh, (0, 0), 14)
    sh = np.roll(cv2.resize(sh, (W, H)), 46, axis=0)[..., None] / 255 * 0.75 * alpha
    canvas = canvas * (1 - sh)
    # 가장자리의 얇은 빛 테두리
    edge = np.zeros((H, W), np.float32)
    cv2.polylines(edge, [quad.astype(np.int32)], True, 1.0, 1, cv2.LINE_AA)
    canvas = canvas * (1 - a) + warped[..., :3] * a
    canvas = canvas + edge[..., None] * np.array((60, 80, 110), np.float32) * alpha
    return canvas


# ---------- 글자와 패널 ----------

class Layer:
    def __init__(self):
        self.img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def text(self, xy, s, size, color=TEXT, weight=400, alpha=1.0, anchor='la'):
        if alpha <= 0.01:
            return
        self.d.text(xy, s, font=font(size, weight), fill=(*color, int(255 * clamp(alpha))), anchor=anchor)

    def rise(self, xy, s, size, color, weight, t, start, anchor='la', exit_alpha=1.0):
        a = ease_out((t - start) / 0.8) * exit_alpha
        dy = (1 - ease_out((t - start) / 0.8)) * 26
        self.text((xy[0], xy[1] + dy), s, size, color, weight, a, anchor)

    def glass(self, rect, alpha=1.0, outline=ACCENT):
        if alpha <= 0.01:
            return
        x0, y0, x1, y1 = rect
        self.d.rounded_rectangle((x0, y0 + 14, x1, y1 + 14), radius=16, fill=(0, 0, 0, int(90 * alpha)))
        self.d.rounded_rectangle(rect, radius=16, fill=(14, 20, 30, int(246 * alpha)), outline=(*outline, int(150 * alpha)), width=1)

    def chip(self, xy, s, alpha=1.0, color=GLOW, size=21):
        if alpha <= 0.01:
            return
        f = font(size, 500)
        w = self.d.textlength(s, font=f)
        x, y = xy
        self.d.rounded_rectangle((x, y, x + w + 30, y + size + 22), radius=(size + 22) // 2,
                                 fill=(10, 16, 26, int(235 * alpha)), outline=(*color, int(210 * alpha)), width=1)
        self.d.text((x + 15, y + 10), s, font=f, fill=(*color, int(255 * alpha)))

    def over(self, canvas):
        a = np.asarray(self.img, np.float32)
        al = a[..., 3:4] / 255
        return canvas * (1 - al) + a[..., :3] * al


TEXT_X = 1395

# 기능마다 화면 아래에 차례로 뜨는 설명 자막. 문제, 동작, 효과 순서로 짚는다.
CAPTIONS = {
    1: ['운전 중에는 내비 화면을 가릴 수 없습니다.',
        '길목은 3분할 화면 중 한 칸에서만 동작합니다.',
        '경로 안내를 그대로 보면서 바로 옆에서 추천을 받습니다.'],
    2: ['고리를 누르고 평소 말투로 말하면 됩니다.',
        '음성은 차 안에서 바로 글자로 바뀌어 화면 아래에 뜹니다.',
        '인터넷이 끊긴 구간에서도 인식합니다.'],
    3: ['“10분 넘게 늦으면 싫어”는 시간 상한 10분이 됩니다.',
        '반려견과 다닌 기록이 있으면 반려견 동반이 필수 조건이 됩니다.',
        '말하지 않은 조건은 사용자 기록에서 채웁니다.'],
    4: ['경로 위 후보 10곳을 하나씩 확인합니다.',
        '지나친 곳, U턴이 필요한 곳, 도착할 때 문 닫는 곳을 뺍니다.',
        'AI가 아니라 코드가 판정하므로 결과가 매번 같습니다.'],
    5: [(0.4, 3.0, '반려견과 다닌 기록이 있으면 함께 들어갈 수 있는 카페가 1순위입니다.'),
        (3.0, 6.0, '뒷좌석에 두 명이 타면 수유실과 유아 의자가 있는 곳이 먼저입니다.'),
        (6.0, 9.2, '배터리가 28%면 충전하면서 쉴 수 있는 곳을 먼저 추천합니다.'),
        (9.6, 17.6, '같은 질문이어도 차 안 상황에 따라 답이 달라집니다.')],
    6: [(1.0, 4.8, '사진으로 어떤 곳인지 먼저 보여 줍니다.'),
        (4.8, 7.0, '왜 추천했는지는 이유 한 줄로 적었습니다.'),
        (7.0, 9.2, '설명에는 분위기와 편의 시설을 담았습니다.'),
        (9.2, 12.6, '추가 시간은 내장 내비에 실제로 넣어 잰 값입니다.')],
    7: ['“첫 번째로 가자”라고 말하면 바로 경유지가 됩니다.',
        '목적지를 다시 검색하거나 길찾기를 누를 필요가 없습니다.',
        '터치로 다른 곳을 고르면 이전 경유지를 바꿔 넣습니다.'],
    8: ['기어를 D로 바꾸면 화면이 주행 모드로 바뀝니다.',
        '움직이는 연출은 멈추고 글자와 정보만 남깁니다.',
        'Pleos 디자인 가이드의 주행 중 규칙을 따랐습니다.'],
    9: ['Gleo에게 말해도 길목이 찾아 줍니다.',
        'Gleo가 길목의 함수를 부르면 7초 안에 결과를 돌려줍니다.',
        '“두 번째 곳 넣어 줘”라고 하면 경유지 추가까지 이어집니다.'],
}
CAP_X, CAP_Y = 700, 968


def caption(layer, no, t, dur):
    lines = CAPTIONS.get(no)
    if not lines:
        return
    if isinstance(lines[0], tuple):
        spans = lines
    else:
        start, end = 1.2, dur - 0.4
        seg = (end - start) / len(lines)
        spans = [(start + i * seg, start + (i + 1) * seg, ln) for i, ln in enumerate(lines)]
    k = next((i for i, (a0, b0, _) in enumerate(spans) if a0 <= t < b0), None)
    if k is None:
        return
    seg = spans[k][1] - spans[k][0]
    local = t - spans[k][0]
    lines = [x[2] for x in spans]
    a = ease_out(local / 0.5) * (1 - ease_io((local - (seg - 0.4)) / 0.4))
    dy = (1 - ease_out(local / 0.6)) * 16
    f = font(30, 500)
    w = layer.d.textlength(lines[k], font=f)
    # 글자 뒤에 아주 옅은 띠를 깔아 화면 위에서도 읽히게 한다.
    layer.d.rounded_rectangle((CAP_X - w / 2 - 28, CAP_Y - 30 + dy, CAP_X + w / 2 + 28, CAP_Y + 30 + dy), radius=30,
                              fill=(8, 12, 20, int(170 * a)))
    layer.text((CAP_X, CAP_Y + dy), lines[k], 30, TEXT, 500, a, 'mm')
    # 몇 번째 문장인지 점으로 표시
    for i in range(len(lines)):
        c = GLOW if i == k else (70, 80, 96)
        x = CAP_X - (len(lines) - 1) * 9 + i * 18
        layer.d.ellipse((x - 3, CAP_Y + 44, x + 3, CAP_Y + 50), fill=(*c, int(255 * a)))



def feature_text(layer, no, title, lines, tags, t, dur):
    caption(layer, no, t, dur)
    out = 1 - ease_io((t - (dur - 0.5)) / 0.5)
    layer.rise((TEXT_X, 300), f'{no:02d}', 22, ACCENT, 600, t, 0.2, exit_alpha=out)
    layer.rise((TEXT_X, 340), title, 50, TEXT, 600, t, 0.35, exit_alpha=out)
    for i, ln in enumerate(lines):
        layer.rise((TEXT_X, 430 + i * 44), ln, 26, (210, 216, 224), 300, t, 0.6 + 0.1 * i, exit_alpha=out)
    y = 430 + len(lines) * 44 + 34
    for i, tg in enumerate(tags):
        layer.rise((TEXT_X, y + i * 34), tg, 19, MUTED, 400, t, 1.0 + 0.1 * i, exit_alpha=out)


def progress(layer, i, total=9):
    x0, y = TEXT_X, 1000
    for k in range(total):
        c = ACCENT if k < i else (40, 48, 60)
        layer.d.line((x0 + k * 46, y, x0 + k * 46 + 36, y), fill=(*c, 255), width=3)


def card_chip(card_layer, rect_card, s, alpha, below=False):
    x = rect_card[0]
    y = rect_card[3] + 14 if below else rect_card[1] - 50
    card_layer.chip((x, y), s, alpha)


def ribbon(canvas, cx, cy, r, t, alpha=1.0, draw=1.0):
    layer = np.zeros((H, W, 3), np.float32)
    steps = 200
    for k in range(16):
        f = k / 15
        pts = []
        for i in range(int(steps * draw) + 1):
            a = 2 * math.pi * i / steps
            wave = math.sin(a * 3 + t * 2.1 + f * 1.3) + 0.55 * math.sin(a * 5 - t * 3.1 + f * 2.4)
            rr = r * (1 + 0.075 * wave * (0.3 + f)) * (1 + 0.03 * math.sin(t * 1.05))
            ang = a - math.pi / 2 + t * 0.35
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        if len(pts) < 2:
            continue
        mix = np.array([lerp(ACCENT[j], GLOW[j], f) for j in range(3)], np.float32)
        wgt = (1 - f) ** 2
        cv2.polylines(layer, [np.array(pts, np.int32)], False, (mix * (0.35 + 0.65 * wgt)).tolist(), 2 if wgt > 0.5 else 1, cv2.LINE_AA)
    glow = cv2.GaussianBlur(layer, (0, 0), 10)
    return np.clip(canvas + (layer + glow * 1.6) * alpha, 0, 255)


# ---------- 장면 ----------
# 각 장면은 state(t)를 돌려준다:
#   clip, src(녹화 시각), cam(카메라), tilt(기울기), scale, spot(카드 좌표 계산 전 녹화 좌표, 강도), card_alpha,
#   draw(layer, card_layer, t) : 글자와 패널

SCENES = []


def scene(dur):
    def wrap(fn):
        SCENES.append((dur, fn))
        return fn
    return wrap


def hold_then(t, start, play_from, rate, freeze_at=None):
    """start 전에는 play_from에 멈춰 있다가 rate 속도로 재생, freeze_at에서 멈춘다."""
    src = play_from + max(0.0, t - start) * rate
    if freeze_at is not None:
        src = min(src, freeze_at)
    return src


@scene(6.5)
def s_title(t):
    def draw(layer, card_layer, canvas):
        canvas = ribbon(canvas, W / 2, 430, 150, t, ease_out(t / 1.5), ease_out(t / 2.0))
        layer.rise((W / 2, 660), '길목', 92, TEXT, 600, t, 1.4, 'mm', 1 - ease_io((t - 6.0) / 0.5))
        layer.rise((W / 2, 745), '경로 위 맞춤 경유지 추천', 30, (205, 212, 222), 300, t, 1.9, 'mm', 1 - ease_io((t - 6.0) / 0.5))
        layer.rise((W / 2, 860), '현대자동차그룹 차량용 앱 개발 공모전  ·  일단 브랜딩', 19, MUTED, 400, t, 2.5, 'mm', 1 - ease_io((t - 6.0) / 0.5))
        return canvas
    return dict(card_alpha=0.0, draw=draw)


@scene(13)
def s_window(t):
    lbl = win(t, 4.0, 12.2)
    def draw(layer, card_layer, canvas):
        for rect, name, main in ((DRIVE, '주행 화면', False), (APP, '길목 · 화면의 1/3', True), (NAVI, '내장 내비', False)):
            r = to_card(rect, CAM_FULL)
            card_layer.chip((r[0] + 18, r[3] - 64), name, lbl * (1.0 if main else 0.7), GLOW if main else MUTED)
        feature_text(layer, 1, '내비 옆 1/3 화면', ['Pleos Connect의 3분할 창 정책에 맞춰', '내비 옆 한 칸만 씁니다.', '경로 안내를 가리지 않습니다.'],
                     ['세로 841dp 화면 기준 설계', 'Pleos Window Policy'], t, 13)
        progress(layer, 1)
        return canvas
    return dict(clip='A', src=0.5 + t * 0.25, cam=CAM_FULL, tilt=lerp(16, 7, ease_io(t / 4)), scale=1.0,
                spot=(APP, win(t, 4.0, 12.6, 0.7)), draw=draw)


@scene(14)
def s_voice(t):
    src = hold_then(t, 0.3, 1.0, 1.0, freeze_at=6.8)
    cam = lerp_t(CAM_FULL, CAM_APP, ease_io((t - 0.3) / 1.6))
    sp = win(t, 6.0, 13.6, 0.6)
    def draw(layer, card_layer, canvas):
        r = to_card(CAPTION, cam)
        card_chip(card_layer, r, '음성 인식 결과', sp)
        feature_text(layer, 2, '음성 입력과 안내', ['차량 마이크로 듣고 차 안에서', '바로 글자로 바꿉니다.', '결과는 음성으로도 알려 줍니다.'],
                     ['온디바이스 인식 · 앱 등록과 네트워크 불필요', 'SpeechToText 3.3.1 · TextToSpeech 3.3.1'], t, 14)
        layer.text((40, 1048), '질문 장면은 음성 대신 문장을 직접 넣어 재현했습니다.', 15, MUTED, 400, 0.7)
        progress(layer, 2)
        return canvas
    return dict(clip='A', src=src, cam=cam, tilt=lerp(7, 3, ease_io(t / 3)), scale=1.0, spot=(CAPTION, sp), draw=draw)


CAT = {'any': '휴식', 'cafe': '카페', 'restaurant': '식사', 'ev': '충전'}
TAGS = {'pet_ok': '반려견 동반', 'kids_chair': '유아 의자', 'vegan': '채식', 'drive_through': '드라이브스루'}


@scene(13)
def s_intent(t):
    def draw(layer, card_layer, canvas):
        a = win(t, 0.8, 12.6, 0.6)
        x0, y0 = 900, 250
        layer.glass((x0, y0, x0 + 440, y0 + 380), a)
        layer.text((x0 + 30, y0 + 28), '의도 파악 결과', 20, ACCENT, 600, a)
        req = ', '.join(TAGS.get(k, k) for k in IA['requiredTags']) or '없음'
        rows = [('종류', CAT.get(IA['category'], IA['category'])),
                ('시간 상한', f'{IA["maxDetourMin"]}분' if IA['maxDetourMin'] else '없음'),
                ('필수 조건', req), ('선호 조건', ', '.join(IA['preferredTags']) or '없음')]
        for i, (k, v) in enumerate(rows):
            ra = win(t, 1.4 + i * 0.35, 12.6, 0.5)
            dy = (1 - ease_out((t - 1.4 - i * 0.35) / 0.6)) * 14
            layer.text((x0 + 30, y0 + 90 + i * 66 + dy), k, 22, MUTED, 400, ra)
            layer.text((x0 + 170, y0 + 86 + i * 66 + dy), v, 28, TEXT, 600, ra)
        if 'pet_ok' in IA['requiredTags']:
            layer.text((x0 + 170, y0 + 86 + 2 * 66 + 40), '사용자 기록에서 가져옴', 16, MUTED, 400, win(t, 2.6, 12.6))
        feature_text(layer, 3, '의도 파악', ['평소 말투의 요청을 정해진 조건으로', '바꿉니다. 이 조건이 다음 단계의', '거르기 기준이 됩니다.'],
                     ['Gleo 연동 시 Gleo가 같은 값을 넘겨줌', 'LLM · 규칙 기반 대체'], t, 13)
        progress(layer, 3)
        return canvas
    return dict(clip='A', src=6.6 + t * 0.12, cam=CAM_APP, tilt=lerp(3, 9, ease_io(t / 4)), scale=0.98,
                spot=(CAPTION, 1 - ease_io(t / 0.8)), draw=draw)


RULES = ['이미 지나친 곳', '반대 차선 (U턴 필요)', '도착 시각에 영업 종료', '말한 시간 상한 초과', '필수 조건 불일치']
RULE_OF = {'이미 지나친 구간': 0, '반대 차선 · U턴 필요': 1, '도착 시각엔 영업 종료': 2}


def rule_index(reason):
    return RULE_OF.get(reason, 3 if '상한' in reason else 4)


@scene(17)
def s_filter(t):
    src = hold_then(t, 0.4, 6.6, 0.5, freeze_at=11.4)
    ex = IA['excluded']
    shown = int(len(ex) * clamp((t - 1.5) / 9))
    def draw(layer, card_layer, canvas):
        a = win(t, 0.8, 16.6, 0.6)
        x0, y0 = 880, 200
        grow = clamp((t - 1.0) / 9.5) * len(ex)
        layer.glass((x0, y0, x0 + 470, y0 + 112 + 44 * max(1.0, grow + 0.6)), a)
        cur = IA['reviewed'] - shown
        layer.text((x0 + 28, y0 + 26), '경로 위 후보', 20, ACCENT, 600, a)
        layer.text((x0 + 28, y0 + 60), f'{IA["reviewed"]}곳  →  제외 {shown}곳  →  남은 후보 {cur}곳', 24, TEXT, 600, a)
        for i, e in enumerate(ex[:shown]):
            ra = ease_out((t - 1.5 - 9 * i / len(ex)) / 0.5) * a
            yy = y0 + 112 + i * 44
            layer.text((x0 + 28, yy), e['name'], 21, (200, 206, 214), 400, ra)
            layer.text((x0 + 250, yy), e['reason'], 21, WARN, 500, ra)
        lit = {rule_index(e['reason']) for e in ex[:shown]}
        out = 1 - ease_io((t - 16.5) / 0.5)
        layer.rise((TEXT_X, 300), '04', 22, ACCENT, 600, t, 0.2, exit_alpha=out)
        layer.rise((TEXT_X, 340), '경로 위 후보 거르기', 50, TEXT, 600, t, 0.35, exit_alpha=out)
        for i, ln in enumerate(['경로와 영업시간처럼 규칙으로', '판정되는 조건은 코드가 처리합니다.']):
            layer.rise((TEXT_X, 430 + i * 44), ln, 26, (210, 216, 224), 300, t, 0.6 + 0.1 * i, exit_alpha=out)
        for i, rname in enumerate(RULES):
            on = i in lit
            ra = ease_out((t - 1.0 - 0.1 * i) / 0.8) * out * (1.0 if on else 0.4)
            yy = 548 + i * 40
            layer.d.ellipse((TEXT_X, yy + 11, TEXT_X + 9, yy + 20), fill=(*(ACCENT if on else MUTED), int(255 * ra)))
            layer.text((TEXT_X + 24, yy), rname, 23, TEXT if on else MUTED, 400 if not on else 500, ra)
        layer.text((TEXT_X, 770), 'NaviHelper · CandidateFilter (단위 테스트 7개)', 19, MUTED, 400, out * ease_out((t - 1.4) / 0.8))
        layer.text((40, 1048), '탐색 화면은 시각 효과이며 실제 도로가 아닙니다.', 15, MUTED, 400, 0.7)
        caption(layer, 4, t, 17)
        progress(layer, 4)
        return canvas
    return dict(clip='A', src=src, cam=CAM_APP, tilt=lerp(9, 5, ease_io(t / 5)), scale=0.98, spot=(APP, 0.0), draw=draw)


def first_pick(name):
    p = LOG[name]['decision']['picks'][0]
    return p['name'], p['why']


@scene(18)
def s_personal(t):
    seq = [('A', 14.0, '반려견 동승 기록'), ('B', 12.0, '뒷좌석 2명 탑승'), ('C', 12.5, '배터리 28%')]
    i = min(2, int(t / 3))
    name, src, tag = seq[i]
    compare = ease_io((t - 9) / 1.2)
    def draw(layer, card_layer, canvas):
        if t < 9.6:
            card_layer.chip((to_card(APP, CAM_APP)[0] + 20, 30), tag, win(t, i * 3 + 0.1, i * 3 + 3.0, 0.3))
        if compare > 0:
            layer.text((150, 200), f'같은 질문  “{UTTER}”', 26, MUTED, 400, compare)
            for k, (n, _, tg) in enumerate(seq):
                nm, why = first_pick(n)
                ca = ease_out((t - 9.4 - k * 0.4) / 0.8)
                x = 150 + k * 390
                dy = (1 - ca) * 30
                layer.glass((x, 270 + dy, x + 360, 760 + dy), ca)
                layer.text((x + 30, 300 + dy), '입력', 17, MUTED, 400, ca)
                layer.text((x + 30, 330 + dy), tg, 26, GLOW, 600, ca)
                layer.d.line((x + 30, 395 + dy, x + 330, 395 + dy), fill=(60, 70, 84, int(255 * ca)), width=1)
                layer.text((x + 30, 420 + dy), '1순위', 17, MUTED, 400, ca)
                words, line, lines = nm.split(' '), '', []
                for w_ in words:
                    if layer.d.textlength((line + ' ' + w_).strip(), font=font(32, 600)) > 300:
                        lines.append(line)
                        line = w_
                    else:
                        line = (line + ' ' + w_).strip()
                lines.append(line)
                for j, ln in enumerate(lines):
                    layer.text((x + 30, 452 + j * 44 + dy), ln, 32, TEXT, 600, ca)
                layer.text((x + 30, 600 + dy), '이유', 17, MUTED, 400, ca)
                layer.text((x + 30, 630 + dy), why, 22, (210, 216, 224), 400, ca)
        feature_text(layer, 5, '개인 맞춤 추천', ['걸러진 후보 중에서 이 사람에게', '맞는 순서로 최대 3곳을 고릅니다.'],
                     ['입력: 방문 기록, 선호, 뒷좌석 인원, 배터리', '후보에 없는 장소는 고를 수 없음', 'Vehicle 2.3.2 · Decision Agent'], t, 18)
        progress(layer, 5)
        return canvas
    return dict(clip=name, src=src + (t - i * 3) * 0.2, cam=CAM_APP, tilt=lerp(5, -6, compare), scale=lerp(0.98, 0.55, compare),
                center=lerp_t((700, 548), (520, 548), compare), card_alpha=1 - compare,
                spot=(ROW1, win(t, i * 3 + 0.8, i * 3 + 3.0, 0.4) * (1 - compare)), draw=draw)


@scene(13)
def s_card(t):
    target = around(ROW1, 40)
    cam = lerp_t(CAM_APP, target, ease_io((t - 0.4) / 1.8))
    k = int(clamp((t - 2.6) / 2.2, 0, 3.99))
    part_rect, part_name = CARD_PARTS[k]
    sp = win(t, 2.6, 11.4, 0.5)
    def draw(layer, card_layer, canvas):
        r = to_card(part_rect, cam)
        card_chip(card_layer, r, part_name, win(t, 2.6 + k * 2.2, 2.6 + (k + 1) * 2.2, 0.35), below=(part_name == '설명'))
        if t > 11.0:
            rr = to_card(CARD_PARTS[3][0], cam)
            card_layer.chip((rr[2] - 360, rr[3] + 18), '내장 내비에 넣어 측정한 값', ease_out((t - 11.0) / 0.5))
        feature_text(layer, 6, '추천 카드', ['고르는 데 필요한 정보만', '한 줄에 모았습니다.', '1순위는 음성으로도 안내합니다.'],
                     ['사진, 추천 이유, 설명, 추가 시간, 평점', '추가 시간은 내비에 넣어 측정한 실측값'], t, 13)
        layer.text((40, 1048), '장소 이름, 사진, 평점은 시연용 가상 데이터입니다.', 15, MUTED, 400, 0.7)
        progress(layer, 6)
        return canvas
    spot_rect = part_rect if t < 11.0 else CARD_PARTS[3][0]
    return dict(clip='A', src=15.0, cam=cam, tilt=lerp(-6, 4, ease_io(t / 2)), scale=1.0,
                spot=(spot_rect, max(sp, ease_out((t - 11.0) / 0.5) * (1 - ease_io((t - 12.5) / 0.5)))), draw=draw)


@scene(17)
def s_select(t):
    first = t < 11
    if first:
        src = hold_then(t, 0.6, 17.0, 1.6, freeze_at=27.0)
        cam = lerp_t(around(ROW1, 40), CAM_APP_NAVI, ease_io((t - 0.2) / 1.6))
        stage2 = ease_io((t - 5.6) / 0.6)
        rect = NAVI_PANEL if t > 5.6 else ROW1
        sp = win(t, 0.8, 10.6, 0.5)
    else:
        src = 12.6 + (t - 11) * 2.0
        cam = CAM_APP_NAVI
        rect, sp, stage2 = ROW2, win(t, 11.6, 16.6, 0.4), 0
    def draw(layer, card_layer, canvas):
        if first:
            card_layer.chip((to_card(APP, cam)[0] + 24, to_card(APP, cam)[3] - 80), '“첫 번째로 가자”', win(t, 0.6, 4.6, 0.4), GLOW, 24)
            r = to_card(NAVI_PANEL, cam)
            card_chip(card_layer, r, '내장 내비 · 경유지 1개 포함', win(t, 5.9, 10.6, 0.4), below=True)
        else:
            card_layer.chip((to_card(APP, cam)[0] + 24, 26), '터치로 2순위 선택', win(t, 11.2, 16.6, 0.4))
        feature_text(layer, 7, '고르면 바로 내비로', ['말이나 터치로 고르면 내장 내비에', '바로 경유지로 들어갑니다.', '다시 고르면 이전 경유지를 바꿉니다.'],
                     ['“첫 번째”, “두 번째” 음성 선택', 'NaviHelper addWaypoint()'], t, 17)
        progress(layer, 7)
        return canvas
    return dict(clip='A' if first else 'B', src=src, cam=cam, tilt=lerp(4, -4, ease_io(t / 6)), scale=1.0, spot=(rect, sp), draw=draw)


@scene(13)
def s_drive(t):
    src = 2.0 + t * 1.15
    stage = 0 if t < 6 else 1
    def draw(layer, card_layer, canvas):
        g = to_card(GEAR, CAM_FULL)
        card_layer.chip((g[0] - 60, g[3] + 18), '기어 P → D', win(t, 1.5, 6.0, 0.4))
        a = to_card(APP, CAM_FULL)
        card_layer.chip((a[0] + 20, a[1] + 20), '연출 정지 · 정보만 표시', win(t, 6.4, 12.6, 0.4))
        feature_text(layer, 8, '주행 중 화면', ['기어가 D에 있으면 움직이는 연출을', '멈추고 필요한 정보만 남깁니다.'],
                     ['Pleos 디자인 가이드의 주행 중 규칙 반영', '주행 중에도 앱이 차단되지 않도록 설정'], t, 13)
        progress(layer, 8)
        return canvas
    return dict(clip='D', src=src, cam=CAM_FULL, tilt=lerp(10, 6, ease_io(t / 4)), scale=1.0,
                spot=(GEAR if stage == 0 else APP, win(t, 1.4, 6.2, 0.4) if stage == 0 else win(t, 6.2, 12.6, 0.4)), draw=draw)


GLEO = [('Gleo → 길목', 'FIND_STOPS_ON_ROUTE', '{"userRequest": "강아지랑 커피 마실 데 있어?"}'),
        ('길목 → Gleo', 'success', 'Found 3 places along the route. The best match is 숲속정원 카페.'),
        ('Gleo → 길목', 'ADD_STOP_TO_ROUTE', '{"rank": 2}'),
        ('길목 → Gleo', 'success', 'Added 횡성 급속충전 라운지 to the route as a waypoint.')]


@scene(12)
def s_gleo(t):
    gone = ease_io(t / 1.0)
    def draw(layer, card_layer, canvas):
        layer.text((150, 190), 'Gleo 호출 시험 로그', 22, MUTED, 400, ease_out((t - 0.6) / 0.6))
        for i, (who, fn, body) in enumerate(GLEO):
            a = ease_out((t - 1.0 - i * 1.5) / 0.7) * (1 - ease_io((t - 11.5) / 0.5))
            y = 250 + i * 170 + (1 - a) * 24
            to_app = who.startswith('Gleo')
            x0 = 150 if to_app else 260
            layer.glass((x0, y, x0 + 980, y + 140), a, ACCENT if to_app else (90, 100, 116))
            layer.text((x0 + 32, y + 24), who, 19, ACCENT if to_app else GLOW, 600, a)
            layer.text((x0 + 220, y + 22), fn, 24, TEXT, 600, a)
            layer.text((x0 + 32, y + 80), body, 22, (200, 206, 214), 400, a)
        feature_text(layer, 9, 'Gleo 연동', ['Gleo가 앱의 함수를 직접 부를 수', '있게 스키마와 응답을 구현했습니다.'],
                     ['함수 2개: 장소 찾기, 경유지 추가', 'Gleo 7초 제한에 맞춰 즉시 응답', '실제 연동은 스키마 승인 후 가능'], t, 12)
        progress(layer, 9)
        return canvas
    return dict(clip='D', src=17.0, cam=CAM_FULL, tilt=lerp(6, -20, gone), scale=lerp(1.0, 0.7, gone),
                center=lerp_t((700, 548), (300, 560), gone), card_alpha=1 - gone, spot=(APP, 0), draw=draw)


FLOW = ['음성·Gleo', '의도 파악', '맥락 수집', '후보 거르기', '추천 결정', '내비 반영']


@scene(11)
def s_end(t):
    def draw(layer, card_layer, canvas):
        part1 = 1 - ease_io((t - 6.0) / 0.6)
        bw, gap = 240, 46
        x0 = (W - (6 * bw + 5 * gap)) / 2
        for i, s in enumerate(FLOW):
            a = ease_out((t - 0.3 - i * 0.25) / 0.6) * part1
            x = x0 + i * (bw + gap)
            layer.glass((x, 360, x + bw, 450), a)
            layer.text((x + bw / 2, 405), s, 26, TEXT, 500, a, 'mm')
            if i < 5:
                layer.text((x + bw + gap / 2, 405), '→', 26, ACCENT, 400, a, 'mm')
        layer.rise((W / 2, 540), 'AI는 걸러진 후보 안에서만 고르고, 응답이 없으면 규칙으로 대신 고릅니다.', 26, (215, 220, 228), 300, t, 2.0, 'mm', part1)
        layer.rise((W / 2, 590), '제출용 APK는 외부 AI 없이 동작합니다.', 26, (215, 220, 228), 300, t, 2.4, 'mm', part1)
        if t > 6.0:
            canvas = ribbon(canvas, W / 2, 400, 120, t, ease_out((t - 6.0) / 1.0))
            fin = 1 - ease_io((t - 10.3) / 0.7)
            layer.rise((W / 2, 610), '길목', 80, TEXT, 600, t, 6.5, 'mm', fin)
            layer.rise((W / 2, 685), '일단 브랜딩', 26, MUTED, 400, t, 7.0, 'mm', fin)
        notes = ['장소 이름, 사진, 평점은 시연용 가상 데이터입니다.',
                 '이 영상의 추천 AI는 외부 LLM으로 시연했으며, 이후 Pleos LLM SDK로 바꿀 계획입니다.',
                 '질문 장면은 음성 대신 문장을 직접 넣어 재현했습니다.']
        for i, s in enumerate(notes):
            layer.text((W / 2, 925 + i * 30), s, 17, MUTED, 400, ease_out((t - 1.0) / 0.8) * 0.85 * (1 - ease_io((t - 10.3) / 0.7)), 'mm')
        return canvas
    return dict(card_alpha=0.0, draw=draw)


# ---------- 렌더 ----------

DEFAULT = dict(clip='A', src=0.0, cam=CAM_FULL, tilt=10.0, scale=1.0, center=(700, 548), card_alpha=1.0, spot=(APP, 0.0))
TOTAL = sum(d for d, _ in SCENES)


def state_at(sec):
    start = 0.0
    for idx, (dur, fn) in enumerate(SCENES):
        if sec < start + dur or idx == len(SCENES) - 1:
            local = sec - start
            st = {**DEFAULT, **fn(local)}
            # 장면이 바뀔 때 카메라·기울기·크기를 앞 장면의 끝 상태에서 부드럽게 이어 준다.
            if idx > 0 and local < 1.2:
                prev = {**DEFAULT, **SCENES[idx - 1][1](SCENES[idx - 1][0] - 1e-3)}
                k = ease_io(local / 1.2)
                for key in ('cam', 'center'):
                    st[key] = lerp_t(prev[key], st[key], k)
                for key in ('tilt', 'scale', 'card_alpha'):
                    st[key] = lerp(prev[key], st[key], k)
                st['_prev'] = (prev, 1 - ease_io(local / 0.5))
            return st, local
        start += dur
    raise ValueError(sec)


def render_card(st):
    frame = clips[st['clip']].frame(st['src'])
    card = camera_crop(frame, st['cam']).astype(np.float32)
    if '_prev' in st:
        prev, mix = st['_prev']
        if mix > 0 and prev['card_alpha'] > 0 and (prev['clip'], round(prev['src'], 1)) != (st['clip'], round(st['src'], 1)):
            pc = camera_crop(clips[prev['clip']].frame(prev['src']), st['cam']).astype(np.float32)
            card = card * (1 - mix) + pc * mix
    rect, strength = st['spot']
    return spotlight(card, to_card(rect, st['cam']), strength)


def frame_at(sec):
    st, local = state_at(sec)
    canvas = BG.copy()
    layer = Layer()
    card_layer = Layer()
    card_layer.img = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
    card_layer.d = ImageDraw.Draw(card_layer.img)
    canvas = st['draw'](layer, card_layer, canvas)
    if st['card_alpha'] > 0.01:
        card = render_card(st)
        ca = np.asarray(card_layer.img, np.float32)
        card = card * (1 - ca[..., 3:4] / 255) + ca[..., :3] * (ca[..., 3:4] / 255)
        quad = card_quad(st['tilt'], st['scale'], st['center'])
        canvas = composite_card(canvas, card, quad, st['card_alpha'])
    canvas = layer.over(canvas)
    return np.clip(canvas, 0, 255).astype(np.uint8)


def preview(out_dir, secs):
    os.makedirs(out_dir, exist_ok=True)
    for s in secs:
        Image.fromarray(frame_at(float(s))).save(os.path.join(out_dir, f'f{float(s):06.1f}.png'))
    print('total', TOTAL)


def render(out_mp4):
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', BGM, '-map', '0:v', '-map', '1:a', '-shortest',
           '-c:v', 'libx264', '-preset', 'slow', '-b:v', '900k', '-maxrate', '1600k', '-bufsize', '3200k',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '112k',
           '-af', f'afade=t=in:st=0:d=1.5,afade=t=out:st={TOTAL - 4}:d=4,volume=0.85',
           '-map_metadata', '-1', '-metadata', 'title=길목 데모', '-movflags', '+faststart', out_mp4]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = int(TOTAL * FPS)
    for i in range(n):
        p.stdin.write(frame_at(i / FPS).tobytes())
        if i % 450 == 0:
            print(f'{i / FPS:.0f}s / {TOTAL}s', flush=True)
    p.stdin.close()
    p.wait()
    print('done', out_mp4, f'{os.path.getsize(out_mp4) / 1e6:.1f}MB')


if __name__ == '__main__':
    if sys.argv[1] == 'preview':
        preview(sys.argv[2], sys.argv[3:])
    else:
        render(sys.argv[2])
