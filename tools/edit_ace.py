"""Ace's VSL (another creator): his best takes assembled by tools/ace_assemble.py, edited in the same style as Jan's
videos (AB Nasdaq structure, Ricky's design, light leaks, staircase zooms). RAW is the assembled clean cut (base.mov).

    python tools/edit_ace.py base.mov WORK video T0 T1 OUT.mp4 / audio SONG.mp3 OUT.wav / frames DIR t ...

FAQ notes: Same engine as the thank-you video; one cue sheet per FAQ, chosen by the raw
file's name (FAQ-HOWMUCHTIME, FAQ-ISTHISLEGIT, FAQ-WHAT.IS.INSIDE, FAQ-WHOISTHISFOR).

Thank-you notes: AB Nasdaq's thank-you structure (light leaks, staircase zooms, word cards),
Ricky's (rickyvideoediting) design system. Engine copied from tools/edit_vsl.py.

Original VSL notes:

Structure (from the AB Nasdaq reference VSL): a framing change every 3-5 s (wide / close, slow push-ins,
punch-ins on the hard lines), 2-3 word captions at the bottom, key lines beside his head, full-screen text pages,
cards for numbers and ideas, a proof montage, a split screen for the offer and a CTA on the application.

Look (from Ricky's STYLE.md): near-black + white + gold (60/30/10), Inter Display SemiBold + EB Garamond Bold Italic
(gold, deep glow), per-letter write-on (rise + blur->sharp + yellow->colour, posterised to 15 fps), orange->black
cards with a glowing rim, grid pages with an orange glow from the bottom, trim-path underlines, zoom-blur
transitions, background darkened/blurred only while graphics are up.

usage:
  python tools/edit_vsl.py RAW WORK frames OUTDIR t1 t2 ...      (stills at OUTPUT times)
  python tools/edit_vsl.py RAW WORK video T0 T1 OUT.mp4          (render an OUTPUT-time range)
  python tools/edit_vsl.py RAW WORK audio MUSIC.mp3 OUT.wav
  python tools/edit_vsl.py RAW WORK info
WORK holds words.json (word timestamps of the raw), optionally words_aligned.json (tools/snap_words.py), fonts/ and imgjpg/ (the results-and-images release as JPG).
All cue times below are in RAW-video seconds.
"""
import functools
import json
import os
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

cv2.setNumThreads(1)
RAW, WORK, MODE = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
SW, SH = 1920, 1080
VERT = os.environ.get("VSL_FORMAT") == "9x16"      # 9:16 version: same edit, portrait layout
OW, OH = (1080, 1920) if VERT else (1920, 1080)
K = 1.0
FPS = 30
SR = 48000
RAW_END = 1000.0   # set per FAQ below

# ------------------------------------------------------------------ palette (BGR)
SECOND = (168, 156, 150)
ACCENT = (48, 172, 250)        # gold #FAAC30
WHITE = (242, 242, 242)
INTRO = (110, 220, 255)
RED = (70, 70, 235)

F_SANS = str(WORK / "fonts/InterDisplay-SemiBold.otf")
F_SANS_M = str(WORK / "fonts/InterDisplay-Medium.otf")
F_SERIF = str(WORK / "fonts/EBGaramond-BoldItalic.ttf")
IMG = WORK / "imgjpg"


@functools.lru_cache(None)
def font(path, px):
    return ImageFont.truetype(path, int(px))


# ------------------------------------------------------------------ words + pause cuts
WORDS = json.load(open(WORK / "words.json"))
for w in WORDS:
    w["w"] = w["w"].strip()
WORDS = [w for w in WORDS if w["w"]]
CUTS = []
for a, b in zip(WORDS, WORDS[1:]):
    if b["s"] - a["e"] > 0.30:
        CUTS.append((a["e"] + 0.12, b["s"] - 0.10))

# Better word timing (words_aligned.json: same words, starts/ends re-measured on the audio). Every cue below was
# written against the first transcript's word starts; rt() moves a cue time onto the re-measured timeline.
_OLD_S = np.array([w["s"] for w in WORDS])
_AL = WORK / "words_aligned.json"
if _AL.exists():
    WORDS = [dict(w, w=w["w"].strip()) for w in json.load(open(_AL)) if w["w"].strip()]
    _NEW_S = np.array([w["s"] for w in WORDS])
    assert len(_NEW_S) == len(_OLD_S), "aligned words must match the transcript word for word"
    # never cut into a re-measured word
    _c = []
    for a, b in CUTS:
        for w in WORDS:
            if w["s"] - 0.08 < b and w["e"] + 0.08 > a:
                if w["s"] >= (a + b) / 2:
                    b = min(b, w["s"] - 0.08)
                else:
                    a = max(a, w["e"] + 0.08)
        if b - a > 0.05:
            _c.append((a, b))
    CUTS = _c
else:
    _NEW_S = _OLD_S


def rt(t):
    return float(np.interp(t, _OLD_S, _NEW_S))


TEXT_LEAD = 0.08   # letters take ~0.3 s to resolve, so they start a touch before the word
POP_LEAD = 0.06    # cards fade in over 0.22 s
CAP_LEAD = 0.03    # captions switch a frame before the first word


def to_out(t):
    return t - sum(min(b, max(a, t)) - a for a, b in CUTS)


def to_src(tau):
    t = tau
    for a, b in CUTS:
        if t >= a:
            t += b - a
    return t


TOTAL = to_out(RAW_END)


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def e_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def e_expo(x):
    x = clamp(x)
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def e_io(x):
    x = clamp(x)
    return 16 * x ** 5 if x < 0.5 else 1 - (-2 * x + 2) ** 5 / 2


def e_sm(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ramp(t, a, b, fin=0.35, fout=0.35):
    if t < a or t > b:
        return 0.0
    return min(e_sm((t - a) / fin) if fin else 1, e_sm((b - t) / fout) if fout else 1)


# ------------------------------------------------------------------ image helpers
def soft_blur(img, sigma):
    h, w = img.shape[:2]
    s = cv2.resize(img, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    s = cv2.GaussianBlur(s, (0, 0), max(0.5, sigma / 4))
    return cv2.resize(s, (w, h), interpolation=cv2.INTER_LINEAR)


def blend_rgba(dst, spr, x, y, alpha=1.0):
    if alpha <= 0.003:
        return
    h, w = spr.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x0 >= x1 or y0 >= y1:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[:, :, 3:4].astype(np.float32) * (alpha / 255.0)
    r = dst[y0:y1, x0:x1].astype(np.float32)
    dst[y0:y1, x0:x1] = (r + (s[:, :, :3].astype(np.float32) - r) * a).astype(np.uint8)


def pil_to_bgra(im):
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGBA2BGRA)


_yy, _xx = np.mgrid[0:OH, 0:OW]
_r = np.sqrt(((_xx - OW / 2) / (OW / 2)) ** 2 + ((_yy - OH / 2) / (OH / 2)) ** 2) / math.sqrt(2)
VIG = np.repeat((np.clip(1 - 0.42 * _r ** 2.3, 0, 1) * 255).astype(np.uint8)[:, :, None], 3, 2)
# soft feathered ellipse around Jan (flipped frame: head centre x~990), 1 inside -> 0 outside
_e = (np.sqrt(((_xx - 540) / 620.0) ** 2 + ((_yy - 800) / 1050.0) ** 2) if VERT else
      np.sqrt(((_xx - 960) / 560.0) ** 2 + ((_yy - 600) / 720.0) ** 2))
HEAD_MASK = np.clip((1.35 - _e) / 0.55, 0, 1).astype(np.float32)[:, :, None]
# dark fade along the bottom for captions
BOTTOM = (np.clip((_yy[:, :1] - OH * 0.62) / (OH * 0.38), 0, 1).astype(np.float32) ** 1.4)[:, :, None]
del _yy, _xx, _r, _e


# ------------------------------------------------------------------ grid page (Ricky's STEP page)
def _make_page(glow=(18, 88, 220)):
    m = 240
    H, W = OH + m, OW + m
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.empty((H, W, 3), np.float32)
    img[:] = (7, 6, 6)
    r1 = np.sqrt(((xx - W * 0.5) / (W * 0.62)) ** 2 + ((yy - H * 1.02) / (H * 0.80)) ** 2)
    g1 = np.clip(1 - r1, 0, 1) ** 1.7
    r2 = np.sqrt(((xx - W * 0.10) / (W * 0.42)) ** 2 + ((yy + H * 0.05) / (H * 0.55)) ** 2)
    g2 = np.clip(1 - r2, 0, 1) ** 2.0
    orange = np.array(glow, np.float32)
    img += orange[None, None] * (g1 * 0.62 + g2 * 0.20)[:, :, None]
    step = 90
    lines = np.zeros((H, W), np.float32)
    lines[:, ::step] = 1
    lines[::step, :] = 1
    lines = cv2.GaussianBlur(lines, (0, 0), 0.7)
    rc = np.sqrt(((xx - W / 2) / (W * 0.52)) ** 2 + ((yy - H * 0.52) / (H * 0.58)) ** 2)
    fade = np.clip(1 - rc, 0, 1) ** 1.2
    img += lines[:, :, None] * (55 * fade + 45 * g1)[:, :, None]
    return np.clip(img, 0, 255).astype(np.uint8), step


GRID, GSTEP = _make_page()
GRID_RED, _ = _make_page((40, 34, 205))


def grid_bg(t, w=OW, x_off=0, red=False):
    ox = int((t * 7) % GSTEP)
    return (GRID_RED if red else GRID)[120:120 + OH, 120 - ox + x_off:120 - ox + x_off + w].copy()


# ------------------------------------------------------------------ shapes, cards, photos
def rr_mask(w, h, r, ss=2):
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=255)
    return np.array(im.resize((w, h), Image.LANCZOS))


def persp(w, h, s=1.0, rx=0.0, ry=0.0, rz=0.0, f=None):
    f = f or 2.4 * max(w, h)
    pts = np.array([[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]], np.float64)
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    out = []
    for x, y in pts:
        x, y, z = x * s, y * s, 0.0
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        k = f / (f + z)
        x, y = x * k, y * k
        x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
        out.append((x, y))
    out = np.array(out)
    ow, oh = int(np.abs(out[:, 0]).max() * 2) + 4, int(np.abs(out[:, 1]).max() * 2) + 4
    dst = (out + [ow / 2, oh / 2]).astype(np.float32)
    src = (pts + [w / 2, h / 2]).astype(np.float32)
    return cv2.getPerspectiveTransform(src, dst), ow, oh


def draw_text_pil(im, xy, text, path, px, color, anchor="la", glow=False):
    d = ImageDraw.Draw(im)
    f = font(path, px)
    if glow:
        gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).text(xy, text, font=f, fill=color[:3] + (255,), anchor=anchor)
        arr = np.array(gl).astype(np.float32)
        a = arr[:, :, 3]
        arr[:, :, 3] = np.clip(cv2.GaussianBlur(a, (0, 0), 5) * 0.55 + cv2.GaussianBlur(a, (0, 0), 18) * 0.45, 0, 255)
        im.alpha_composite(Image.fromarray(arr.astype(np.uint8)))
    d.text(xy, text, font=f, fill=color, anchor=anchor)


