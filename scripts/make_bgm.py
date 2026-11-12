"""데모 영상용 잔잔한 배경음을 코드로 합성한다. 외부 음원을 쓰지 않으므로 저작권 문제가 없다.

사용법: python scripts/make_bgm.py <출력.wav> [길이(초)] [BPM]
"""
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
OUT = sys.argv[1] if len(sys.argv) > 1 else 'bgm.wav'
LENGTH = float(sys.argv[2]) if len(sys.argv) > 2 else 150.0
BPM = float(sys.argv[3]) if len(sys.argv) > 3 else 100
BEAT = 60 / BPM
CHORD_SEC = BEAT * 8  # 두 마디마다 화음이 바뀐다

rng = np.random.default_rng(11)


def midi(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


# Dmaj9 → Bm9 → Gmaj7 → Asus2. 밝지만 들뜨지 않는 진행
CHORDS = [
    [50, 54, 57, 61, 64],
    [47, 50, 54, 57, 61],
    [43, 47, 50, 54, 57],
    [45, 52, 59, 61, 64],
]

n = int(SR * LENGTH)
t = np.arange(n) / SR
left = np.zeros(n)
right = np.zeros(n)


def envelope(length: int, attack: float, release: float) -> np.ndarray:
    env = np.ones(length)
    a = min(int(attack * SR), length // 2)
    r = min(int(release * SR), length - a)
    env[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    env[length - r:] *= np.cos(np.linspace(0, np.pi / 2, r)) ** 2
    return env


def pad_note(freq: float, start: float, dur: float, gain: float) -> None:
    s = int(start * SR)
    e = min(n, int((start + dur) * SR))
    if e <= s:
        return
    tt = np.arange(e - s) / SR
    env = envelope(e - s, 1.4, 2.2)
    for ch, cents in ((left, -5), (right, 5)):
        f = freq * 2 ** (cents / 1200)
        wobble = 1 + 0.002 * np.sin(2 * np.pi * 0.11 * tt + rng.uniform(0, 6))
        phase = 2 * np.pi * f * np.cumsum(wobble) / SR
        tone = np.sin(phase) + 0.28 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
        ch[s:e] += gain * env * tone


def bell(freq: float, start: float, gain: float) -> None:
    s = int(start * SR)
    if s >= n:
        return
    length = min(n - s, int(3.5 * SR))
    tt = np.arange(length) / SR
    env = np.exp(-tt * 1.6) * np.minimum(1, tt / 0.008)
    tone = np.sin(2 * np.pi * freq * tt) + 0.18 * np.sin(2 * np.pi * freq * 2.01 * tt)
    pan = rng.uniform(0.3, 0.7)
    left[s:s + length] += gain * (1 - pan) * env * tone
    right[s:s + length] += gain * pan * env * tone


def pluck(freq: float, start: float, gain: float, decay: float = 4.0) -> None:
    s = int(start * SR)
    if s >= n:
        return
    length = min(n - s, int(1.6 * SR))
    tt = np.arange(length) / SR
    env = np.exp(-tt * decay) * np.minimum(1, tt / 0.004)
    tone = np.sin(2 * np.pi * freq * tt) + 0.35 * np.sin(4 * np.pi * freq * tt) * np.exp(-tt * 8)
    pan = 0.5 + 0.25 * np.sin(start * 1.3)
    left[s:s + length] += gain * (1 - pan) * env * tone
    right[s:s + length] += gain * pan * env * tone


def kick(start: float, gain: float) -> None:
    s = int(start * SR)
    if s >= n:
        return
    length = min(n - s, int(0.35 * SR))
    tt = np.arange(length) / SR
    freq = 42 + 48 * np.exp(-tt * 22)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-tt * 9)
    left[s:s + length] += gain * tone
    right[s:s + length] += gain * tone


# 화음 패드와 낮은 베이스. 화음끼리 1.5초 겹쳐 부드럽게 넘어간다.
k = 0
start = 0.0
while start < LENGTH:
    chord = CHORDS[k % len(CHORDS)]
    for m in chord:
        pad_note(midi(m), start, CHORD_SEC + 1.5, 0.05)
    pad_note(midi(chord[0] - 12), start, CHORD_SEC + 1.5, 0.07)
    # 8분음표로 흐르는 아르페지오가 앞으로 나아가는 느낌을 만든다. 처음 한 화음과 마지막 8초는 비운다.
    if k >= 1 and start < LENGTH - 8:
        order = [1, 2, 3, 4, 3, 2, 1, 2]
        for b in range(16):
            note = chord[order[b % len(order)] % len(chord)] + 12
            accent = 1.0 if b % 4 == 0 else 0.7
            pluck(midi(note), start + b * BEAT / 2, 0.034 * accent)
        # 가볍게 맑은 종소리를 얹는다.
        for b in range(8):
            if rng.random() < (0.3 if k < 4 else 0.5):
                note = chord[rng.integers(1, len(chord))] + 24
                bell(midi(note), start + b * BEAT + rng.uniform(0, 0.02), 0.03)
    # 부드러운 박동: 1, 3박의 낮은 킥과 8분음표 베이스
    if k >= 2 and start < LENGTH - 8:
        for b in range(8):
            if b % 2 == 0:
                kick(start + b * BEAT, 0.16)
            pluck(midi(chord[0] - 12), start + b * BEAT + BEAT / 2, 0.05, decay=6.0)
    start += CHORD_SEC
    k += 1

# 공기감을 주는 아주 작은 노이즈
air = sosfilt(butter(2, [300, 2500], 'bandpass', fs=SR, output='sos'), rng.normal(0, 1, n))
left += 0.004 * air
right += 0.004 * np.roll(air, 1200)

# 높은 대역을 걷어 부드럽게 만든다.
lp = butter(4, 5200, 'lowpass', fs=SR, output='sos')
left, right = sosfilt(lp, left), sosfilt(lp, right)

# 잔향: 감쇠하는 노이즈 임펄스와 컨볼루션
ir_len = int(3.2 * SR)
decay = np.exp(-np.linspace(0, 7, ir_len))
ir_l = rng.normal(0, 1, ir_len) * decay
ir_r = rng.normal(0, 1, ir_len) * decay
ir_l /= np.abs(ir_l).sum() / 6
ir_r /= np.abs(ir_r).sum() / 6
wet_l = fftconvolve(left, ir_l)[:n]
wet_r = fftconvolve(right, ir_r)[:n]
left = 0.72 * left + 0.28 * wet_l
right = 0.72 * right + 0.28 * wet_r

# 처음 3초 서서히 시작, 마지막 6초 서서히 끝
fade = envelope(n, 3.0, 6.0)
mix = np.stack([left * fade, right * fade], axis=1)
mix /= np.abs(mix).max() / 10 ** (-3 / 20)  # 최고 -3dBFS
wavfile.write(OUT, SR, (mix * 32767).astype(np.int16))
rms = 20 * np.log10(np.sqrt((mix ** 2).mean()))
print(f'saved {OUT} {LENGTH:.0f}s peak -3.0dBFS rms {rms:.1f}dBFS')
