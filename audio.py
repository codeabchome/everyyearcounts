#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EveryYearCounts - audio.py
Prosedurel ambient fon muzigi. Hicbir dis kaynak kullanmaz:
her nota sifirdan sentezlenir, dolayisiyla Content ID riski YOKTUR.

Tasarim: sakin, ilerleyis hissi veren yavas pad akorlari.
Grafigin onune gecmemesi icin seviye dusuk tutulur (-25 dBFS civari).
"""
import math
import wave

import numpy as np

SR = 44100
MASTER = 0.055           # cok dusuk: fon, on plan degil

# Am - F - C - G : sakin, notr, "ilerliyor" hissi
PROGRESSION = [
    (45, 48, 52),        # Am   A2  C3  E3
    (41, 45, 48),        # F    F2  A2  C3
    (48, 52, 55),        # C    C3  E3  G3
    (43, 47, 50),        # G    G2  B2  D3
]
CHORD_SEC = 8.0


def midi_hz(n):
    return 440.0 * (2 ** ((n - 69) / 12.0))


def _pad_voice(freq, n, t):
    """Tek bir pad sesi: temel + hafif detune + yumusak harmonikler."""
    v = np.zeros(n, dtype=np.float64)
    for det in (-0.12, 0.12):
        f = freq * (2 ** (det / 12.0))
        v += np.sin(2 * np.pi * f * t)
    v *= 0.5
    v += 0.22 * np.sin(2 * np.pi * freq * 2 * t)
    v += 0.09 * np.sin(2 * np.pi * freq * 3 * t)
    lfo = 1.0 + 0.06 * np.sin(2 * np.pi * 0.07 * t)
    return v * lfo


def _lowpass(x, cutoff=2000.0):
    """Basit tek kutuplu alcak geciren: tiz kenarlari yumusatir."""
    a = math.exp(-2.0 * math.pi * cutoff / SR)
    b = 1.0 - a
    y = np.empty_like(x)
    acc = 0.0
    for i in range(x.size):
        acc = b * x[i] + a * acc
        y[i] = acc
    return y


def _chord_block(notes, seconds):
    n = int(SR * seconds)
    t = np.arange(n) / SR
    block = np.zeros(n, dtype=np.float64)
    for i, m in enumerate(notes):
        gain = 1.0 if i == 0 else 0.72
        block += gain * _pad_voice(midi_hz(m), n, t)
    block /= max(len(notes), 1)

    fade = int(SR * 2.2)
    env = np.ones(n)
    env[:fade] = np.linspace(0, 1, fade) ** 1.5
    env[-fade:] = np.linspace(1, 0, fade) ** 1.5
    return block * env


def make_ambient(path, seconds, seed=0):
    """seconds uzunlugunda ambient WAV uretir."""
    rng = np.random.default_rng(seed)
    start = int(rng.integers(0, len(PROGRESSION)))

    need = int(SR * seconds)
    out = np.zeros(need + int(SR * CHORD_SEC), dtype=np.float64)

    pos, idx = 0, start
    overlap = int(SR * 2.0)
    while pos < need:
        notes = PROGRESSION[idx % len(PROGRESSION)]
        blk = _chord_block(notes, CHORD_SEC)
        out[pos:pos + blk.size] += blk
        pos += blk.size - overlap
        idx += 1

    out = out[:need]
    out = _lowpass(out, 2000.0)

    fi = int(SR * 3.0)
    fo = int(SR * 4.0)
    if out.size > fi + fo:
        out[:fi] *= np.linspace(0, 1, fi)
        out[-fo:] *= np.linspace(1, 0, fo)

    peak = np.max(np.abs(out)) or 1.0
    out = out / peak * MASTER

    pcm = (out * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1).ravel()

    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())
    return path


if __name__ == "__main__":
    make_ambient("out/ambient_demo.wav", 30, seed=3)
    print("yazildi: out/ambient_demo.wav")