@functools.lru_cache(None)
def icon_alpha(kind, size):
    S4 = size * 4
    im = Image.new("L", (S4, S4), 0)
    d = ImageDraw.Draw(im)
    lw = int(S4 * 0.05)
    c = S4 / 2
    if kind == "dollar":
        d.ellipse((S4 * .08, S4 * .08, S4 * .92, S4 * .92), outline=255, width=lw)
        d.text((c, c), "$", font=font(F_SERIF, S4 * .56), fill=255, anchor="mm")
    elif kind == "chart":
        for i, hh in enumerate((.35, .55, .8)):
            x0 = S4 * (.14 + i * .26)
            d.rounded_rectangle((x0, S4 * (.9 - hh), x0 + S4 * .18, S4 * .9), int(S4 * .04), outline=255, width=lw)
    elif kind == "down":
        d.line([(S4 * .2, S4 * .78), (S4 * .45, S4 * .5), (S4 * .62, S4 * .64), (S4 * .86, S4 * .3)],
               fill=255, width=lw, joint="curve")
    elif kind == "gear":
        d.ellipse((S4 * .22, S4 * .22, S4 * .78, S4 * .78), outline=255, width=lw)
        d.ellipse((S4 * .4, S4 * .4, S4 * .6, S4 * .6), outline=255, width=lw)
        for k in range(8):
            a = k * math.pi / 4
            d.line([(c + math.cos(a) * S4 * .28, c + math.sin(a) * S4 * .28),
                    (c + math.cos(a) * S4 * .42, c + math.sin(a) * S4 * .42)], fill=255, width=int(lw * 1.6))
    elif kind == "clock":
        d.ellipse((S4 * .1, S4 * .1, S4 * .9, S4 * .9), outline=255, width=lw)
        d.line([(c, c), (c, S4 * .26)], fill=255, width=lw)
        d.line([(c, c), (S4 * .68, S4 * .6)], fill=255, width=lw)
    elif kind == "phone":
        d.rounded_rectangle((S4 * .3, S4 * .06, S4 * .7, S4 * .94), int(S4 * .08), outline=255, width=lw)
        d.line([(S4 * .44, S4 * .84), (S4 * .56, S4 * .84)], fill=255, width=lw)
    elif kind == "mail":
        d.rounded_rectangle((S4 * .08, S4 * .22, S4 * .92, S4 * .78), int(S4 * .06), outline=255, width=lw)
        d.line([(S4 * .1, S4 * .26), (c, S4 * .56), (S4 * .9, S4 * .26)], fill=255, width=lw, joint="curve")
    elif kind == "calendar":
        d.rounded_rectangle((S4 * .1, S4 * .16, S4 * .9, S4 * .9), int(S4 * .07), outline=255, width=lw)
        d.line([(S4 * .1, S4 * .36), (S4 * .9, S4 * .36)], fill=255, width=lw)
        for x in (.32, .68):
            d.line([(S4 * x, S4 * .08), (S4 * x, S4 * .24)], fill=255, width=lw)
        for i in range(3):
            for j in range(2):
                d.ellipse((S4 * (.26 + i * .2), S4 * (.5 + j * .18), S4 * (.32 + i * .2), S4 * (.56 + j * .18)),
                          fill=255)
    elif kind == "check":
        d.ellipse((S4 * .08, S4 * .08, S4 * .92, S4 * .92), outline=255, width=lw)
        d.line([(S4 * .3, S4 * .52), (S4 * .45, S4 * .67), (S4 * .72, S4 * .36)], fill=255, width=lw, joint="curve")
    elif kind == "brain":
        d.ellipse((S4 * .12, S4 * .2, S4 * .6, S4 * .78), outline=255, width=lw)
        d.ellipse((S4 * .4, S4 * .2, S4 * .88, S4 * .78), outline=255, width=lw)
    return cv2.resize(np.array(im), (size, size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def _frame_layers(w, h, accent, r, tone="gold"):
    """shared Ricky-card chrome: mask, gradient body, rim with light sweep, glows, drop shadow."""
    g = 90
    W, H = w + 2 * g, h + 2 * g
    m = rr_mask(w, h, r).astype(np.float32) / 255
    full = np.zeros((H, W), np.float32)
    full[g:g + h, g:g + w] = m
    YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = (XX - g) / w, (YY - g) / h
    d = np.clip(u * 0.55 + v * 0.45, 0, 1)
    rim = np.clip(full - cv2.erode(full, np.ones((3, 3), np.uint8), iterations=2), 0, 1)
    sweep = np.clip(1 - d * 1.1, 0, 1) ** 1.3
    rim_i = rim * (0.16 + 0.84 * sweep)
    glow_t = np.clip(cv2.GaussianBlur(rim_i, (0, 0), 7) * 2.4, 0, 1)
    glow_w = np.clip(cv2.GaussianBlur(rim_i, (0, 0), 30) * 3.0, 0, 1)
    shadow = np.roll(cv2.GaussianBlur(full, (0, 0), 28), 20, 0) * 0.75 * (1 - full)
    return dict(g=g, W=W, H=H, full=full, XX=XX, YY=YY, u=u, d=d, rim_i=rim_i, glow_t=glow_t, glow_w=glow_w,
                shadow=shadow, accent=accent, tone=tone)


def _compose(L, body_rgb, extra=None):
    full, outside = L["full"], 1 - L["full"]
    rgbf = np.zeros((L["H"], L["W"], 3), np.float32)
    a = np.zeros((L["H"], L["W"]), np.float32)

    def over(col, al):
        nonlocal rgbf, a
        al3 = al[:, :, None]
        rgbf = rgbf * (1 - al3) + col * al3
        a = a + al * (1 - a)

    red = L.get("tone") == "red"
    rimcol = np.array((255, 70, 60) if red else (255, 156, 64), np.float32)
    over(np.zeros(3, np.float32), L["shadow"])
    over(rimcol, L["glow_w"] * outside * (0.42 if L["accent"] else 0.30))
    over(rimcol, L["glow_t"] * outside * (0.75 if L["accent"] else 0.55))
    over(body_rgb, full * 0.97)
    if extra is not None:
        over(*extra)
    over(np.array((255, 150, 140) if red else (255, 196, 140), np.float32), L["rim_i"])
    return rgbf, a


@functools.lru_cache(None)
def ui_card(w, h, main="", sub="", style="sans", icon=None, accent=False, check=False, main_px=0, align="c",
            sub_px=0, tone="gold"):
    """Ricky's card: rounded rect, orange -> black gradient, faded grid inside, glowing orange rim, faded icon."""
    r = int(min(56, h * 0.28))
    L = _frame_layers(w, h, accent, r, tone)
    g, W, H, XX, YY, u, d = L["g"], L["W"], L["H"], L["XX"], L["YY"], L["u"], L["d"]
    warm = np.clip(1 - d * 1.25, 0, 1) ** 1.5
    orange = np.array((205, 30, 30) if tone == "red" else (232, 104, 24), np.float32)
    dark = np.array((9, 8, 8), np.float32)
    body = dark + (orange - dark) * (warm * (0.62 if accent else 0.42))[:, :, None]
    step = 30
    gl = np.zeros((H, W), np.float32)
    gl[:, g % step::step] = 1
    gl[g % step::step, :] = 1
    gl = cv2.GaussianBlur(gl, (0, 0), 0.6)
    body = body + gl[:, :, None] * (8 + 46 * warm)[:, :, None]
    hl = np.exp(-((YY - g - 3) / 3.0) ** 2) * np.clip(1 - u * 1.2, 0, 1)
    body = body + hl[:, :, None] * 40
    extra = None
    if icon:
        size = int(h * 1.05)
        ia = icon_alpha(icon, size)
        lay = np.zeros((H, W), np.float32)
        x0, y0 = int(g + w - size * 0.72), int(g + (h - size) / 2)
        xs0, xs1 = max(0, x0), min(W, x0 + size)
        lay[y0:y0 + size, xs0:xs1] = ia[:, xs0 - x0:xs1 - x0]
        wipe = np.clip((XX - x0) / size * 1.4 - 0.1, 0, 1) * 0.16
        extra = (np.array((255, 214, 170), np.float32), lay * wipe * L["full"])
    rgbf, a = _compose(L, body, extra)
    # NB: colours above are RGB (PIL), converted at the end
    im = Image.fromarray(np.dstack([rgbf, a * 255]).clip(0, 255).astype(np.uint8), "RGBA")
    gold = (250, 172, 48, 255)
    x = g + 44
    if check:
        dd = ImageDraw.Draw(im)
        rr = min(h * 0.2, 26)
        cy = g + h / 2
        dd.ellipse((x, cy - rr, x + 2 * rr, cy + rr), fill=gold)
        dd.line([(x + rr * .55, cy + rr * .02), (x + rr * .9, cy + rr * .38), (x + rr * 1.5, cy - rr * .4)],
                fill=(14, 14, 16, 255), width=5, joint="curve")
        x += 2 * rr + 26
    if main:
        serif = style == "serif"
        px = main_px if main_px else (h * (0.36 if serif else 0.2))
        path = F_SERIF if serif else F_SANS
        room = (w - (x - g) - 40 if align != "c" else w * 0.84) - (h * 0.25 if icon and align == "c" else 0)
        while px > 24 and font(path, px).getlength(main) > room:   # always fits inside the card
            px -= 2
        col = (255, 72, 66, 255) if tone == "red" else gold if (serif and accent) else (246, 244, 242, 255)
        cy = g + h * (0.42 if sub else 0.5)
        anchor = "mm" if align == "c" else "lm"
        draw_text_pil(im, (g + w / 2 if align == "c" else x, cy), main, path, px, col, anchor,
                      glow=serif and (accent or tone == "red"))
        if sub:
            draw_text_pil(im, (g + w / 2 if align == "c" else x, g + h * 0.76), sub, F_SANS_M,
                          sub_px or h * 0.085, (214, 206, 198, 255), anchor)
    return pil_to_bgra(im), g


@functools.lru_cache(None)
def photo_card(name, w, max_h=10000, rz=0.0, accent=False):
    """a picture inside Ricky's card chrome (glowing orange rim, deep glow, drop shadow), optionally rotated."""
    src = cv2.imread(str(IMG / name))
    sh, sw = src.shape[:2]
    h = int(round(w * sh / sw))
    if h > max_h:
        h = max_h
        w = int(round(h * sw / sh))
    pic = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA)
    L = _frame_layers(w, h, accent, 22)
    g = L["g"]
    body = np.zeros((L["H"], L["W"], 3), np.float32)
    body[g:g + h, g:g + w] = pic[:, :, ::-1].astype(np.float32)  # BGR -> RGB
    rgbf, a = _compose(L, body)
    spr = cv2.cvtColor(np.dstack([rgbf, a * 255]).clip(0, 255).astype(np.uint8), cv2.COLOR_RGBA2BGRA)
    if rz:
        H, W = spr.shape[:2]
        M = cv2.getRotationMatrix2D((W / 2, H / 2), rz, 1.0)
        c, s = abs(M[0, 0]), abs(M[0, 1])
        nW, nH = int(H * s + W * c), int(H * c + W * s)
        M[0, 2] += nW / 2 - W / 2
        M[1, 2] += nH / 2 - H / 2
        spr = cv2.warpAffine(spr, M, (nW, nH), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    return spr, g


def pop_in(dst, spr_g, cx, cy, t, t0, t_out=None, dur=0.8, rise=90):
    """UI pop-up: scale + rise + 3D tilt settling flat; fast entry, long settle; tilt away on exit."""
    spr, g = spr_g
    t0 = rt(t0) - POP_LEAD
    if t < t0 or (t_out is not None and t > t_out):
        return
    p = e_expo((t - t0) / dur)
    a = clamp((t - t0) / 0.22)
    q = 0.0
    if t_out is not None:
        q = e_sm(clamp((t - (t_out - 0.35)) / 0.35))
        a *= 1 - q
    if a <= 0.003:
        return
    s = 0.74 + 0.26 * p - 0.06 * q
    rx = 32 * (1 - p) - 14 * q
    h, w = spr.shape[:2]
    if abs(rx) < 0.05 and abs(s - 1) < 0.002:
        im = spr
    else:
        Hm, ow, oh = persp(w, h, s, rx=rx)
        im = cv2.warpPerspective(spr, Hm, (ow, oh), flags=cv2.INTER_LINEAR)
    h2, w2 = im.shape[:2]
    blend_rgba(dst, im, cx - w2 / 2, cy - h2 / 2 + ((1 - p) * rise - q * 30), a)


# ------------------------------------------------------------------ per-character text engine (Ricky)
BLUR_LEVELS = [0, 1.5, 3, 5, 7.5, 10]


class TextSeq:
    """lines: [[(word, style, t_start), ...], ...]  style 'sans' | 'serif' | 'grey' | 'red'."""

    def __init__(self, lines, t_out, centre=(OW / 2, OH / 2), sizes=(84, 150), gap=1.0, align="c",
                 stagger=0.035, dur=0.5, ry=0.0, rz=0.0, shadow=0.55, base=None, spread=0.45):
        self.t_out, self.stagger, self.dur = t_out, stagger, dur
        self.ry, self.rz, self.shadow = ry, rz, shadow
        self.chars = []
        sans_px, serif_px = sizes
        # never wider than 90 % of the frame (matters in 9:16)
        def _w(sp, rp):
            ws = []
            for ln in lines:
                tot = 0.0
                for wi, (word, style, _) in enumerate(ln):
                    f = font(*((F_SERIF, rp) if style in ("serif", "red") else
                               (F_SANS_M, sp * 0.42) if style == "grey" else (F_SANS, sp)))
                    tot += f.getlength(word) + (f.getlength(" ") if wi < len(ln) - 1 else 0)
                ws.append(tot)
            return max(ws)
        fit = min(1.0, 0.9 * OW / max(1.0, _w(sans_px, serif_px)))
        sans_px, serif_px = sans_px * fit, serif_px * fit
        heights, layouts = [], []
        # readable: the whole phrase builds within ~0.45 s of its first word, then holds until t_out
        ts = (rt(base) if base is not None else min(rt(w[2]) for ln in lines for w in ln)) - TEXT_LEAD
        for line in lines:
            x, items, lh = 0.0, [], 0
            for wi, (word, style, t0) in enumerate(line):
                t0 = ts + min((rt(t0) - TEXT_LEAD - ts) * 0.45, spread)
                path, px = ((F_SERIF, serif_px) if style in ("serif", "red") else
                            (F_SANS_M, sans_px * 0.42) if style == "grey" else (F_SANS, sans_px))
                f = font(path, px)
                items.append((word, style, t0, f, px, x))
                x += f.getlength(word) + (f.getlength(" ") if wi < len(line) - 1 else 0)
                lh = max(lh, px)
            layouts.append((items, x))
            heights.append(lh)
        y = centre[1] - sum(heights) * gap / 2
        self.box = [1e9, 1e9, -1e9, -1e9]
        for (items, width), lh in zip(layouts, heights):
            base_y = y + lh * 0.80
            x0 = {"c": centre[0] - width / 2, "r": centre[0] - width, "l": centre[0]}[align]
            for word, style, t0, f, px, wx in items:
                for i, ch in enumerate(word):
                    if ch == " ":
                        continue
                    self._add_char(ch, f, px, x0 + wx + f.getlength(word[:i]), base_y, style, t0 + i * stagger)
            y += lh * gap
        mg = 130
        self.box = [int(max(0, self.box[0] - mg)), int(max(0, self.box[1] - mg)),
                    int(min(OW, self.box[2] + mg)), int(min(OH, self.box[3] + mg))]
        self.H = None
        if self.ry or self.rz:
            x0, y0, x1, y1 = self.box
            w, h = x1 - x0, y1 - y0
            Hm, ow, oh = persp(w, h, 1.0, ry=self.ry, rz=self.rz, f=3.0 * w)
            T = np.array([[1, 0, -(ow - w) / 2], [0, 1, -(oh - h) / 2], [0, 0, 1]])
            self.H = (T @ Hm).astype(np.float64)

    def _add_char(self, ch, f, px, x, base_y, style, t0):
        pad = int(max(px * 0.5, 60))
        adv = f.getlength(ch)
        w, h = int(adv + 2 * pad), int(px * 1.25 + 2 * pad)
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).text((pad, pad + px * 0.95), ch, font=f, fill=255, anchor="ls")
        a = np.array(im).astype(np.float32) / 255
        levels = [a if s == 0 else cv2.GaussianBlur(a, (0, 0), s) for s in BLUR_LEVELS]
        glow = None
        if style in ("serif", "red"):
            glow = cv2.GaussianBlur(a, (0, 0), 4) * 0.7 + cv2.GaussianBlur(a, (0, 0), 16) * 0.65
        colour = {"serif": ACCENT, "sans": WHITE, "grey": SECOND, "red": RED}[style]
        ox, oy = x - pad, base_y - pad - px * 0.95
        self.chars.append(dict(levels=levels, glow=glow, col=np.array(colour, np.float32), x=ox, y=oy, t0=t0, px=px))
        self.box[0] = min(self.box[0], ox + pad * 0.6)
        self.box[1] = min(self.box[1], oy + pad * 0.6)
        self.box[2] = max(self.box[2], ox + w - pad * 0.6)
        self.box[3] = max(self.box[3], oy + h - pad * 0.6)

    def serif_span(self):
        cs = [c for c in self.chars if c["glow"] is not None]
        if not cs:
            return None
        pad = max(cs[0]["px"] * 0.5, 60)
        return (min(c["x"] for c in cs) + pad, max(c["x"] for c in cs) + pad + cs[-1]["px"] * 0.5,
                max(c["y"] for c in cs) + pad + cs[0]["px"] * 1.12)

    def active(self, t):
        return self.chars and self.chars[0]["t0"] - 0.05 <= t <= self.t_out + 0.05

    def draw(self, dst, t):
        if not self.active(t):
            return
        tq = math.floor(t * 15) / 15
        x0, y0, x1, y1 = self.box
        if x1 <= x0 or y1 <= y0:
            return
        bw, bh = x1 - x0, y1 - y0
        C = np.zeros((bh, bw, 3), np.float32)
        A = np.zeros((bh, bw), np.float32)
        G = np.zeros((bh, bw, 3), np.float32)
        q_out = clamp((t - (self.t_out - 0.35)) / 0.35)
        any_ = False
        for c in self.chars:
            p = (tq - c["t0"]) / self.dur
            if p <= 0:
                continue
            e = e_out(p)
            alpha = clamp(p * 1.8) * (1 - q_out)
            if alpha <= 0.002:
                continue
            any_ = True
            lvl = int(round((1 - e) * 5 + q_out * 4))
            m = c["levels"][min(5, lvl)]
            dy = (1 - e) * 0.45 * c["px"] - e_sm(q_out) * 0.18 * c["px"]
            col = c["col"] + (np.array(INTRO, np.float32) - c["col"]) * (1 - e_sm(clamp(p * 1.3)))
            cx, cy = int(round(c["x"])) - x0, int(round(c["y"] + dy)) - y0
            h, w = m.shape
            a0, b0 = max(cx, 0), max(cy, 0)
            a1, b1 = min(cx + w, bw), min(cy + h, bh)
            if a0 >= a1 or b0 >= b1:
                continue
            mm = m[b0 - cy:b1 - cy, a0 - cx:a1 - cx] * alpha
            C[b0:b1, a0:a1] = C[b0:b1, a0:a1] * (1 - mm[:, :, None]) + col * mm[:, :, None]
            A[b0:b1, a0:a1] = A[b0:b1, a0:a1] + mm * (1 - A[b0:b1, a0:a1])
            if c["glow"] is not None:
                gg = c["glow"][b0 - cy:b1 - cy, a0 - cx:a1 - cx][:, :, None] * (alpha * e)
                G[b0:b1, a0:a1] += gg * col * 0.42
        if not any_:
            return
        if self.H is not None:
            C = cv2.warpPerspective(C, self.H, (bw, bh), flags=cv2.INTER_LINEAR)
            A = cv2.warpPerspective(A, self.H, (bw, bh), flags=cv2.INTER_LINEAR)
            G = cv2.warpPerspective(G, self.H, (bw, bh), flags=cv2.INTER_LINEAR)
        roi = dst[y0:y1, x0:x1].astype(np.float32)
        if self.shadow:
            sh = cv2.GaussianBlur(A, (0, 0), 7) * self.shadow
            roi *= (1 - sh)[:, :, None]
        roi = roi * (1 - A[:, :, None]) + C + G
        dst[y0:y1, x0:x1] = np.clip(roi, 0, 255).astype(np.uint8)


class Stroke:
    """trim-path line that draws on."""

    def __init__(self, pts, t0, t_out, dur=0.55, colour=ACCENT, width=7):
        self.pts = np.array(pts, np.float32)
        t0 = rt(t0)
        self.t0, self.t_out, self.dur, self.col, self.w = t0, t_out, dur, colour, width
        seg = np.linalg.norm(np.diff(self.pts, axis=0), axis=1)
        self.cum = np.concatenate([[0], np.cumsum(seg)])

    def draw(self, dst, t):
        if t < self.t0 or t > self.t_out:
            return
        p = e_io((t - self.t0) / self.dur)
        a = 1 - clamp((t - (self.t_out - 0.3)) / 0.3)
        Lw = self.cum[-1] * p
        pts = self.pts
        keep = [pts[0]]
        for i in range(1, len(pts)):
            if self.cum[i] <= Lw:
                keep.append(pts[i])
            else:
                f = (Lw - self.cum[i - 1]) / max(1e-6, self.cum[i] - self.cum[i - 1])
                keep.append(pts[i - 1] + (pts[i] - pts[i - 1]) * f)
                break
        poly = np.array(keep, np.float32)
        if len(poly) < 2:
            return
        x0, y0 = np.floor(poly.min(0) - 60).astype(int)
        x1, y1 = np.ceil(poly.max(0) + 60).astype(int)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(OW, x1), min(OH, y1)
        if x1 <= x0 or y1 <= y0:
            return
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.polylines(m, [((poly - (x0, y0)) * 4).astype(np.int32)], False, 255, int(self.w), cv2.LINE_AA, 2)
        mf = m.astype(np.float32) / 255
        gl = cv2.GaussianBlur(mf, (0, 0), 9)
        roi = dst[y0:y1, x0:x1].astype(np.float32)
        col = np.array(self.col, np.float32)
        roi += gl[:, :, None] * col * 0.6 * a
        roi += (col - roi) * (mf[:, :, None] * a)
        dst[y0:y1, x0:x1] = np.clip(roi, 0, 255).astype(np.uint8)


def curve(x0, y0, x1, y1, bend=0.0, n=40):
    t = np.linspace(0, 1, n)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2 + bend
    xs = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t ** 2 * x1
    ys = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t ** 2 * y1
    return list(zip(xs, ys))


def underline(seq, t0, t_out, colour=ACCENT, width=6, dy=0):
    x0, x1, y = seq.serif_span()
    return Stroke(curve(x0 - 10, y + dy, x1 + 10, y + dy - 8, 14), t0, t_out, dur=0.6, colour=colour, width=width)


def L(*words):
    return list(words)


def PY(y):
    """vertical position of full-screen page text (designed for 1080 tall)."""
    return 960 + (y - 540) * 1.25 if VERT else y


CW, CH = (600, 270) if VERT else (420, 300)                       # card size in the rows of three
SLOTS = ([(540, 650), (540, 965), (540, 1280)] if VERT else [(460, 540), (960, 540), (1460, 540)])
PHOTO_XY = (540, 1150) if VERT else (1500, 480)
CAP_Y = 1560 if VERT else 935


# ================================================================== THE EDIT (seconds in the assembled clean cut): ACE VSL
# The clean cut comes from tools/ace_assemble.py (best takes of the raw session). Same look as Jan's videos.
FACE_C = (960, 470)
WIDE = (960, 540)
CL = FACE_C
SL, SR_ = 650, 1270


def side(left, right, t_out, y=430, sizes=(88, 130), sl=SL, sr=SR_):
    def width(lines, path, px):
        f = font(path, px)
        return max(f.getlength(" ".join(w for w, _, _ in ln)) for ln in lines)
    sans_px, serif_px = sizes
    lw = width(left, F_SANS, sans_px)
    while serif_px > 90 and width(right, F_SERIF, serif_px) > 1.12 * lw:
        serif_px -= 2
    base = min(w[2] for ln in left + right for w in ln)
    return [TextSeq(left, t_out, (sl, y), sizes=(sans_px, serif_px), align="r", ry=-12, rz=-1.5, base=base,
                    spread=0.6),
            TextSeq(right, t_out, (sr, y + 10), sizes=(sans_px, serif_px), align="l", ry=14, rz=3, stagger=0.045,
                    base=base, spread=0.6)]


def W_(text, style, t0, step=0.12):
    """words of one line, each a little after the previous: W_("a b c", "sans", 1.0)."""
    return [(w, style, t0 + i * step) for i, w in enumerate(text.split())]


PAGES = []


def page(t0, t1, texts, strokes=(), tone="gold", under=()):
    PAGES.append((t0, t1, texts, list(strokes), tone, list(under)))


def label(words, t0, t_out, y=330):
    return TextSeq([L(*[(w, "grey", t0 + 0.04 * i) for i, w in enumerate(words.split())])], t_out, (OW / 2, y),
                   sizes=(96, 96), stagger=0.03)


def zigzag(x0, y0, x1, y1, n=9, amp=70, seed=3):
    r = np.random.default_rng(seed)
    return [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n + (r.uniform(-1, 1) * amp if 0 < i < n else 0))
            for i in range(n + 1)]


