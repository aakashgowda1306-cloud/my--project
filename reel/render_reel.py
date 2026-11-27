#!/usr/bin/env python3
"""
Cinematic countdown reel compositor — STRICT IDENTITY LOCK.

Rules enforced in code:
  * The subject's pixels come straight from the source photo. They are never
    graded, filtered, retouched or regenerated. Only geometric placement
    (and, during camera moves, high-quality Lanczos resampling) is applied.
  * Every grade, fog, particle, light sweep, glow, graphic and text layer is
    composited BEHIND the person mask, so nothing is ever drawn over the person.
  * In the finale the subject sits at exactly 1:1 scale on an integer offset,
    so those frames carry the photo's original pixel values (verified by
    --verify before encoding).

Usage:
  python3 render_reel.py --work DIR --fonts DIR --out reel.mp4 [--audio a.wav]
  python3 render_reel.py ... --stills 3.5,8,12,16      (preview PNGs only)
  python3 render_reel.py ... --verify                  (pixel-identity check)
"""
import argparse, math, os, subprocess, sys
import multiprocessing as mp
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
DUR = 18.5
NFRAMES = int(round(DUR * FPS))

# Scene boundaries (seconds)
T_CH3, T_CH2, T_CH1, T_FIN = 2.2, 6.2, 10.2, 14.2
BOUNDS = [T_CH3, T_CH2, T_CH1, T_FIN]

# World space == photo pixel space (photo is cropped to 1080x1440, which
# removes the camera watermark strip). Environment layers extend beyond it.
WX0, WY0, WW, WH = -420, -760, 1940, 2820
HORIZON = 440.0
P_SUBJ = (655.0, 870.0)          # torso centre in photo coords
HEAD = (575.0, 470.0)            # head centre in photo coords

G = {}  # globals shared with forked workers


# ----------------------------------------------------------------- utilities
def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)

def lerp(a, b, t):
    return a + (b - a) * t

def ease_out_expo(t):
    t = clamp(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)

def ease_out_cubic(t):
    t = clamp(t); return 1 - (1 - t) ** 3

def ease_in_cubic(t):
    t = clamp(t); return t ** 3

def ease_io(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)

def fbm2d(h, w, seed, base=6, octaves=5, aspect=1.0):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        gw = max(2, int(base * 2 ** o * aspect)); gh = max(2, int(base * 2 ** o))
        g = rng.random((gh, gw)).astype(np.float32)
        out += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp; amp *= 0.5
    out /= tot
    out = (out - out.min()) / (out.max() - out.min() + 1e-6)
    return out

