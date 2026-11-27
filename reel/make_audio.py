#!/usr/bin/env python3
"""Procedural sound design for the reel: ambient drone + wind, countdown hits,
transition whooshes, clock ticks, and a warm closing swell. Output: 48k stereo WAV."""
import sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
DUR = 18.5
T_CH3, T_CH2, T_CH1, T_FIN = 2.2, 6.2, 10.2, 14.2
n = int(SR * DUR)
t = np.arange(n) / SR
rng = np.random.default_rng(3)
L = np.zeros(n); R = np.zeros(n)


def env_adsr(start, a, d, length=None):
    e = np.zeros(n)
    i0 = int(start * SR)
    m = n - i0 if length is None else min(n - i0, int(length * SR))
    tt = np.arange(m) / SR
    e[i0:i0 + m] = (1 - np.exp(-tt / max(a, 1e-4))) * np.exp(-tt / d)
    return e


def bandnoise(lo, hi, seed):
    x = np.random.default_rng(seed).standard_normal(n)
    sos = signal.butter(2, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


# --- ambient drone (A minor-ish, detuned, slow breathing) ----------------
drone = np.zeros(n)
for f, amp in ((55.0, 0.30), (55.4, 0.22), (82.4, 0.16), (110.0, 0.10), (164.8, 0.05), (220.3, 0.03)):
    drone += amp * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
drone *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.13 * t)
drone *= np.clip(t / 2.5, 0, 1)
L += drone * 0.32; R += drone * 0.32

# --- wind / water air bed ---------------------------------------------
for ch, seed in ((L, 10), (R, 11)):
    w = bandnoise(180, 1400, seed)
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * (0.07 + 0.02 * seed % 3) * t + seed)
    ch += w * lfo * 0.035 * np.clip(t / 1.5, 0, 1)

# --- countdown hits: sub boom + transient -------------------------------
for th in (T_CH3 + 0.1, T_CH2 + 0.1, T_CH1 + 0.1):
    i0 = int(th * SR); m = int(2.2 * SR); tt = np.arange(m) / SR
    f = 34 + 40 * np.exp(-tt * 9)
    ph = 2 * np.pi * np.cumsum(f) / SR
    boom = np.sin(ph) * np.exp(-tt * 2.2) * (1 - np.exp(-tt * 400))
    click = bandnoise(1500, 6000, int(th * 100))[i0:i0 + m] * np.exp(-tt * 60) * 0.35
    seg = (boom * 0.85 + click)
    L[i0:i0 + m] += seg[:n - i0]; R[i0:i0 + m] += seg[:n - i0]

# --- whooshes into each cut (rising band sweep) -------------------------
for tb in (T_CH3, T_CH2, T_CH1, T_FIN):
    d = 0.6; i0 = int((tb - d) * SR); m = int((d + 0.25) * SR)
    x = rng.standard_normal(m)
    out = np.zeros(m); blk = 1024
    zi = None
    for k in range(0, m, blk):
        p = min(1, k / (d * SR))
        fc = 300 + 4200 * p ** 2
        sos = signal.butter(2, [fc * 0.6, min(fc * 1.6, 20000)], btype="band", fs=SR, output="sos")
        if zi is None:
            zi = signal.sosfilt_zi(sos) * 0
        out[k:k + blk], zi = signal.sosfilt(sos, x[k:k + blk], zi=zi)
    tt = np.arange(m) / SR
    e = np.clip(tt / d, 0, 1) ** 2.5 * np.where(tt > d, np.exp(-(tt - d) * 18), 1)
    pan = np.linspace(-0.6, 0.6, m)
    L[i0:i0 + m] += out * e * 0.5 * (1 - pan) / 1.5
    R[i0:i0 + m] += out * e * 0.5 * (1 + pan) / 1.5

# --- clock ticks during the countdown chapters --------------------------
tick_m = int(0.03 * SR); tt = np.arange(tick_m) / SR
tick = np.sin(2 * np.pi * 2900 * tt) * np.exp(-tt * 260) + np.sin(2 * np.pi * 1700 * tt) * np.exp(-tt * 180) * 0.6
k = 0
for tk in np.arange(T_CH3 + 0.6, T_FIN - 0.4, 0.5):
    i0 = int(tk * SR); g = 0.06 if k % 2 == 0 else 0.035
    (L if k % 2 == 0 else R)[i0:i0 + tick_m] += tick * g
    (R if k % 2 == 0 else L)[i0:i0 + tick_m] += tick * g * 0.5
    k += 1

# --- finale: warm chord swell + reverse riser into it -------------------
sw = np.zeros(n)
for f, amp in ((220.0, 0.20), (261.6, 0.14), (329.6, 0.12), (440.0, 0.07), (110.0, 0.18), (523.3, 0.04)):
    for det in (-0.6, 0.6):
        sw += amp * np.sin(2 * np.pi * (f + det) * t)
e = np.clip((t - T_FIN) / 1.6, 0, 1) ** 1.5 * np.clip((DUR - 0.2 - t) / 2.2, 0, 1)
sw *= e
L += sw * 0.16; R += sw * 0.16
rise = bandnoise(800, 9000, 99) * np.clip((t - (T_FIN - 1.6)) / 1.6, 0, 1) ** 3 * (t < T_FIN)
L += rise * 0.05; R += rise * 0.05

# --- simple stereo reverb (feedback delays) -----------------------------
def verb(x, delays, fb):
    y = x.copy()
    for dly, g in zip(delays, fb):
        d = int(dly * SR); z = np.zeros_like(x); z[d:] = x[:-d] * g
        y += z
    return y
L = verb(L, (0.031, 0.067, 0.113, 0.197), (0.30, 0.22, 0.16, 0.10))
R = verb(R, (0.037, 0.071, 0.127, 0.211), (0.30, 0.22, 0.16, 0.10))

# master: global fade in/out, soft clip, normalize
master = np.clip(t / 0.4, 0, 1) * np.clip((DUR - t) / 0.9, 0, 1)
st = np.stack([L, R], 1) * master[:, None]
st = np.tanh(st * 1.4)
st /= np.max(np.abs(st)) / 0.89
wavfile.write(sys.argv[1] if len(sys.argv) > 1 else "reel_audio.wav", SR, (st * 32767).astype(np.int16))
print("audio ok")