SLOTS = [(415, 560), (960, 560), (1505, 560)]
CW, CH = 510, 300
TWO = [(600, 560), (1320, 560)]
TW = 560
PHOTO_XY = (1500, 480)
CAP_Y = 935
CARDS, STRIKES, LINKS, UNDER_TEXT, SIDES, FLASHES, CHING = [], [], [], [], [], [], []
CARD_DIM, DIM_KEEP, PHOTO_DIM = [], [], []
MONTAGE, MONT_IMGS, MONT_LABEL = (-10.0, -9.0), [], None


def card(w, h, x, y, t0, t1, **kw):
    CARDS.append((kw, (w, h), x, y, t0, t1))


def strike(x, y, w, t0, t1, colour=RED):
    STRIKES.append((x - w / 2 + 35, y + 5, x + w / 2 - 35, y - 15, t0, t1, colour))


def link(a, b, t0, t1, w=CW):
    (ax, ay), (bx, by) = a, b
    LINKS.append((ax + w / 2 - 3, ay, bx - w / 2 + 3, by, t0, t1))


def over(text_lines, t_out, y=300, sizes=(80, 120)):
    UNDER_TEXT.append(TextSeq(text_lines, t_out, (OW / 2, y), sizes=sizes))


RAW_END = 185.30   # the clean cut is 184.3 s; the last frame holds a second for the sign-off, then fades