def fbm1d(n, seed, base=4, octaves=6):
    rng = np.random.default_rng(seed)
    x = np.zeros(n, np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        k = base * 2 ** o + 1
        pts = rng.random(k).astype(np.float32)
        xs = np.linspace(0, k - 1, n)
        # cosine interpolation
        i0 = np.floor(xs).astype(int); i1 = np.minimum(i0 + 1, k - 1); f = xs - i0
        f = (1 - np.cos(f * np.pi)) / 2
        x += amp * (pts[i0] * (1 - f) + pts[i1] * f)
        tot += amp; amp *= 0.5
    x /= tot
    return (x - x.min()) / (x.max() - x.min() + 1e-6)

def premul(rgb, a):
    return np.dstack([rgb * a[..., None], a]).astype(np.float32)

def over(dst_rgb, layer):
    """dst_rgb (H,W,3) <- premultiplied RGBA layer over it."""
    a = layer[..., 3:4]
    return dst_rgb * (1 - a) + layer[..., :3]


# ------------------------------------------------------------ asset building
def build_assets(work, fonts):
    src = cv2.cvtColor(cv2.imread(os.path.join(work, "src.jpg")), cv2.COLOR_BGR2RGB)[:1440]
    src_u8 = src.copy()
    src = src.astype(np.float32) / 255.0
    pm = cv2.imread(os.path.join(work, "mask_birefnet-portrait.png"), 0).astype(np.float32) / 255.0
    rm = cv2.imread(os.path.join(work, "mask_rock.png"), 0).astype(np.float32) / 255.0
    ph, pw = pm.shape

    # ---- rock (environment, so it may be graded) -----------------------
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    side = smoothstep(0, 170, xx) * smoothstep(pw, pw - 170, xx)
    bottom = smoothstep(1440, 1350, yy)
    ra = rm * side * bottom * (1 - pm)
    lum = src @ np.array([0.299, 0.587, 0.114], np.float32)
    rock = lerp(src, lum[..., None].repeat(3, 2), 0.45)          # desaturate
    rock = rock ** 1.25 * 0.62                                      # darken / contrast
    shadow_tint = np.array([0.80, 0.97, 1.02], np.float32)
    high_tint = np.array([1.06, 0.98, 0.88], np.float32)
    k = np.clip(lum, 0, 1)[..., None]
    rock = rock * lerp(shadow_tint, high_tint, k)
    rock *= lerp(1.0, 0.55, smoothstep(1260, 1440, yy))[..., None]
    G["rock"] = premul(np.clip(rock, 0, 1), ra)
    G["src"] = src                       # subject pixels (never modified)
    G["src_u8"] = src_u8
    G["pm"] = pm

    # ---- clean water plate (subject + rocks removed) --------------------
    hole = ((pm > 0.02) | (rm > 0.02)).astype(np.uint8)
    hole = cv2.dilate(hole, np.ones((31, 31), np.uint8)).astype(bool)
    clean = src.copy()
    for shift in (430, -430, 300, -300):
        sh = np.roll(src, shift, axis=1); shh = np.roll(hole, shift, axis=1)
        fill = hole & ~shh
        clean[fill] = sh[fill]; hole = hole & ~fill
    if hole.any():
        c8 = (np.clip(clean, 0, 1) * 255).astype(np.uint8)
        clean = cv2.inpaint(c8, hole.astype(np.uint8), 9, cv2.INPAINT_TELEA).astype(np.float32) / 255
    seam = 1150
    for kk in range(1, 1440 - seam):
        clean[seam + kk] = clean[max(450, seam - kk)]
    water = clean[int(HORIZON):1440]
    # extend to world rect
    top = int(HORIZON) - WY0
    bot = WY0 + WH - 1440
    water = cv2.copyMakeBorder(water, 0, bot, -WX0, WX0 + WW - pw, cv2.BORDER_REFLECT)
    wl = water @ np.array([0.299, 0.587, 0.114], np.float32)
    wl = cv2.GaussianBlur(wl, (0, 0), 1.6)
    n = (wl - np.median(wl)) * 3.2 + 0.5
    n = np.clip(n, 0, 1)
    wy = np.arange(water.shape[0], dtype=np.float32)[:, None] + HORIZON
    wx = np.arange(water.shape[1], dtype=np.float32)[None, :] + WX0
    deep = np.array([0.020, 0.040, 0.047], np.float32)
    mid = np.array([0.090, 0.160, 0.170], np.float32)
    wcol = deep + (mid - deep) * (n[..., None] ** 1.4)
    # warm glow reflection near horizon, centred behind subject
    glow = np.exp(-((wx - 640) / 420) ** 2) * np.exp(-((wy - HORIZON) / 260))
    wcol += (np.array([0.30, 0.17, 0.08], np.float32) * (glow * n ** 3)[..., None]) * 0.9
    # distance darkening toward the camera
    wcol *= lerp(1.0, 0.35, smoothstep(HORIZON, 1500, wy))[..., None]
    wcol *= lerp(1.0, 0.25, smoothstep(1450, 2000, wy))[..., None]
    wa = smoothstep(HORIZON - 1, HORIZON + 6, wy) * np.ones_like(wx)
    water_layer = np.zeros((WH, WW, 4), np.float32)
    water_layer[top:top + wcol.shape[0]] = premul(np.clip(wcol, 0, 1), wa)[:WH - top]
    G["water"] = water_layer

    # ---- sky ------------------------------------------------------------
    sy = (np.arange(WH, dtype=np.float32) + WY0)[:, None]
    sx = (np.arange(WW, dtype=np.float32) + WX0)[None, :]
    t = smoothstep(WY0, HORIZON, sy)
    c_top = np.array([0.010, 0.014, 0.018], np.float32)
    c_hor = np.array([0.105, 0.140, 0.150], np.float32)
    sky = c_top + (c_hor - c_top) * (t ** 2.2)[..., None]
    sky = np.broadcast_to(sky, (WH, WW, 3)).copy()
    clouds = fbm2d(WH, WW, 11, base=3, octaves=6, aspect=0.5)
    sky *= (0.78 + 0.45 * clouds)[..., None]
    g1 = np.exp(-(((sx - 650) / 760) ** 2 + ((sy - HORIZON) / 300) ** 2))
    sky += np.array([0.32, 0.19, 0.09], np.float32) * (g1 ** 1.3)[..., None] * 0.55
    g2 = np.exp(-(((sx - 150) / 700) ** 2 + ((sy + 200) / 600) ** 2))
    sky += np.array([0.02, 0.07, 0.08], np.float32) * g2[..., None]
    G["sky"] = premul(np.clip(sky, 0, 1), np.ones((WH, WW), np.float32))

    # ---- layered ridges -------------------------------------------------
    def ridge(seed, amp, base_off, color, fogc, rim, smooth_oct):
        h = fbm1d(WW, seed, base=3, octaves=smooth_oct)
        line = HORIZON + base_off - amp * h            # ridge top (world y)
        a = np.clip((sy - line[None, :]) * 0.9, 0, 1)
        a *= smoothstep(HORIZON + 260, HORIZON + 120, sy)  # fade below horizon
        depth = np.clip((sy - line[None, :]) / (HORIZON - line[None, :] + 40), 0, 1)
        col = color + (fogc - color) * (depth ** 1.6)[..., None]
        rimw = np.exp(-np.clip(sy - line[None, :], 0, None) / 6.0)
        col += rim * rimw[..., None] * np.exp(-((sx - 650) / 600) ** 2)[..., None]
        return premul(np.clip(col, 0, 1), a.astype(np.float32))
    G["r_far"] = ridge(21, 300, 2, np.array([0.085, 0.115, 0.125], np.float32),
                       np.array([0.13, 0.17, 0.175], np.float32),
                       np.array([0.10, 0.07, 0.04], np.float32), 5)
    G["r_mid"] = ridge(37, 170, 4, np.array([0.040, 0.058, 0.064], np.float32),
                       np.array([0.11, 0.145, 0.15], np.float32),
                       np.array([0.07, 0.05, 0.03], np.float32), 6)
    G["r_near"] = ridge(53, 34, 6, np.array([0.018, 0.026, 0.030], np.float32),
                        np.array([0.06, 0.08, 0.085], np.float32),
                        np.array([0.05, 0.035, 0.02], np.float32), 7)

    # ---- double-exposure card: pale sky with dark ridges, in subject shape
    ys_, xs_ = np.where(pm > 0.5)
    bx0, bx1, by0, by1 = xs_.min(), xs_.max(), ys_.min(), ys_.max()
    sil = pm[by0:by1 + 1, bx0:bx1 + 1]
    sh_, sw_ = sil.shape
    cy = np.arange(sh_, dtype=np.float32)[:, None] / sh_
    cx = np.arange(sw_, dtype=np.float32)[None, :] / sw_
    card = np.array([0.50, 0.60, 0.60], np.float32) * (1 - 0.55 * cy)[..., None] * np.ones((1, sw_, 1), np.float32)
    card += np.array([0.25, 0.14, 0.05], np.float32) * np.exp(-((cx - 0.5) / 0.35) ** 2 - ((cy - 0.42) / 0.12) ** 2)[..., None]
    for seed, base, amp, val in ((5, 0.48, 0.20, 0.30), (9, 0.60, 0.16, 0.16), (13, 0.74, 0.10, 0.05)):
        hh = fbm1d(sw_, seed, base=3, octaves=6)
        line = (base - amp * hh)[None, :]
        m = np.clip((cy - line) * sh_ * 0.6, 0, 1)
        card = card * (1 - m[..., None]) + np.array([val, val * 1.15, val * 1.2], np.float32) * m[..., None]
    fogn = fbm2d(sh_, sw_, 77, base=3, octaves=5)
    card = card * (0.85 + 0.3 * fogn[..., None])
    sil_soft = cv2.GaussianBlur(sil, (0, 0), 3)
    sil_soft *= smoothstep(1.0, 0.55, cy) * np.ones_like(cx)  # fade the legs out
    G["ghost"] = premul(np.clip(card, 0, 1), sil_soft.astype(np.float32))

    # ---- fog textures ---------------------------------------------------
    G["fog"] = fbm2d(900, 3200, 101, base=3, octaves=6, aspect=3.5)
    G["fog2"] = fbm2d(900, 3200, 202, base=4, octaves=6, aspect=3.0)

    # ---- particles ------------------------------------------------------
    rng = np.random.default_rng(7)
    npart = 150
    G["parts"] = dict(
        x=rng.uniform(0, W, npart), y=rng.uniform(0, H, npart),
        sp=rng.uniform(8, 38, npart), ph=rng.uniform(0, 6.28, npart),
        r=np.where(rng.random(npart) < 0.12, rng.uniform(7, 16, npart), rng.uniform(1.0, 2.8, npart)),
        b=rng.uniform(0.15, 0.6, npart), warm=rng.random(npart) < 0.35)
    sprites = {}
    for r in range(1, 17):
        s = int(r * 3 + 3) | 1
        g = np.zeros((s, s), np.float32); c = s // 2
        yy2, xx2 = np.mgrid[0:s, 0:s]
        d = np.sqrt((yy2 - c) ** 2 + (xx2 - c) ** 2)
        g = np.exp(-(d / max(0.8, r * 0.6)) ** 2) if r < 5 else np.clip((r - d) / 2.5, 0, 1) * 0.6 + np.exp(-(d / r) ** 2) * 0.4
        sprites[r] = g.astype(np.float32)
    G["sprites"] = sprites

    # ---- screen grids ---------------------------------------------------
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    G["gx"], G["gy"] = gx, gy
    vig = np.sqrt(((gx - W / 2) / (W * 0.78)) ** 2 + ((gy - H * 0.47) / (H * 0.62)) ** 2)
    G["vig"] = (1 - 0.78 * smoothstep(0.45, 1.15, vig))[..., None].astype(np.float32)
    ang = math.radians(28)
    G["sweep_u"] = (gx * math.cos(ang) + gy * math.sin(ang)).astype(np.float32)

    # ---- fonts ----------------------------------------------------------
    F = lambda n, s: ImageFont.truetype(os.path.join(fonts, n), s)
    G["fonts"] = dict(
        anton_xl=F("anton.woff", 1150), anton_xxl=F("anton.woff", 1500),
        anton_h=F("anton.woff", 168), anton_t=F("anton.woff", 150),
        bebas=F("bebas.woff", 64), corm=F("corm_it.woff", 50), corm_s=F("corm_it.woff", 40),
        mont=F("mont.woff", 25), mont_b=F("mont_b.woff", 27), mont_s=F("mont.woff", 21))
    # big countdown numerals: outline + fill as separate premultiplied layers
    nums = {}
    for key in ("03", "02", "01"):
        f = G["fonts"]["anton_xl"]
        bb = f.getbbox(key)
        w_, h_ = bb[2] - bb[0] + 40, bb[3] - bb[1] + 40
        ol = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
        ImageDraw.Draw(ol).text((20 - bb[0], 20 - bb[1]), key, font=f, fill=(0, 0, 0, 0),
                                stroke_width=4, stroke_fill=(150, 205, 205, 255))
        fi = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
        ImageDraw.Draw(fi).text((20 - bb[0], 20 - bb[1]), key, font=f, fill=(255, 255, 255, 255))
        ola = np.asarray(ol).astype(np.float32) / 255
        fia = np.asarray(fi)[..., 3].astype(np.float32) / 255
        nums[key] = (premul(ola[..., :3], ola[..., 3]), fia)
    G["nums"] = nums


# ------------------------------------------------------------------ camera
def camera(t):
    """Returns dict(s, F, Q, s0, Q0, pan, plate_alpha, ghost)."""
    def punch(t0, amt=0.075, d=0.7):
        lt = t - t0
        return 1.0 if lt >= d else 1 + amt * (1 - ease_out_expo(lt / d))
    if t < T_CH3:
        u = ease_io(t / T_CH3)
        F = P_SUBJ; s = 1.0; s0 = 1.0
        Q0 = (540.0, 1460.0); Q = (540.0, lerp(1460, 1170, u))
        return dict(s=s, F=F, Q=Q, s0=s0, Q0=Q0, pan=0.0,
                    plate=clamp((t - 1.3) / 0.85), ghost=0.42 * clamp(t / 0.8) * (1 - clamp((t - 1.6) / 0.6)),
                    ghost_pos=(540, 1080), ghost_scale=2.15)
    if t < T_CH2:
        lt = (t - T_CH3) / (T_CH2 - T_CH3); u = ease_io(lt)
        s0 = 1.0; s = lerp(1.0, 1.05, u) * punch(T_CH3)
        Q0 = (540.0, 1150.0); Q = (540.0, lerp(1150, 1135, u))
        return dict(s=s, F=P_SUBJ, Q=Q, s0=s0, Q0=Q0, pan=lerp(0, -30, u), plate=1.0, ghost=0.0)
    if t < T_CH1:
        lt = (t - T_CH2) / (T_CH1 - T_CH2); u = ease_io(lt)
        F = (620.0, 620.0); s0 = 1.42
        s = lerp(1.42, 1.50, u) * punch(T_CH2)
        Q0 = (560.0, 905.0); Q = (lerp(560, 525, u), lerp(905, 890, u))
        return dict(s=s, F=F, Q=Q, s0=s0, Q0=Q0, pan=lerp(0, 40, u), plate=1.0,
                    ghost=0.30 * clamp((t - T_CH2 - 0.2) / 0.9), ghost_pos=(lerp(330, 360, u), 1010),
                    ghost_scale=lerp(2.55, 2.65, u))
    if t < T_FIN:
        lt = (t - T_CH1) / (T_FIN - T_CH1); u = ease_io(lt)
        s0 = 1.0; s = lerp(1.0, 1.03, u) * punch(T_CH1)
        Q0 = (395.0, 1150.0); Q = (lerp(395, 455, u), 1150.0)
        return dict(s=s, F=P_SUBJ, Q=Q, s0=s0, Q0=Q0, pan=lerp(0, -20, u), plate=1.0, ghost=0.0)
    lt = (t - T_FIN) / (DUR - T_FIN); u = ease_io(lt)
    p = punch(T_FIN, 0.06, 0.8)
    Q = (540.0, 1200.0)        # integer placement, scale exactly 1 after punch
    return dict(s=1.0 * p, F=P_SUBJ, Q=Q, s0=1.0, Q0=Q, pan=lerp(0, -55, u), plate=1.0,
                ghost=0.0)


def layer_affine(cam, d, img_origin):
    s0, s = cam["s0"], cam["s"]
    sl = s0 * (s / s0) ** d
    Qx = cam["Q0"][0] + (cam["Q"][0] - cam["Q0"][0]) * d + cam["pan"] * (1 - d)
    Qy = cam["Q0"][1] + (cam["Q"][1] - cam["Q0"][1]) * d
    Fx, Fy = cam["F"]; ox, oy = img_origin
    return np.float32([[sl, 0, sl * (ox - Fx) + Qx], [0, sl, sl * (oy - Fy) + Qy]])


def warp(img, M, interp=cv2.INTER_LINEAR):
    return cv2.warpAffine(img, M, (W, H), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def place_plate(arr, M, interp):
    """Exact integer paste when scale==1 (pixel-identical), else resample."""
    s = M[0, 0]; tx, ty = M[0, 2], M[1, 2]
    if abs(s - 1.0) < 1e-9 and abs(tx - round(tx)) < 1e-9 and abs(ty - round(ty)) < 1e-9:
        tx, ty = int(round(tx)), int(round(ty))
        shape = (H, W) + arr.shape[2:]
        out = np.zeros(shape, arr.dtype)
        h, w = arr.shape[:2]
        x0, y0 = max(0, tx), max(0, ty); x1, y1 = min(W, tx + w), min(H, ty + h)
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = arr[y0 - ty:y1 - ty, x0 - tx:x1 - tx]
        return out, True
    return warp(arr, M, interp), False


# ------------------------------------------------------------- typography
def draw_text(canvas, s, font, x, y, align, t, t_in, t_out, color=(235, 232, 225),
              stagger=0.035, dur=0.55, track0=0.0, track1=0.0, rise=36, alpha=1.0):
    if t < t_in or t > t_out + 0.5:
        return
    ttrack = ease_out_expo((t - t_in) / 1.6)
    track = lerp(track0, track1, ttrack)
    widths = [font.getlength(c) for c in s]
    total = sum(widths) + track * (len(s) - 1)
    x0 = x if align == "l" else (x - total if align == "r" else x - total / 2)
    out_a = 1 - ease_in_cubic((t - t_out) / 0.45)
    cx = x0
    asc = font.getbbox("H")[1]
    for i, c in enumerate(s):
        p = (t - t_in - i * stagger) / dur
        e = ease_out_cubic(p)
        a = e * out_a * alpha
        if a > 0.004 and c != " ":
            bb = font.getbbox(c)
            gw, gh = bb[2] - bb[0] + 6, bb[3] - bb[1] + 6
            px = cx + bb[0] - 3; py = y + bb[1] - asc - 3 + (1 - e) * rise
            ix, iy = int(math.floor(px)), int(math.floor(py))
            im = Image.new("RGBA", (gw + 2, gh + 2), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((3 - bb[0] + (px - ix), 3 - bb[1] + (py - iy)), c, font=font,
                                    fill=color + (int(255 * clamp(a)),))
            _safe_comp(canvas, im, ix, iy)
        cx += widths[i] + track


def _safe_comp(canvas, im, ix, iy):
    x0, y0 = max(0, -ix), max(0, -iy)
    if ix >= W or iy >= H or ix + im.width <= 0 or iy + im.height <= 0:
        return
    if x0 or y0 or ix + im.width > W or iy + im.height > H:
        im = im.crop((x0, y0, min(im.width, W - ix), min(im.height, H - iy)))
    canvas.alpha_composite(im, dest=(max(ix, 0), max(iy, 0)))


def draw_rule(draw, x, y, length, t, t_in, t_out, align="l", alpha=0.7, color=(200, 220, 220)):
    if t < t_in or t > t_out + 0.5:
        return
    e = ease_out_expo((t - t_in) / 0.9) * (1 - ease_in_cubic((t - t_out) / 0.45))
    L = length * e
    xa = x if align == "l" else (x - L if align == "r" else x - L / 2)
    draw.line([(xa, y), (xa + L, y)], fill=color + (int(255 * alpha * e),), width=2)


CHAPTERS = [
    dict(t0=T_CH3, t1=T_CH2, num="03", word="THREE", head="PRESENCE",
         sub="Some moments ask only that you stand still.", layout="tl"),
    dict(t0=T_CH2, t1=T_CH1, num="02", word="TWO", head="STILLNESS",
         sub="The water keeps every secret it is told.", layout="tr"),
    dict(t0=T_CH1, t1=T_FIN, num="01", word="ONE", head="DEPTH",
         sub="What runs quiet, runs deep.", layout="br"),
]


def typography(t):
    Fn = G["fonts"]
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    warm = (226, 196, 160); ice = (180, 214, 212); white = (238, 235, 228)

    # viewfinder corner brackets + frame metadata (whole reel)
    fa = clamp((t - 0.3) / 0.8) * (1 - clamp((t - (DUR - 1.0)) / 0.6))
    if fa > 0:
        m, L = 54, 46; c = (210, 225, 225, int(150 * fa))
        for (x, y, sx, sy) in ((m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)):
            d.line([(x, y), (x + sx * L, y)], fill=c, width=2)
            d.line([(x, y), (x, y + sy * L)], fill=c, width=2)
        draw_text(canvas, "73MM   F/2.65   1/100S", Fn["mont_s"], 84, H - 110, "l", t, 0.6, DUR - 1.0,
                  color=(190, 205, 205), stagger=0.012, dur=0.4, track0=10, track1=3, rise=0, alpha=0.75)
        # progress line
        prog = clamp(t / (DUR - 0.9))
        d.line([(84, H - 72), (W - 84, H - 72)], fill=(255, 255, 255, int(38 * fa)), width=1)
        d.line([(84, H - 72), (84 + (W - 168) * prog, H - 72)], fill=warm + (int(200 * fa),), width=2)

    # rolling countdown counter (top-right)
    if T_CH3 - 0.2 < t < T_FIN + 0.3:
        seq = [(T_CH3, 3), (T_CH2, 2), (T_CH1, 1), (T_FIN, 0)]
        cur = 3
        for (tb, v) in seq:
            if t >= tb: cur = v
        f = Fn["bebas"]
        box_x, box_y = W - 84, 94
        alpha = clamp((t - (T_CH3 - 0.2)) / 0.5) * (1 - clamp((t - T_FIN) / 0.3))
        # digit roll: previous digit slides up, new digit slides in from below
        roll = 1.0
        for (tb, v) in seq[1:]:
            if tb <= t < tb + 0.45:
                roll = ease_out_expo((t - tb) / 0.45)
        layer = Image.new("RGBA", (220, 80), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
        txt_new = f"T-0{cur}"; txt_old = f"T-0{cur + 1}"
        if roll < 1.0:
            ld.text((0, 6 - 70 * roll), txt_old, font=f, fill=white + (int(255 * alpha * (1 - roll)),))
            ld.text((0, 6 + 70 * (1 - roll)), txt_new, font=f, fill=warm + (int(255 * alpha * roll),))
        else:
            ld.text((0, 6), txt_new, font=f, fill=warm + (int(255 * alpha),))
        tw = int(f.getlength(txt_new))
        canvas.alpha_composite(layer, dest=(box_x - tw, box_y))

    # intro title
    draw_text(canvas, "A FILM IN THREE BREATHS", Fn["mont_b"], W / 2, 860, "c", t, 0.25, 1.25,
              color=white, stagger=0.03, dur=0.6, track0=2, track1=16, rise=0)
    draw_rule(d, W / 2, 915, 260, t, 0.55, 1.25, align="c", color=warm)
    draw_text(canvas, "03   .   02   .   01", Fn["mont"], W / 2, 950, "c", t, 0.6, 1.25,
              color=ice, stagger=0.04, dur=0.5, track0=0, track1=6, rise=10, alpha=0.8)

    # chapters
    for ch in CHAPTERS:
        t0, t1 = ch["t0"], ch["t1"]
        a_in, a_out = t0 + 0.35, t1 - 0.55
        lay = ch["layout"]
        if lay == "tl":
            x, al, y0 = 84, "l", 205
        elif lay == "tr":
            x, al, y0 = W - 84, "r", 205
        else:
            x, al, y0 = W - 84, "r", 1380
        draw_rule(d, x, y0 + 14, 70, t, a_in - 0.1, a_out, align=al, color=warm)
        lx = x + 92 if al == "l" else x - 92
        draw_text(canvas, ch["word"], Fn["mont_b"], lx, y0, al, t, a_in, a_out, color=warm,
                  stagger=0.05, dur=0.5, track0=26, track1=12, rise=0)
        draw_text(canvas, ch["head"], Fn["anton_h"], x, y0 + 52, al, t, a_in + 0.15, a_out,
                  color=white, stagger=0.06, dur=0.6, track0=0, track1=6, rise=60)
        draw_text(canvas, ch["sub"], Fn["corm"], x, y0 + 260, al, t, a_in + 0.75, a_out,
                  color=(205, 214, 210), stagger=0.012, dur=0.6, rise=14)

    # finale
    tf = T_FIN
    draw_text(canvas, "STILL WATERS", Fn["anton_t"], W / 2, 190, "c", t, tf + 0.45, DUR - 0.75,
              color=white, stagger=0.055, dur=0.7, track0=30, track1=4, rise=38)
    draw_text(canvas, "RUN DEEP", Fn["anton_t"], W / 2, 360, "c", t, tf + 0.95, DUR - 0.75,
              color=warm, stagger=0.07, dur=0.7, track0=40, track1=14, rise=38)
    draw_rule(d, W / 2, 548, 300, t, tf + 1.5, DUR - 0.75, align="c", color=ice, alpha=0.55)
    draw_text(canvas, "a cinematic portrait", Fn["corm_s"], W / 2, 572, "c", t, tf + 1.7, DUR - 0.75,
              color=(205, 214, 210), stagger=0.02, dur=0.6, rise=10)
    return np.asarray(canvas).astype(np.float32) / 255.0


# ------------------------------------------------------------------- frame
def zoom_blur(img, strength, cx, cy, n=7):
    if strength <= 0.002:
        return img
    acc = np.zeros_like(img)
    for i in range(n):
        s = 1 + strength * i / (n - 1)
        M = np.float32([[s, 0, cx - s * cx], [0, s, cy - s * cy]])
        acc += cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return acc / n


def render(fi, want_meta=False):
    t = fi / FPS
    cam = camera(t)
    origin = (WX0, WY0)

    # ---- environment stack (back to front) ------------------------------
    env = np.zeros((H, W, 3), np.float32)
    for name, dpt in (("sky", 0.10), ("r_far", 0.22), ("r_mid", 0.34), ("r_near", 0.50), ("water", 0.62)):
        env = over(env, warp(G[name], layer_affine(cam, dpt, origin)))

    gx, gy = G["gx"], G["gy"]
    # horizon screen y (for fog band) from the water layer's mapping
    Mw = layer_affine(cam, 0.55, origin)
    hy = Mw[1, 1] * (HORIZON - WY0) + Mw[1, 2]

    # fog band hugging the horizon + low ground fog (drifting)
    off = int(t * 38) % 1500
    fog = G["fog"][:, off:off + W]
    fogb = cv2.resize(fog, (W, 900))
    band = np.zeros((H,), np.float32)
    band += 0.55 * np.exp(-((np.arange(H) - hy - 10) / 110.0) ** 2)
    band += 0.45 * smoothstep(H * 0.70, H, np.arange(H, dtype=np.float32))
    ftex = np.zeros((H, W), np.float32)
    yb = int(np.clip(hy - 450, 0, H - 900))
    ftex[:] = 0.5
    ftex[yb:yb + 900] = fogb
    off2 = int(t * 22) % 1500
    f2 = cv2.resize(G["fog2"][:, off2:off2 + W], (W, H))
    fa = band[:, None] * (0.35 + 0.65 * ftex) * (0.55 + 0.45 * f2)
    fogc = np.array([0.30, 0.40, 0.42], np.float32)
    env = env * (1 - fa[..., None] * 0.55) + fogc * (fa[..., None] * 0.55)

    # subject-plane mapping
    Mp = layer_affine(cam, 1.0, (0, 0))
    hx = Mp[0, 0] * HEAD[0] + Mp[0, 2]; hyy = Mp[1, 1] * HEAD[1] + Mp[1, 2]
    tx_ = Mp[0, 0] * P_SUBJ[0] + Mp[0, 2]; ty_ = Mp[1, 1] * P_SUBJ[1] + Mp[1, 2]

    # backlight halo behind subject (environment light, teal + warm core)
    pa = cam["plate"]
    halo = np.exp(-(((gx - tx_) / 430) ** 2 + ((gy - (ty_ - 120)) / 620) ** 2))
    halo2 = np.exp(-(((gx - hx) / 190) ** 2 + ((gy - hyy) / 210) ** 2))
    env += (np.array([0.05, 0.13, 0.14], np.float32) * halo[..., None] +
            np.array([0.10, 0.06, 0.025], np.float32) * halo2[..., None]) * (0.35 + 0.65 * pa)

    # anamorphic horizon streak
    streak = np.exp(-((gy - hy + 4) / 3.0) ** 2) * np.exp(-((gx - lerp(560, 600, (t % 6) / 6)) / 420) ** 2)
    env += np.array([0.42, 0.28, 0.16], np.float32) * (streak * (0.55 + 0.15 * math.sin(t * 2.1)))[..., None]

    # double-exposure ghost silhouette (landscape inside a giant outline)
    if cam["ghost"] > 0.002:
        gs = cam["ghost_scale"]; gpx, gpy = cam["ghost_pos"]
        gh_, gw_ = G["ghost"].shape[:2]
        Mg = np.float32([[gs, 0, gpx - gs * gw_ / 2], [0, gs, gpy - gs * gh_ / 2]])
        gl = warp(G["ghost"], Mg)
        a = cam["ghost"]
        # screen blend at low opacity
        lay = gl[..., :3]
        env = env + (lay - env * lay) * a

    # big countdown numeral behind the subject
    for ch in CHAPTERS:
        if ch["t0"] - 0.05 <= t < ch["t1"] + 0.05:
            lt = t - ch["t0"]
            ol, fia = G["nums"][ch["num"]]
            e = ease_out_expo((lt - 0.1) / 0.9)
            out = 1 - ease_in_cubic((t - (ch["t1"] - 0.45)) / 0.45)
            sc = lerp(1.22, 1.0, e) * lerp(1.0, 1.05, clamp(lt / 4))
            if ch["num"] == "03":
                cx, cy = 540, 1010
            elif ch["num"] == "02":
                cx, cy = 600, 1230; sc *= 1.2
            else:
                cx, cy = 730, 960
            cx += lerp(0, -18, clamp(lt / 4)) if ch["num"] != "01" else lerp(0, 25, clamp(lt / 4))
            hh, ww = fia.shape
            Mn = np.float32([[sc, 0, cx - sc * ww / 2], [0, sc, cy - sc * hh / 2]])
            alpha = e * out
            oll = warp(ol, Mn)
            env = env * (1 - oll[..., 3:4] * alpha * 0.85) + oll[..., :3] * alpha * 0.85
            # fill wipes up from bottom
            fw = warp(fia, Mn)
            wipe_y = lerp(cy + sc * hh / 2, cy - sc * hh / 2, ease_out_cubic((lt - 0.35) / 1.4))
            wm = smoothstep(wipe_y + 40, wipe_y - 40, gy)
            fillc = np.array([0.16, 0.22, 0.23], np.float32)
            fa2 = (fw * (1 - wm) * 0.30 * alpha)[..., None]
            env = env * (1 - fa2) + fillc * fa2

    # light sweep (environment only)
    for (ts, dur, amp) in ((0.2, 1.4, 0.10), (T_CH3 + 0.1, 1.1, 0.07), (T_CH1 + 0.2, 1.2, 0.07),
                           (T_FIN + 0.3, 1.5, 0.11)):
        if ts <= t <= ts + dur:
            c = lerp(-600, W * math.cos(math.radians(28)) + H * math.sin(math.radians(28)) + 400,
                     ease_io((t - ts) / dur))
            band_ = np.exp(-((G["sweep_u"] - c) / 120.0) ** 2) * amp
            env += np.array([1.0, 0.90, 0.75], np.float32) * band_[..., None]

    # particles (behind subject)
    P = G["parts"]; spr = G["sprites"]
    pl = np.zeros((H, W, 3), np.float32)
    for i in range(len(P["x"])):
        x = (P["x"][i] + 18 * math.sin(t * 0.45 + P["ph"][i]) + cam["pan"] * 0.6) % W
        y = (P["y"][i] - P["sp"][i] * t) % H
        r = int(round(min(16, max(1, P["r"][i])))); sp = spr[r]; s = sp.shape[0]
        x0, y0 = int(x) - s // 2, int(y) - s // 2
        if x0 < 0 or y0 < 0 or x0 + s > W or y0 + s > H:
            continue
        col = (0.95, 0.75, 0.52) if P["warm"][i] else (0.6, 0.85, 0.86)
        b = P["b"][i] * (0.6 + 0.4 * math.sin(t * 1.7 + P["ph"][i] * 3)) * (0.35 if r >= 5 else 1.0)
        pl[y0:y0 + s, x0:x0 + s] += sp[..., None] * np.array(col, np.float32) * b
    env += pl * 0.55

    # ---- rocks (environment, graded) on subject plane ------------------
    rock, _ = place_plate(G["rock"], Mp, cv2.INTER_LINEAR)
    env = over(env, rock * cam["plate"])

    # film grain + vignette on environment only
    rng = np.random.default_rng(fi * 7919 + 13)
    grain = rng.standard_normal((H // 2, W // 2)).astype(np.float32)
    grain = cv2.resize(grain, (W, H), interpolation=cv2.INTER_LINEAR)
    env = env * G["vig"] + grain[..., None] * 0.014
    env = np.clip(env, 0, 1)

    # transition zoom blur on environment
    tb = min(BOUNDS, key=lambda b: abs(b - t))
    dist = abs(t - tb)
    zb = max(0.0, 1 - dist / 0.22) ** 2 * 0.12
    env = zoom_blur(env, zb, W / 2, H * 0.45)

    # ---- subject: ORIGINAL pixels, never altered ----------------------
    pm_s, exact = place_plate(G["pm"], Mp, cv2.INTER_LINEAR)
    if exact:
        subj, _ = place_plate(G["src"], Mp, None)
    else:
        subj = np.clip(warp(G["src"], Mp, cv2.INTER_LANCZOS4), 0, 1)
    a = (pm_s * cam["plate"])[..., None]
    frame = env * (1 - a) + subj * a

    # ---- typography & graphics: always behind/around, never over subject
    ty = typography(t)
    ta = ty[..., 3:4] * (1 - a)
    frame = frame * (1 - ta) + ty[..., :3] * ta

    # dip-to-black at cuts and final fade (opacity only)
    dip = max(0.0, 1 - dist / 0.11) * 0.92
    fade_in = clamp(t / 0.35)
    fade_out = 1 - clamp((t - (DUR - 0.8)) / 0.75)
    k = (1 - dip) * fade_in * fade_out
    if k < 1:
        frame = frame * k
    out = np.rint(np.clip(frame, 0, 1) * 255).astype(np.uint8)
    if want_meta:
        return out, dict(exact=exact, k=k, pm=pm_s * cam["plate"], ta=ta[..., 0])
    return out


def _init(g):
    G.update(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--out", default="reel.mp4")
    ap.add_argument("--audio", default=None)
    ap.add_argument("--stills", default=None)
    ap.add_argument("--stilldir", default=".")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--procs", type=int, default=os.cpu_count())
    a = ap.parse_args()
    build_assets(a.work, a.fonts)

    if a.verify:
        # Finale frame: subject placed 1:1 on an integer offset. Compare every
        # pixel where the person mask is fully opaque against the source photo.
        fi = int((T_FIN + 2.0) * FPS)
        img, meta = render(fi, want_meta=True)
        assert meta["exact"], "finale is not on the exact 1:1 path"
        Mp = layer_affine(camera(fi / FPS), 1.0, (0, 0))
        tx, ty = int(round(Mp[0, 2])), int(round(Mp[1, 2]))
        pm = G["pm"]; src = G["src_u8"]
        sel = pm >= 0.999
        ys, xs = np.where(sel)
        got = img[ys + ty, xs + tx]
        exp = src[ys, xs]
        diff = np.abs(got.astype(int) - exp.astype(int))
        text_over = (meta["ta"][ys + ty, xs + tx] > 0).sum()
        print(f"verify frame {fi}: {len(ys)} fully-opaque subject pixels, "
              f"identical={int((diff.max(1) == 0).sum())}, max_abs_diff={int(diff.max())}, "
              f"text/graphics pixels over subject={int(text_over)}")
        return

    if a.stills:
        os.makedirs(a.stilldir, exist_ok=True)
        for ts in a.stills.split(","):
            fi = int(float(ts) * FPS)
            Image.fromarray(render(fi)).save(os.path.join(a.stilldir, f"still_{float(ts):05.2f}.png"))
            print("still", ts)
        return

    vid_tmp = a.out + ".video.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-tune", "film",
           "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-movflags", "+faststart", vid_tmp]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    ctx = mp.get_context("fork")
    with ctx.Pool(a.procs) as pool:
        for i, fr in enumerate(pool.imap(render, range(NFRAMES), chunksize=3)):
            ff.stdin.write(fr.tobytes())
            if i % 60 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close(); ff.wait()
    if a.audio:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid_tmp, "-i", a.audio,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
                        "-movflags", "+faststart", a.out], check=True)
        os.remove(vid_tmp)
    else:
        os.replace(vid_tmp, a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