# camera: AB staircase pushes, resets under a light leak or a smooth pull-out
ZK = [(0.00, 1.30, 0.0, *CL), (0.05, 1.0, 1.0, *WIDE),
      (13.70, 1.15, 0.8, *CL), (15.95, 1.0, 0.0, *WIDE),
      (20.10, 1.15, 0.7, *CL), (21.20, 1.30, 0.7, *CL), (21.95, 1.0, 0.5, *WIDE),
      (24.10, 1.14, 0.8, *CL), (26.50, 1.0, 0.5, *WIDE),
      (52.20, 1.15, 0.7, *CL), (53.85, 1.32, 0.7, *CL), (55.95, 1.0, 0.0, *WIDE),
      (67.40, 1.12, 0.8, *CL), (69.10, 1.0, 0.4, *WIDE),
      (78.80, 1.15, 0.7, *CL), (80.55, 1.30, 0.7, *CL), (82.45, 1.0, 0.0, *WIDE),
      (108.70, 1.15, 0.7, *CL), (110.55, 1.30, 0.7, *CL), (112.45, 1.0, 0.0, *WIDE),
      (113.10, 1.12, 0.9, *CL), (115.40, 1.0, 0.4, *WIDE),
      (153.95, 1.15, 0.8, *CL), (156.40, 1.0, 0.4, *WIDE),
      (175.50, 1.15, 0.6, *CL), (176.95, 1.0, 0.0, *WIDE),
      (183.30, 1.0, 0.0, *WIDE)]
FLASHES += [55.95, 112.45]

# ---------------------------------------------------------------- 0:00 hook
SIDES.append((0.0, 1.90, side([L(*W_("For two years", "sans", 0.0, 0.18))],
                              [L(("trading", "red", 0.82)), L(("didn't", "red", 1.10), ("work", "red", 1.36))], 1.90)))
card(640, 380, 960, 560, 2.18, 4.05, main="-$1,200", sub="for a mentorship", style="serif", main_px=150, sub_px=30,
     tone="red", icon="down")
CARD_DIM.append((1.95, 4.05))
SIDES.append((4.10, 6.98, side([L(("couldn't", "sans", 4.64), ("pass", "sans", 4.90)), L(("an", "sans", 5.14), ("eval", "sans", 5.28))],
                               [L(("for", "red", 5.56), ("1.5", "red", 6.02)), L(("years", "red", 6.20))], 6.98)))
card(TW, CH, 960, 560, 8.70, 10.72, main="A wall of payouts", sub="like all the gurus do", main_px=64, sub_px=30,
     icon="dollar")
strike(960, 560, TW, 9.70, 10.70)
CARD_DIM.append((7.30, 10.72))
page(10.75, 13.60, [label("INSTEAD", 10.78, 13.56),
                    TextSeq([L(("My", "sans", 11.82), ("students'", "sans", 12.34))], 13.56, (OW / 2, 500), sizes=(110, 200)),
                    TextSeq([L(("results", "serif", 13.06))], 13.56, (OW / 2, 690), sizes=(110, 240))])
_g = TextSeq([L(("$100,000", "serif", 18.26))], 19.91, (OW / 2, 520), sizes=(110, 260), stagger=0.05)
page(15.95, 19.95, [label("I GUARANTEE YOU'LL PASS", 16.08, 19.91, y=320), _g,
                    TextSeq([L(("funded", "sans", 19.04), ("account", "sans", 19.30))], 19.91, (OW / 2, 740),
                            sizes=(100, 150))], [underline(_g, 18.7, 19.91)])
card(TW + 80, 320, 960, 560, 22.62, 24.02, main="Every single cent back", sub="if you don't pass", style="serif",
     accent=True, main_px=80, sub_px=32, icon="check")
CARD_DIM.append((22.05, 24.02))
CHING.append(23.26)

# ---------------------------------------------------------------- 0:27 student proof
over([L(("STUDENT", "grey", 27.10), ("RESULTS:", "grey", 27.14), ("BRANDON", "sans", 27.20))], 32.98, y=330,
     sizes=(90, 90))
card(TW, CH, *TWO[0], 28.20, 32.98, main="Zero experience", sub="never traded before", style="serif", main_px=78,
     sub_px=30, tone="red", icon="down")
card(TW, CH, *TWO[1], 31.68, 32.98, main="First payout", sub="in 2 weeks", style="serif", accent=True, main_px=96,
     sub_px=34, icon="check")
link(TWO[0], TWO[1], 31.5, 32.95, w=TW)
CHING.append(31.94)
over([L(("STUDENT", "grey", 33.52), ("RESULTS:", "grey", 33.56), ("ZLADE", "sans", 33.60))], 40.88, y=330,
     sizes=(90, 90))
card(CW, CH, *SLOTS[0], 33.92, 40.88, main="Failed 7 months", sub="before working with me", style="serif",
     main_px=70, sub_px=28, tone="red", icon="down")
card(CW, CH, *SLOTS[1], 38.44, 40.88, main="3 evals passed", sub="from the 8th month", style="serif", accent=True,
     main_px=76, sub_px=28, icon="check")
card(CW, CH, *SLOTS[2], 40.46, 40.88, main="Got paid", sub="", style="serif", accent=True, main_px=96, icon="dollar")
link(SLOTS[0], SLOTS[1], 38.3, 40.85)
link(SLOTS[1], SLOTS[2], 40.3, 40.85)
CARD_DIM.append((27.05, 40.90))
CHING.append(40.66)

# ---------------------------------------------------------------- 0:41 the pain
SIDES.append((40.94, 43.30, side([L(("buying", "sans", 41.68), ("eval", "sans", 41.96))],
                                 [L(("after", "red", 42.44), ("eval", "red", 42.76))], 43.30)))
card(TW, 340, 960, 560, 44.00, 45.90, main="$200 away", sub="from passing", style="serif", main_px=120, sub_px=34,
     tone="red", icon="chart")
CARD_DIM.append((43.32, 45.90))
page(45.92, 49.62, [TextSeq([L(*W_("One bad day", "sans", 46.74, 0.37))], 49.58, (OW / 2, 430), sizes=(110, 170)),
                    TextSeq([L(("wipes", "red", 47.78), ("out", "red", 48.16), ("the", "red", 48.38), ("good", "red", 49.06),
                               ("ones", "red", 49.26))], 49.58, (OW / 2, 620), sizes=(110, 170))],
     tone="red", under=[Stroke(zigzag(160, 180, 1760, 930, n=11, amp=90, seed=5), 46.0, 49.58, dur=1.6,
                               colour=(40, 40, 170), width=14)])
SIDES.append((49.65, 52.05, side([L(("just", "sans", 50.94), ("one", "sans", 51.08), ("more", "sans", 51.42))],
                                 [L(("account", "red", 51.64))], 52.05)))

# ---------------------------------------------------------------- 0:56 his story
_p = TextSeq([L(("$10", "red", 58.94))], 59.91, (OW / 2, 520), sizes=(110, 270))
page(56.00, 59.95, [label("POPCORN MACHINE, MOVIE THEATER", 56.88, 59.91, y=320), _p,
                    TextSeq([L(("an", "sans", 59.32), ("hour", "sans", 59.60))], 59.91, (OW / 2, 740), sizes=(100, 150))])
SIDES.append((61.70, 63.72, side([L(("never", "sans", 62.06), ("work", "sans", 62.32)), L(("a", "sans", 62.58), ("job", "sans", 62.68))],
                                 [L(("ever", "serif", 62.92)), L(("again", "serif", 63.24))], 63.72)))
card(TW, CH, 960, 560, 65.68, 67.32, main="Live account", sub="saved up for it, then blew it", style="serif",
     main_px=96, sub_px=30, tone="red", icon="down")
strike(960, 560, TW, 66.74, 67.30, colour=WHITE)
CARD_DIM.append((65.30, 67.32))
card(TW, CH, *TWO[0], 70.20, 75.80, main="-$1,200", sub="for a mentorship", style="serif", main_px=120, sub_px=30,
     tone="red", icon="down")
card(TW, CH, *TWO[1], 73.66, 75.80, main="20-minute videos", sub="then he left me", main_px=58, sub_px=30,
     icon="clock")
link(TWO[0], TWO[1], 73.5, 75.75, w=TW)
CARD_DIM.append((69.62, 75.80))
card(CW, CH, *SLOTS[0], 76.00, 78.66, main="No check-ins", style="serif", main_px=72, tone="red")
card(CW, CH, *SLOTS[1], 76.92, 78.66, main="No follow-ups", style="serif", main_px=72, tone="red")
card(CW, CH, *SLOTS[2], 77.98, 78.66, main="No nothing", style="serif", main_px=80, tone="red")
CARD_DIM.append((75.82, 78.66))

# ---------------------------------------------------------------- 1:22 the deal (split screen)
SPLIT = (82.45, 108.45)
OFFER = [("1-on-1, step by step until you're funded", 83.78),
         ("No years of experience needed", 87.76),
         ("No 50 different concepts to learn", 90.82),
         ("Simple rules that decide for you", 93.48),
         ("Every week I review your trades with you", 97.44),
         ("Pass $100,000 or every single cent back", 101.68)]
OFFER_TITLE = TextSeq([L(("Here's", "sans", 82.80), ("my", "serif", 83.24), ("deal", "serif", 83.36))], 108.25,
                      (1440, 150), sizes=(70, 110))
CHING.append(106.90)

# ---------------------------------------------------------------- 1:48 why the guarantee
SIDES.append((115.80, 117.45, side([L(("are", "sans", 116.52), ("you", "sans", 116.72)), L(("making", "sans", 116.82))],
                                   [L(("money", "serif", 117.02)), L(("yet?", "serif", 117.28))], 117.45)))
card(CW, CH, *SLOTS[0], 119.52, 122.95, main="Graduate college", style="serif", main_px=70, icon="check")
card(CW, CH, *SLOTS[1], 120.60, 122.95, main="A job I didn't like", style="serif", main_px=64, tone="red")
card(CW, CH, *SLOTS[2], 121.66, 122.95, main="Trade on the side", style="serif", main_px=66, icon="chart")
link(SLOTS[0], SLOTS[1], 120.5, 122.9)
link(SLOTS[1], SLOTS[2], 121.5, 122.9)
CARD_DIM.append((119.20, 122.95))
page(123.00, 127.45, [label("THEN IT CLICKED", 123.32, 127.41, y=330),
                      TextSeq([L(("My", "sans", 124.22), ("problem", "sans", 124.32), ("wasn't", "sans", 124.72), ("the", "sans", 125.20),
                                 ("strategy.", "sans", 125.38))], 127.41, (OW / 2, 500), sizes=(96, 150)),
                      TextSeq([L(("It", "serif", 126.52), ("was", "serif", 126.86), ("me.", "serif", 127.04))], 127.41,
                              (OW / 2, 690), sizes=(110, 250))])
card(CW, CH, *SLOTS[0], 127.76, 135.45, main="FOMO", style="serif", main_px=110, tone="red", icon="brain")
card(CW, CH, *SLOTS[1], 128.68, 135.45, main="Revenge trading", style="serif", main_px=70, tone="red", icon="down")
card(CW, CH, *SLOTS[2], 132.24, 135.45, main="Simple rules", sub="decide, not my emotions", style="serif",
     accent=True, main_px=84, sub_px=28, icon="gear")
strike(*SLOTS[0], CW, 129.94, 135.42, colour=WHITE)
strike(*SLOTS[1], CW, 130.24, 135.42, colour=WHITE)
link(SLOTS[1], SLOTS[2], 132.1, 135.4)
CARD_DIM.append((127.50, 135.45))
card(760, 130, 960, 420, 135.96, 139.45, main="Passed", check=True, align="l", main_px=44)
card(760, 130, 960, 570, 136.76, 139.45, main="Got paid", check=True, align="l", main_px=44)
card(760, 130, 960, 720, 138.28, 139.45, main="Paid every single month since", check=True, align="l", main_px=40,
     accent=True)
CARD_DIM.append((135.52, 139.48))
CHING.append(136.94)

# ---------------------------------------------------------------- 2:20 Koi
over([L(("STUDENT", "grey", 141.16), ("RESULTS:", "grey", 141.20), ("KOI", "sans", 141.24))], 150.30, y=330,
     sizes=(90, 90))
card(CW, CH, *SLOTS[0], 142.12, 150.30, main="Ex-military", sub="started trading ICT", style="serif", main_px=84,
     sub_px=28, icon="check")
card(CW, CH, *SLOTS[1], 145.12, 150.30, main="Payouts now & then", sub="never consistent", style="serif",
     main_px=62, sub_px=28, tone="red", icon="chart")
card(CW, CH, *SLOTS[2], 149.16, 150.30, main="2 payouts", sub="back to back", style="serif", accent=True,
     main_px=96, sub_px=32, icon="dollar")
link(SLOTS[0], SLOTS[1], 145.0, 150.25)
link(SLOTS[1], SLOTS[2], 149.0, 150.25)
CARD_DIM.append((141.10, 150.32))
CHING.append(149.38)

# ---------------------------------------------------------------- 2:30 what this is not
_s = TextSeq([L(("signal", "red", 152.92), ("group", "red", 153.30))], 154.36, (OW / 2, 640), sizes=(110, 200))
page(150.40, 154.40, [label("TO BE VERY CLEAR", 150.94, 154.36, y=330),
                      TextSeq([L(("This", "sans", 152.02), ("is", "sans", 152.26), ("not", "sans", 152.42), ("a", "sans", 152.68))],
                              154.36, (OW / 2, 470), sizes=(110, 190)), _s],
     [Stroke(curve(560, 660, 1360, 630, 6), 153.62, 154.36, dur=0.35, colour=WHITE, width=9)])
SIDES.append((156.90, 158.22, side([L(("consistently", "sans", 157.30))], [L(("profitable", "serif", 157.82))], 158.22)))
card(TW + 40, CH, 960, 560, 159.08, 162.55, main="Just a Discord", sub="where you're left on your own", style="serif",
     main_px=88, sub_px=30, tone="red")
strike(960, 560, TW + 40, 161.86, 162.52, colour=WHITE)
CARD_DIM.append((158.30, 162.55))

# ---------------------------------------------------------------- 2:42 who it's for + CTA
over([L(*W_("THIS IS FOR YOU IF", "grey", 162.62, 0.04))], 169.22, y=270, sizes=(90, 90))
card(800, 130, 960, 420, 163.76, 169.22, main="You're willing to put in the work", check=True, align="l", main_px=40)
card(800, 130, 960, 570, 166.42, 169.22, main="You're not here to get rich quick", check=True, align="l", main_px=40)
card(800, 130, 960, 720, 168.32, 169.22, main="You want to be profitable long term", check=True, align="l",
     main_px=40, accent=True)
CARD_DIM.append((162.60, 169.25))
CTA = [TextSeq([L(("Click", "sans", 169.28), ("the", "sans", 169.74), ("link", "sans", 169.86), ("below", "serif", 169.98))],
               171.72, (OW / 2, 800), sizes=(84, 130)),
       TextSeq([L(*W_("FILL OUT A SHORT APPLICATION", "grey", 170.46, 0.06))], 171.72, (OW / 2, 940), sizes=(84, 84),
               stagger=0.02)]
CTA_DIM = (169.20, 171.75)
card(TW, CH, *TWO[0], 172.52, 175.45, main="A quick call", sub="I look at where you're at", style="serif",
     main_px=90, sub_px=30, icon="phone")
card(TW, CH, *TWO[1], 174.46, 175.45, main="Clear yes or no", sub="both answers are fine", style="serif",
     accent=True, main_px=84, sub_px=30, icon="check")
link(TWO[0], TWO[1], 174.3, 175.4, w=TW)
CARD_DIM.append((171.80, 175.45))
_r = TextSeq([L(("Risk-free", "serif", 178.32))], 183.26, (OW / 2, 470), sizes=(110, 230))
page(177.00, 183.30, [label("AND REMEMBER", 177.04, 183.26, y=300), _r,
                      TextSeq([L(("pass", "sans", 179.96), ("$100,000", "sans", 180.48))], 183.26, (OW / 2, 680),
                              sizes=(84, 130)),
                      TextSeq([L(("or", "sans", 181.54), ("every", "serif", 182.22), ("single", "serif", 182.56),
                                 ("cent", "serif", 182.86), ("back", "serif", 183.10))], 183.26, (OW / 2, 820),
                              sizes=(84, 130))], [underline(_r, 178.9, 183.26)])
CTA += [TextSeq([L(("See", "sans", 183.66), ("you", "sans", 183.78), ("on", "serif", 183.88), ("the", "serif", 183.96),
                   ("call", "serif", 184.04))], 186.0, (OW / 2, 840), sizes=(96, 150))]
CTA_DIM = (169.20, 171.75)
END_DIM = (183.30, 186.0)

BGFX = [(a - 0.05, b + 0.1) for a, b, _ in SIDES] + [END_DIM]
FULLSCREEN = [(a, b, "page", i) for i, (a, b, *_) in enumerate(PAGES)]
STROKES = [Stroke(curve(*s_[:4], 6), s_[4], s_[5], dur=0.3, colour=s_[6], width=7) for s_ in STRIKES]
STROKES += [Stroke(curve(x0, y0, x1, y1, 0), t0, t1, dur=0.35, colour=(150, 190, 240), width=4)
            for x0, y0, x1, y1, t0, t1 in LINKS]
POPS = [c[4] for c in CARDS]


def cards_over(fr, t):
    for kw, (w, h), x, y, t0, t1 in CARDS:
        pop_in(fr, ui_card(w, h, **kw), x, y, t, t0, t1, rise=50 if h < 200 else 90)
    for s_ in STROKES:
        s_.draw(fr, t)
    for s_ in UNDER_TEXT:
        s_.draw(fr, t)


SPOT = (-10.0, -9.0)
SPOT_RECT = (20, 430, 380, 870)
LEAKS = sorted({round(x, 2) for a, b, *_ in FULLSCREEN for x in (a, b) if 0.05 < x < 184.0} | {SPLIT[0], SPLIT[1]} |
               set(FLASHES))
TOTAL = to_out(RAW_END)

GOLD = {"strategy", "results", "guarantee", "funded", "confident", "promise", "experience", "payout", "paid", "evals",
        "passing", "account", "theater", "money", "mentorship", "videos", "trusted", "deal", "personally",
        "rules", "decisions", "week", "alone", "guarantee", "year", "college", "clicked", "simple", "emotions",
        "month", "military", "ict", "july", "payouts", "back", "clear", "profitable", "teach", "learn", "work",
        "quick", "application", "call", "yes", "fine", "risk", "cent", "students'", "zero", "gurus", "experience"}
RED_WORDS = {"failed", "blew", "couldn't", "didn't", "guessing", "nothing", "fomo'd", "revenge", "bad", "wipe",
             "hated", "nagging", "left"}
NO_CAPS = ([(a, b) for a, b, _ in SIDES] + [(a, b) for a, b, _, _ in FULLSCREEN] + CARD_DIM + [SPLIT, CTA_DIM,
                                                                                               END_DIM])


def _caption_groups():
    def hidden(t):
        return any(a - 0.05 <= t <= b for a, b in NO_CAPS)

    ws = []
    for w in WORDS:
        txt = w["w"]
        if txt.startswith(",") and ws:       # "$7" + ",000"
            ws[-1]["w"] += txt
            ws[-1]["e"] = w["e"]
            continue
        if txt.startswith("-") and ws:       # step-by-step, one-on-one
            ws[-1]["w"] += txt
            ws[-1]["e"] = w["e"]
            continue
        ws.append(dict(w))
    # 1) clauses: split at . , ? ! , at pauses and where a graphic hides the captions
    clauses, cur = [], []
    for i, w in enumerate(ws):
        if hidden(w["s"] + 0.05):
            if cur:
                clauses.append(cur)
                cur = []
            continue
        cur.append(w)
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        if nxt is None or hidden(nxt["s"] + 0.05) or nxt["s"] - w["e"] > 0.3 or w["w"][-1] in ".,?!":
            clauses.append(cur)
            cur = []
    if cur:
        clauses.append(cur)
    # 2) short clauses joined to the next one inside the same sentence (a comma, not a full stop)
    joined = []
    for c in clauses:
        if joined:
            p = joined[-1]
            same_sentence = p[-1]["w"][-1] == "," and c[0]["s"] - p[-1]["e"] < 0.3
            short = (p[-1]["e"] - p[0]["s"]) < 0.8 or (c[-1]["e"] - c[0]["s"]) < 0.6
            if same_sentence and short and sum(len(x["w"]) + 1 for x in p + c) <= 30:
                joined[-1] = p + c
                continue
        joined.append(c)
    # 3) long clauses cut into balanced pieces (<= 26 characters, >= ~0.8 s each), never ending on a weak word
    WEAK = {"the", "a", "an", "to", "of", "and", "that", "my", "your", "i'm", "is", "in", "on", "for", "at", "their",
            "it", "you", "as", "or", "but", "so", "with", "this", "be", "no", "not", "i", "we", "gonna", "any", "if",
            "prop", "every", "single", "lot", "multiple", "two", "pay"}
    groups = []
    for c in joined:
        chars = sum(len(x["w"]) + 1 for x in c)
        dur = c[-1]["e"] - c[0]["s"]
        k = max(1, math.ceil(chars / 26))
        k = max(k, min(math.ceil(chars / 34), len(c)))
        while k > 1 and dur / k < 0.8 and math.ceil(chars / (k - 1)) <= 34:
            k -= 1
        if k == 1:
            groups.append(c)
            continue
        # balanced split points by characters, nudged off weak words
        cum = np.cumsum([len(x["w"]) + 1 for x in c])
        cuts = []
        for j in range(1, k):
            target = chars * j / k
            i = int(np.argmin(np.abs(cum - target)))
            for d in (0, 1, -1, 2, -2):
                ii = i + d
                if 0 <= ii < len(c) - 1 and c[ii]["w"].strip(".,?!").lower() not in WEAK and \
                        (not cuts or ii > cuts[-1]):
                    i = ii
                    break
            if not cuts or i > cuts[-1]:
                cuts.append(i)
        prev = 0
        for i in cuts:
            groups.append(c[prev:i + 1])
            prev = i + 1
        groups.append(c[prev:])
    out = []
    for gi, g in enumerate(groups):
        t0 = g[0]["s"]
        t1 = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else g[-1]["e"] + 0.4
        t1 = min(t1, g[-1]["e"] + 0.6)
        for a, b in NO_CAPS:
            if t0 < a < t1:
                t1 = a - 0.05
        words = [("I" if x["w"].strip(".,?!") == "i" else x["w"].strip(".,?!")) for x in g]
        if t1 - t0 >= 0.45:   # never flash a caption too short to read ...
            out.append((t0, t1, words))
        elif out and abs(out[-1][1] - t0) < 0.1 and len(" ".join(out[-1][2] + words)) <= 36:
            out[-1] = (out[-1][0], t1, out[-1][2] + words)   # ... fold it into the line before instead
    return out


CAPTIONS = _caption_groups()


@functools.lru_cache(None)
def caption_sprite(words):
    words = list(words)
    gold_i, red = None, False
    for i, w in enumerate(words):
        if w.strip("$").lower() in GOLD or w in GOLD:
            gold_i = i
    for i, w in enumerate(words):
        if w.lower() in RED_WORDS:
            gold_i, red = i, True
    if gold_i is None:
        for i, w in enumerate(words):
            if any(ch.isdigit() for ch in w):
                gold_i = i
    items = []
    x = 0
    for i, w in enumerate(words):
        serif = i == gold_i
        f = font(F_SERIF if serif else F_SANS, 84 if serif else 64)
        items.append((w, serif, f, x))
        x += f.getlength(w) + font(F_SANS, 64).getlength(" ")
    width = int(x) + 120
    im = Image.new("RGBA", (width, 220), (0, 0, 0, 0))
    base = 140
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for w, serif, f, xx in items:
        ImageDraw.Draw(sh).text((60 + xx, base), w, font=f, fill=(0, 0, 0, 255), anchor="ls")
    a = np.array(sh).astype(np.float32)
    a[:, :, 3] = cv2.GaussianBlur(a[:, :, 3], (0, 0), 6) * 0.7
    im.alpha_composite(Image.fromarray(a.astype(np.uint8)))
    for w, serif, f, xx in items:
        if serif:
            gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((60 + xx, base), w, font=f, fill=(250, 172, 48, 255), anchor="ls")
            g = np.array(gl).astype(np.float32)
            g[:, :, 3] = np.clip(cv2.GaussianBlur(g[:, :, 3], (0, 0), 4) * 0.5 + cv2.GaussianBlur(g[:, :, 3], (0, 0), 14)
                                 * 0.45, 0, 255)
            im.alpha_composite(Image.fromarray(g.astype(np.uint8)))
        ImageDraw.Draw(im).text((60 + xx, base), w, font=f,
                                fill=(250, 172, 48, 255) if serif else (246, 244, 242, 255), anchor="ls")
    return pil_to_bgra(im)


@functools.lru_cache(None)
def caption_sprite_c(words):
    spr = caption_sprite(words)
    if not any(w.lower() in RED_WORDS for w in words):
        return spr
    # recolour the accent word from gold to red (gold pixels: R high, B low)
    out = spr.copy()
    b, g_, r = out[:, :, 0].astype(np.int32), out[:, :, 1].astype(np.int32), out[:, :, 2].astype(np.int32)
    gold = (r > 120) & (r - b > 90)
    out[:, :, 1][gold] = (g_[gold] * 0.32).astype(np.uint8)
    out[:, :, 0][gold] = (b[gold] * 0.9 + 40).clip(0, 255).astype(np.uint8)
    return out


def draw_caption(fr, t):
    for t0, t1, words in CAPTIONS:
        t0, t1 = t0 - CAP_LEAD, t1 - CAP_LEAD
        if t0 <= t < t1:
            spr = caption_sprite_c(tuple(words))
            # tiny settle on entry (hard switch, 4-frame rise)
            dy = 10 * (1 - e_out((t - t0) / 0.13))
            if spr.shape[1] > OW * 0.96:
                k = OW * 0.96 / spr.shape[1]
                spr = cv2.resize(spr, (int(spr.shape[1] * k), int(spr.shape[0] * k)), interpolation=cv2.INTER_AREA)
            blend_rgba(fr, spr, OW / 2 - spr.shape[1] / 2, CAP_Y - spr.shape[0] * 140 / 220 + dy, 1.0)
            return True
    return False


def caption_fade_amt(t):
    """bottom dark fade while captions are on."""
    for t0, t1, _ in CAPTIONS:
        if t0 - 0.2 <= t <= t1 + 0.2:
            return 1.0
    return 0.0


# ================================================================== rendering
class Source:
    def __init__(self, t_start):
        t_start = min(t_start, globals().get("BASE_END", 1e9) - 1.0)
        self.i0 = max(0, int(t_start * FPS))
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{self.i0 / FPS:.4f}", "-i", RAW, "-an",
                                   "-vf", f"fps={FPS}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                                  stdout=subprocess.PIPE, bufsize=SW * SH * 3 * 4)
        self.next = self.i0
        self.cache = {}
        self.last = None

    def get(self, t):
        t = min(t, globals().get("BASE_END", 1e9))
        i = max(self.i0, int(round(t * FPS)))
        while self.next <= i:
            buf = self.p.stdout.read(SW * SH * 3)
            if len(buf) < SW * SH * 3:
                break
            self.cache[self.next] = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
            self.next += 1
            for k in [k for k in self.cache if k < self.next - 10]:
                del self.cache[k]
        if i in self.cache:
            self.last = self.cache[i]
        return self.last.copy()


def shot_at(t):
    for s in SHOTS:
        if s[0] <= t < s[1]:
            return s
    return SHOTS[-1]


VCX = {960: 990, 520: 300}   # 9:16: wide shots centre on Jan, the certificate push centres on the certificate


def zoom_at(t):
    """AB staircase zooms: each keyframe eases (in-out) from the previous settled framing, or snaps under a leak."""
    z, cx, cy = 1.0, 960.0, 540.0
    for t0, zt, dur, x, y in ZK:
        if t < t0:
            break
        if dur <= 0:
            z, cx, cy = zt, x, y
            continue
        u = e_io((t - t0) / dur) if t < t0 + dur else 1.0
        z, cx, cy = z + (zt - z) * u, cx + (x - cx) * u, cy + (y - cy) * u
    return z, cx, cy


def crop_params(t):
    z, cx, cy = zoom_at(t)
    ch = SH / z
    cw = ch * OW / OH
    x0 = min(max(cx - cw / 2, 0), SW - cw)
    y0 = min(max(cy - ch / 2, 0), SH - ch)
    return x0, y0, OH / ch


def camera(fr, t):
    x0, y0, s_ = crop_params(t)
    if not VERT and abs(s_ - 1) < 1e-3:
        return fr
    M = np.float32([[s_, 0, -x0 * s_], [0, s_, -y0 * s_]])
    out = cv2.warpAffine(fr, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    if s_ > 1.12:  # light unsharp to offset the upscale
        bl = cv2.GaussianBlur(out, (0, 0), 1.2)
        out = cv2.addWeighted(out, 1.35, bl, -0.35, 0)
    return out


def card_dim(fr, amt):
    if amt <= 0.01:
        return fr
    bg = soft_blur(fr, 12)
    bg = cv2.multiply(cv2.multiply(bg, VIG, scale=1 / 255), VIG, scale=1 / 255)
    bg = bg.astype(np.float32) * 0.45
    return (fr * (1 - amt) + bg * amt).astype(np.uint8)


def head_fx(fr, amt):
    """Ricky's feathered ellipse: background around Jan softly darkened + blurred."""
    if amt <= 0.01:
        return fr
    bg = soft_blur(fr, 9).astype(np.float32) * 0.42
    m = HEAD_MASK + (1 - HEAD_MASK) * (1 - amt)
    return (fr * m + bg * (1 - m)).astype(np.uint8)


def spotlight(fr, t):
    amt = ramp(t, SPOT[0] + 0.2, SPOT[1], 0.5, 0.3)
    if amt <= 0.01:
        return fr
    # the spot follows the camera (rect is in source coords, camera push is applied before)
    x0, y0, z = crop_params(t)
    rx0, ry0, rx1, ry1 = [(v - o) * z for v, o in zip(SPOT_RECT, (x0, y0, x0, y0))]
    m = np.zeros((OH, OW), np.float32)
    cv2.rectangle(m, (int(rx0), int(ry0)), (int(rx1), int(ry1)), 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), 30)[:, :, None]
    bg = soft_blur(fr, 9).astype(np.float32) * 0.34
    out = fr * m + bg * (1 - m)
    out = fr * (1 - amt) + out * amt
    # gold underline under the certificate
    o = out.astype(np.uint8)
    Stroke(curve(rx0 + 20, ry1 + 18, rx1 - 20, ry1 + 10, 8), SPOT[0] + 0.9, SPOT[1], dur=0.6, width=6).draw(o, t)
    return o


BASE_END = 184.28   # last frame of the clean cut; held for the sign-off


def footage_frame(src, t):
    fr = camera(src.get(min(t, BASE_END)), t)
    if SPOT[0] <= t <= SPOT[1]:
        fr = spotlight(fr, t)
    amt = max([ramp(t, a, b, 0.35, 0.3) for a, b in CARD_DIM + DIM_KEEP] + [0.0])
    fr = card_dim(fr, amt)
    amt = max([ramp(t, a, b, 0.35, 0.3) for a, b in BGFX + PHOTO_DIM] + [ramp(t, *CTA_DIM, 0.6, 0.3) * 0.8, 0.0])
    amt = max(amt, ramp(t, END_DIM[0], END_DIM[1], 0.5, 0.01) * 0.8)
    fr = head_fx(fr, amt)
    cf = caption_fade_amt(t)
    if cf > 0:
        fr = (fr * (1 - BOTTOM * 0.55 * cf)).astype(np.uint8)
    for a, b, seqs in SIDES:
        if a - 0.1 <= t <= b + 0.1:
            for s in seqs:
                s.draw(fr, t)
    cards_over(fr, t)
    for s in CTA:
        s.draw(fr, t)
    draw_caption(fr, t)
    return fr


def split_frame(src, t, base):
    """AB's offer split screen: Jan slides to the left half, a grid panel with the list slides in from the right."""
    a, b = SPLIT
    p = e_expo((t - a) / 0.7) if t < b - 0.6 else 1 - e_io((t - (b - 0.6)) / 0.6)
    if p <= 0.001:
        return base
    if VERT:
        ph = 1000
        py = int(round(OH - ph * p))
        out = base.copy()
        out[py:] = grid_bg(t)[OH - ph:OH - ph + (OH - py)]
        seam = np.exp(-((np.arange(40) - 20) / 6.0) ** 2)[:, None, None] * np.array((40, 120, 230), np.float32)
        y0 = max(0, py - 20)
        hh = min(40, OH - y0)
        roi = out[y0:y0 + hh].astype(np.float32)
        out[y0:y0 + hh] = np.clip(roi + seam[:hh] * 0.5 * p, 0, 255).astype(np.uint8)
        if p > 0.98:
            OFFER_TITLE.draw(out, t)
            for i, (txt, t0) in enumerate(OFFER):
                pop_in(out, ui_card(960, 104, txt, check=True, align="l", main_px=36, accent=(i == 0)), 540,
                       1150 + i * 124, t, t0, b - 0.3, dur=0.6, rise=40)
        return out
    shift = int(round(510 * p))
    out = np.zeros_like(base)
    out[:, :OW - shift] = base[:, shift:]
    px = int(round(OW - 960 * p))
    panel = grid_bg(t, 960, 480)
    out[:, px:] = panel[:, :OW - px]
    # soft glowing seam
    seam = np.zeros((OH, 40, 3), np.float32)
    seam[:] = (40, 120, 230)
    gl = np.exp(-((np.arange(40) - 20) / 6.0) ** 2)[None, :, None]
    x0 = max(0, px - 20)
    w = min(40, OW - x0)
    if w > 0:
        roi = out[:, x0:x0 + w].astype(np.float32)
        out[:, x0:x0 + w] = np.clip(roi + seam[:, :w] * gl[:, :w] * 0.5 * p, 0, 255).astype(np.uint8)
    if p > 0.98:
        OFFER_TITLE.draw(out, t)
        for i, (txt, t0) in enumerate(OFFER):
            pop_in(out, ui_card(800, 104, txt, check=True, align="l", main_px=36, accent=(i == 0)), 1440,
                   300 + i * 124, t, t0, b - 0.3, dur=0.6, rise=40)
    return out


def page_frame(i, t):
    t0, t1, texts, strokes, tone, under = PAGES[i]
    fr = grid_bg(t, red=(tone == "red"))
    for s_ in under:
        s_.draw(fr, t)
    for s_ in texts:
        s_.draw(fr, t)
    for s_ in strokes:
        s_.draw(fr, t)
    return fr


def montage_frame(t):
    fr = grid_bg(t)
    for name, cx, cy, w, rz, t0 in MONT_IMGS:
        pop_in(fr, photo_card(name, w, 380, rz=rz), cx, cy, t, t0, MONTAGE[1] + 0.2, dur=0.6, rise=60)
    MONT_LABEL.draw(fr, t)
    return fr


def zoom_frame(fr, s, blur=0.0):
    if abs(s - 1) > 1e-3:
        M = np.float32([[s, 0, OW / 2 * (1 - s)], [0, s, OH / 2 * (1 - s)]])
        fr = cv2.warpAffine(fr, M, (OW, OH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if blur > 0.5:
        fr = soft_blur(fr, blur)
    return fr


TD = 0.40


def trans(A, B, u):
    w = e_sm(u)
    a = zoom_frame(A, 1 + 0.08 * e_io(u), 18 * math.sin(math.pi * clamp(u)) ** 1.5)
    b = zoom_frame(B, 0.95 + 0.05 * e_out(u), 18 * math.sin(math.pi * clamp(u)) ** 1.5)
    return cv2.addWeighted(a, 1 - w, b, w, 0)


def full_frame(kind, i, t):
    return page_frame(i, t) if kind == "page" else montage_frame(t)


@functools.lru_cache(None)
def _leak_bands(seed):
    r = np.random.default_rng(seed)
    h, w = OH // 4, OW // 4
    yy = np.mgrid[0:h, 0:w][0].astype(np.float32)
    bands = (1 + 0.35 * np.sin(yy / (h * r.uniform(0.07, 0.13)) + r.uniform(0, 6))
             + 0.2 * np.sin(yy / (h * 0.37) + r.uniform(0, 6)))
    X = np.mgrid[0:h, 0:w][1].astype(np.float32) / w
    return bands, (X if seed % 2 == 0 else 1 - X)


LEAK_LOW = np.array((20, 45, 150), np.float32)     # BGR: red-brown
LEAK_MID = np.array((35, 135, 255), np.float32)    # orange
LEAK_HI = np.array((205, 240, 255), np.float32)    # pale yellow / near white


def light_leak(fr, u, seed):
    """AB's warm film burn: blooms from one side, peaks near-white at the cut (u = 0 s), glow lingers ~0.3 s."""
    a = 0.8 * math.exp(-(u / 0.11) ** 2) + 0.4 * math.exp(-((u - 0.06) / 0.26) ** 2)
    if a < 0.01:
        return fr
    bands, X = _leak_bands(seed)
    x0 = 0.12 + 0.55 * clamp((u + 0.3) / 0.65)
    d = X - x0
    I = np.clip((np.exp(-(d / 0.2) ** 2) * bands * 0.85 + np.exp(-(d / 0.55) ** 2) * 0.32) * a, 0, 1.25)
    lo = np.clip(I / 0.5, 0, 1)[:, :, None]
    hi = np.clip((I - 0.5) / 0.7, 0, 1)[:, :, None]
    col = LEAK_LOW + (LEAK_MID - LEAK_LOW) * lo
    col = col + (LEAK_HI - col) * hi
    lk = cv2.resize(col * np.clip(I, 0, 1)[:, :, None], (OW, OH), interpolation=cv2.INTER_LINEAR)
    f = fr.astype(np.float32)
    return np.clip(255 - (255 - f) * (255 - lk) / 255, 0, 255).astype(np.uint8)   # screen blend


def frame_at(tau, src):
    t = to_src(tau)
    fr = None
    for a, b, kind, i in FULLSCREEN:
        if a <= t < b:
            src.get(t)
            fr = full_frame(kind, i, t)
            break
    if fr is None:
        fr = footage_frame(src, t)
        if SPLIT[0] <= t <= SPLIT[1]:
            fr = split_frame(src, t, fr)
    for k, tl in enumerate(LEAKS):
        u = tau - to_out(tl)
        if -0.35 < u < 0.6:
            fr = light_leak(fr, u, k)
    return fr


def encoder(out):
    return subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OW}x{OH}", "-r", str(FPS),
         "-i", "-", "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-tune", "film",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-x264-params", "keyint=60", out], stdin=subprocess.PIPE)


def render_video(t0, t1, out):
    src = Source(to_src(t0) - 0.5)
    enc = encoder(out)
    n0 = int(round(t0 * FPS))
    n1 = int(round(min(t1, TOTAL) * FPS))
    for n in range(n0, n1):
        tau = n / FPS
        fr = frame_at(tau, src)
        if tau > TOTAL - 0.9:
            fr = (fr * clamp((TOTAL - tau) / 0.9)).astype(np.uint8)
        enc.stdin.write(np.ascontiguousarray(fr).tobytes())
        if n % 150 == 0:
            print(f"{out}: {tau:7.1f}/{t1:.1f}", flush=True)
    enc.stdin.close()
    enc.wait()
    src.p.kill()


# ================================================================== AUDIO
def load(path, start=0.0, dur=None, filt=None):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start)]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-i", str(path), "-vn"]
    if filt:
        cmd += ["-af", filt]
    cmd += ["-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    a = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return a.reshape(-1, 2).copy()


INTRO_BOOST = 9.0   # dB the song is raised at the very start (still well under his voice)
SONG_START = 5.54   # "Me and the Devil": the beat-only intro is skipped, the video opens as the symphony comes in


def db(x):
    return 10 ** (x / 20)


RNG = np.random.default_rng(7)


def onepole(x, fc):
    y = np.zeros_like(x)
    a = np.exp(-2 * np.pi * fc / SR)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def sfx_whoosh(d=0.7, lo=250, hi=5500, peak=0.55):
    n = int(d * SR)
    t = np.linspace(0, 1, n)
    env = np.where(t < peak, (t / peak) ** 2.2, ((1 - t) / (1 - peak)) ** 1.6)
    fc = lo + (hi - lo) * env
    lp = onepole(RNG.standard_normal(n), fc)
    hp = lp - onepole(lp, np.full(n, 160.0))
    s = hp * env
    s /= np.abs(s).max() + 1e-9
    pan = np.clip(t * 1.4 - 0.2, 0, 1)
    return np.stack([s * np.cos(pan * np.pi / 2) * 1.2, s * np.sin(pan * np.pi / 2) * 1.2], 1).astype(np.float32)


def sfx_pop(f=740):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(f * (1 + 0.6 * np.exp(-t * 60))) / SR
    s = np.sin(ph) * np.exp(-t * 34) + RNG.standard_normal(n) * np.exp(-t * 300) * 0.25
    s /= np.abs(s).max()
    return np.stack([s, s], 1).astype(np.float32)


def sfx_tick():
    n = int(0.025 * SR)
    t = np.arange(n) / SR
    s = RNG.standard_normal(n) * np.exp(-t * 400)
    s = s - onepole(s, np.full(n, 3000.0))
    s /= np.abs(s).max()
    return np.stack([s, s], 1).astype(np.float32)


def sfx_ching():
    t = np.arange(int(SR * 1.6)) / SR
    bell = sum(np.sin(2 * np.pi * f * t) * g * np.exp(-t * dd)
               for f, g, dd in ((2093, 1, 3.0), (2637, .7, 3.5), (3136, .5, 4), (4186, .35, 5), (5274, .2, 6)))
    s = bell * 0.4 + RNG.standard_normal(len(t)) * np.exp(-t * 60) * 0.5
    s /= np.abs(s).max()
    return np.stack([s, s], 1).astype(np.float32)


def sfx_scratch():
    """quick marker strike for the struck-out cards."""
    n = int(0.22 * SR)
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t) ** 0.6
    s = onepole(RNG.standard_normal(n), np.full(n, 3800.0)) * env
    s = s - onepole(s, np.full(n, 900.0))
    s /= np.abs(s).max()
    return np.stack([s, s], 1).astype(np.float32)


def sfx_events():
    """(raw time, sound, dB under the voice level): soft, like the thank-you video."""
    wh, pop, tick, ching, scr = sfx_whoosh(0.55, 300, 6500), sfx_pop(), sfx_tick(), sfx_ching(), sfx_scratch()
    ev = [(tl - 0.25, wh, -24) for tl in LEAKS]
    ev += [(t0, pop, -22) for t0 in POPS]
    ev += [(x[5], pop, -23) for x in MONT_IMGS]
    ev += [(s_[4], scr, -22) for s_ in STRIKES]
    for a, b, seqs in SIDES:
        ev.append((("abs", seqs[0].chars[0]["t0"]), tick, -27))
        ev.append((("abs", seqs[1].chars[0]["t0"]), tick, -27))
    ev += [(t0, pop, -23) for _, t0 in OFFER]
    ev += [(t0, ching, -22) for t0 in CHING]
    return ev


def render_audio(music_path, out_wav):
    total = TOTAL + 0.5
    voice = load(RAW, filt="highpass=f=75,acompressor=threshold=-21dB:ratio=3:attack=8:release=120:makeup=3")
    # cut the pauses (6 ms crossfades)
    keep, prev = [], 0.0
    for a, b in CUTS:
        keep.append((prev, a))
        prev = b
    keep.append((prev, RAW_END))
    fade = int(0.006 * SR)
    v = np.zeros((0, 2), np.float32)
    for a, b in keep:
        s = voice[int(a * SR):int(b * SR)]
        if len(v) and len(s) > fade:
            r = np.linspace(0, 1, fade)[:, None]
            v = np.concatenate([v[:-fade], v[-fade:] * (1 - r) + s[:fade] * r, s[fade:]])
        else:
            v = np.concatenate([v, s])
    n = int(total * SR)
    v = np.pad(v, ((0, max(0, n - len(v))), (0, 0)))[:n]
    # voice level while talking
    env = np.sqrt(np.convolve((v ** 2).mean(1), np.ones(2400) / 2400, "same"))
    v_rms = float(np.percentile(env[env > 1e-4], 70))
    # music: the uploaded song from 0:00, under the voice, ducked a little while he talks
    mus = load(music_path, start=SONG_START) if music_path != "none" else np.zeros((n, 2), np.float32)
    f10 = int(0.01 * SR)
    mus[:f10] *= np.linspace(0, 1, f10)[:, None]
    while len(mus) < n:
        mus = np.concatenate([mus, mus])
    mus = mus[:n]
    m_rms = float(np.sqrt((mus ** 2).mean())) or 1.0
    mus *= v_rms / m_rms * db(-16)
    duck = np.clip(env / (v_rms + 1e-9), 0, 1)
    duck = np.convolve(duck, np.ones(SR // 5) / (SR // 5), "same")
    mus *= (1 - 0.30 * duck)[:, None]
    tt = np.arange(n) / SR
    g = np.clip((total - 0.4 - tt) / 2.5, 0, 1)
    # louder opening so the song grabs attention, eased back down to the bed
    b0, b1 = to_out(6.8), to_out(8.6)    # louder through "thank you for applying", easing down on the 90% card
    xb = np.clip((tt - b0) / (b1 - b0), 0, 1)
    boost_db = INTRO_BOOST * (1 - xb * xb * (3 - 2 * xb))
    g *= 10 ** (boost_db / 20)
    mus *= g[:, None]
    for name, (x0, x1) in (("hook 0-5.5s", (0.0, 5.5)), ("body 20-60s", (20.0, 60.0))):
        i0, i1 = int(x0 * SR), int(x1 * SR)
        vr = np.sqrt((v[i0:i1] ** 2).mean()) + 1e-9
        mr = np.sqrt((mus[i0:i1] ** 2).mean()) + 1e-9
        print(f"music vs voice, {name}: {20 * np.log10(mr / vr):+.1f} dB")
    fx = np.zeros((n, 2), np.float32)
    for t_raw, snd, lvl in sfx_events():
        t_abs = t_raw[1] if isinstance(t_raw, tuple) else rt(t_raw)
        i = int(to_out(t_abs) * SR)
        if i < 0 or i >= n:
            continue
        j = min(n, i + len(snd))
        fx[i:j] += snd[:j - i] * v_rms * 3.0 * db(lvl)
    mix = v + mus + fx
    tmp = str(out_wav) + ".raw.wav"
    import wave
    with wave.open(tmp, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((np.clip(mix / max(1e-6, np.abs(mix).max()) * 0.9, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", "loudnorm=I=-14:TP=-1.2:LRA=11", "-ar", str(SR),
                    "-c:a", "pcm_s16le", str(out_wav)], check=True)
    Path(tmp).unlink()


# ================================================================== entry
if __name__ == "__main__":
    if MODE == "info":
        print(f"cuts: {len(CUTS)}, removed {sum(b - a for a, b in CUTS):.2f}s, total {TOTAL:.2f}s")
        for c in CAPTIONS:
            print(f"{c[0]:7.2f}-{c[1]:7.2f} {' '.join(c[2])}")
    elif MODE == "frames":
        outdir = Path(sys.argv[4])
        outdir.mkdir(parents=True, exist_ok=True)
        for s in sys.argv[5:]:
            tau = to_out(float(s[1:])) if s.startswith("r") else float(s)
            src = Source(to_src(tau) - 0.2)
            cv2.imwrite(str(outdir / f"f_{tau:07.2f}.jpg"), frame_at(tau, src), [cv2.IMWRITE_JPEG_QUALITY, 90])
            src.p.kill()
    elif MODE == "video":
        render_video(float(sys.argv[4]), float(sys.argv[5]), sys.argv[6])
    elif MODE == "audio":
        render_audio(sys.argv[4], sys.argv[5])
