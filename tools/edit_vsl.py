"""Jan's VSL edit: AB Nasdaq's VSL structure, Ricky's (rickyvideoediting) design system.

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
OW, OH = 1920, 1080
K = 1.0
FPS = 30
SR = 48000
RAW_END = 155.30

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
_e = np.sqrt(((_xx - 990) / 430.0) ** 2 + ((_yy - 560) / 640.0) ** 2)
HEAD_MASK = np.clip((1.35 - _e) / 0.55, 0, 1).astype(np.float32)[:, :, None]
# dark fade along the bottom for captions
BOTTOM = (np.clip((_yy[:, :1] - OH * 0.62) / (OH * 0.38), 0, 1).astype(np.float32) ** 1.4)[:, :, None]
del _yy, _xx, _r, _e


# ------------------------------------------------------------------ grid page (Ricky's STEP page)
def _make_page():
    m = 240
    H, W = OH + m, OW + m
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.empty((H, W, 3), np.float32)
    img[:] = (7, 6, 6)
    r1 = np.sqrt(((xx - W * 0.5) / (W * 0.62)) ** 2 + ((yy - H * 1.02) / (H * 0.80)) ** 2)
    g1 = np.clip(1 - r1, 0, 1) ** 1.7
    r2 = np.sqrt(((xx - W * 0.10) / (W * 0.42)) ** 2 + ((yy + H * 0.05) / (H * 0.55)) ** 2)
    g2 = np.clip(1 - r2, 0, 1) ** 2.0
    orange = np.array((18, 88, 220), np.float32)
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


def grid_bg(t, w=OW, x_off=0):
    ox = int((t * 7) % GSTEP)
    return GRID[120:120 + OH, 120 - ox + x_off:120 - ox + x_off + w].copy()


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
    elif kind == "brain":
        d.ellipse((S4 * .12, S4 * .2, S4 * .6, S4 * .78), outline=255, width=lw)
        d.ellipse((S4 * .4, S4 * .2, S4 * .88, S4 * .78), outline=255, width=lw)
    return cv2.resize(np.array(im), (size, size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def _frame_layers(w, h, accent, r):
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
                shadow=shadow, accent=accent)


def _compose(L, body_rgb, extra=None):
    full, outside = L["full"], 1 - L["full"]
    rgbf = np.zeros((L["H"], L["W"], 3), np.float32)
    a = np.zeros((L["H"], L["W"]), np.float32)

    def over(col, al):
        nonlocal rgbf, a
        al3 = al[:, :, None]
        rgbf = rgbf * (1 - al3) + col * al3
        a = a + al * (1 - a)

    rimcol = np.array((255, 156, 64), np.float32)
    over(np.zeros(3, np.float32), L["shadow"])
    over(rimcol, L["glow_w"] * outside * (0.42 if L["accent"] else 0.30))
    over(rimcol, L["glow_t"] * outside * (0.75 if L["accent"] else 0.55))
    over(body_rgb, full * 0.97)
    if extra is not None:
        over(*extra)
    over(np.array((255, 196, 140), np.float32), L["rim_i"])
    return rgbf, a


@functools.lru_cache(None)
def ui_card(w, h, main="", sub="", style="sans", icon=None, accent=False, check=False, main_px=0, align="c",
            sub_px=0):
    """Ricky's card: rounded rect, orange -> black gradient, faded grid inside, glowing orange rim, faded icon."""
    r = int(min(56, h * 0.28))
    L = _frame_layers(w, h, accent, r)
    g, W, H, XX, YY, u, d = L["g"], L["W"], L["H"], L["XX"], L["YY"], L["u"], L["d"]
    warm = np.clip(1 - d * 1.25, 0, 1) ** 1.5
    orange = np.array((232, 104, 24), np.float32)
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
        col = gold if (serif and accent) else (246, 244, 242, 255)
        cy = g + h * (0.42 if sub else 0.5)
        anchor = "mm" if align == "c" else "lm"
        draw_text_pil(im, (g + w / 2 if align == "c" else x, cy), main, path, px, col, anchor, glow=serif and accent)
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
                 stagger=0.035, dur=0.5, ry=0.0, rz=0.0, shadow=0.55):
        self.t_out, self.stagger, self.dur = t_out, stagger, dur
        self.ry, self.rz, self.shadow = ry, rz, shadow
        self.chars = []
        sans_px, serif_px = sizes
        heights, layouts = [], []
        for line in lines:
            x, items, lh = 0.0, [], 0
            for wi, (word, style, t0) in enumerate(line):
                t0 = rt(t0) - TEXT_LEAD
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


# ================================================================== THE EDIT (raw-video seconds)
# ---- camera: (t0, t1, z0, z1, cx, cy). hard cut at every t0 (AB: a new framing every 3-5 s)
FACE = (990, 300)
WIDE = (960, 540)
CLOSE = (990, 432)
SHOTS = [
    (0.00, 2.38, 1.08, 1.14, 990, 470),       # hook: a little closer, slow push, side text
    (2.38, 6.00, 1.02, 1.06, *WIDE),          # $7,000 card over the dimmed shot
    (6.00, 7.40, 1.22, 1.25, *CLOSE),         # so I stopped trading myself
    (7.40, 11.00, 1.00, 1.00, *WIDE),         # side text: 2.5 years / an algorithm
    (11.00, 14.10, 1.20, 1.27, *CLOSE),       # in the next two minutes
    (14.10, 16.40, 1.00, 1.00, *WIDE),        # (page)
    (16.40, 18.00, 1.00, 1.00, *WIDE),        # side: trade their capital
    (18.00, 27.20, 1.00, 1.06, *WIDE),        # three cards: fee / pass / fail
    (27.20, 31.00, 1.22, 1.28, *CLOSE),       # sounds pretty simple ... (page 9/10)
    (31.00, 32.48, 1.04, 1.08, *WIDE),        # not because their strategy is bad
    (32.48, 35.50, 1.24, 1.20, *CLOSE),       # that one trade
    (35.50, 41.36, 1.00, 1.05, *WIDE),        # cards: a loss / go bigger / breached
    (41.36, 43.56, 1.00, 1.00, *WIDE),        # side: being human
    (43.56, 49.12, 1.02, 1.07, *WIDE),        # fear / greed / need to be right -> struck out
    (49.12, 50.62, 1.22, 1.26, *CLOSE),       # the hard way
    (50.62, 54.48, 1.00, 1.00, *WIDE),        # (page 2020)
    (54.48, 58.70, 1.00, 1.07, *WIDE),        # wanted to automate
    (58.70, 61.60, 1.25, 1.20, *CLOSE),       # AI back then
    (61.60, 65.80, 1.00, 1.04, *WIDE),        # developer teams (photo)
    (65.80, 66.65, 1.30, 1.30, *CLOSE),       # punch: we failed
    (66.65, 67.65, 1.00, 1.00, *WIDE),        # we had to build again
    (67.65, 68.36, 1.32, 1.32, *CLOSE),       # punch: we failed again
    (68.36, 69.45, 1.00, 1.00, *WIDE),
    (69.45, 73.60, 1.18, 1.27, *CLOSE),       # multiple years ... running today
    (73.60, 78.05, 1.00, 1.06, *WIDE),        # what I figured out (page: I was)
    (78.05, 81.00, 1.00, 1.00, *WIDE),        # side: out of the equation
    (81.00, 88.75, 1.02, 1.08, *WIDE),        # cards: fixed rules / no setup / some weeks
    (88.75, 90.30, 1.22, 1.25, *CLOSE),       # that's the whole point
    (90.30, 97.05, 1.00, 1.05, *WIDE),        # struck-out list
    (97.05, 100.00, 1.00, 1.00, *WIDE),       # photos: runs while you're at work
    (100.00, 103.40, 1.00, 1.22, 520, 640),   # push toward his FTMO certificate
    (103.40, 105.10, 1.02, 1.05, *WIDE),      # check cards: passed / payouts
    (105.10, 107.75, 1.20, 1.26, *CLOSE),     # completely honest
    (107.75, 111.50, 1.00, 1.00, *WIDE),      # side: holy grail / a bad month
    (111.50, 114.35, 1.22, 1.28, *CLOSE),     # no single system
    (114.35, 119.50, 1.00, 1.07, *WIDE),      # if somebody is telling you
    (119.50, 120.68, 1.34, 1.34, *CLOSE),     # punch: they're simply lying to you
    (120.68, 125.70, 1.02, 1.06, *WIDE),      # not the only one (montage)
    (125.70, 128.20, 1.00, 1.00, *WIDE),      # side: get rich quick
    (128.20, 131.40, 1.20, 1.26, *CLOSE),     # if you know trading can work
    (131.40, 134.55, 1.00, 1.06, *WIDE),
    (134.55, 135.45, 1.00, 1.00, *WIDE),      # side: for you
    (135.45, 150.80, 1.00, 1.00, *WIDE),      # split screen offer
    (150.80, 156.00, 1.00, 1.08, *WIDE),      # CTA
]

# ---- text beside his head (white words left, gold serif right): (t_in, t_out, left_lines, right_lines)
SL, SR_ = 820, 1170   # right edge of the left text / left edge of the gold text


def side(left, right, t_out, y=300, sizes=(92, 150), sl=SL, sr=SR_):
    """the gold right side is sized so it is never much wider than the white left side."""
    def width(lines, path, px):
        f = font(path, px)
        return max(f.getlength(" ".join(w for w, _, _ in ln)) for ln in lines)
    sans_px, serif_px = sizes
    lw = width(left, F_SANS, sans_px)
    while serif_px > 96 and width(right, F_SERIF, serif_px) > 1.12 * lw:
        serif_px -= 2
    return [TextSeq(left, t_out, (sl, y), sizes=(sans_px, serif_px), align="r", ry=-12, rz=-1.5),
            TextSeq(right, t_out, (sr, y + 10), sizes=(sans_px, serif_px), align="l", ry=14, rz=3, stagger=0.045)]


SIDES = [
    (0.00, 2.32, side([L(("I", "sans", 0.0), ("failed", "sans", 0.06))],
                      [L(("10", "serif", 0.34), ("FTMO", "serif", 0.54))], 2.32, y=290, sizes=(100, 120),
                      sl=770, sr=1165)),
    (7.46, 10.92, side([L(("2.5", "sans", 7.92), ("years", "sans", 8.38)), L(("building", "sans", 8.66))],
                       [L(("an", "serif", 9.04)), L(("algorithm", "serif", 9.22))], 10.92, sizes=(88, 140))),
    (16.42, 17.98, side([L(("trade", "sans", 17.10), ("their", "sans", 17.28))],
                        [L(("capital", "serif", 17.44))], 17.98)),
    (41.38, 43.52, side([L(("not", "sans", 41.74), ("a", "sans", 41.86)), L(("skill", "sans", 41.98),
                         ("problem", "sans", 42.16))], [L(("being", "serif", 42.84)), L(("human", "serif", 43.0))],
                        43.52, sizes=(88, 140))),
    (79.10, 80.95, side([L(("took", "sans", 79.50), ("myself", "sans", 79.82))],
                        [L(("out", "serif", 80.10), ("of", "serif", 80.32), ("the", "serif", 80.42)),
                         L(("equation", "serif", 80.52))], 80.95, sizes=(92, 120))),
    (107.78, 109.50, side([L(("not", "sans", 107.98), ("some", "sans", 108.06))],
                          [L(("holy", "serif", 108.24)), L(("grail", "serif", 108.46))], 109.50, sizes=(92, 140))),
    (109.70, 111.45, side([L(("October", "sans", 109.74)), L(("was", "sans", 110.72))],
                          [L(("a", "serif", 110.86), ("bad", "serif", 110.96)), L(("month", "serif", 111.12))],
                          111.45, sizes=(92, 140))),
    (125.74, 128.10, side([L(("get", "sans", 126.44), ("rich", "sans", 126.56)), L(("quick?", "sans", 126.74))],
                          [L(("this", "serif", 127.48), ("isn't", "serif", 127.60)), L(("it", "serif", 127.86))],
                          128.10, sizes=(92, 140))),
    (134.58, 135.42, side([L(("this", "sans", 134.70), ("is", "sans", 134.88))],
                          [L(("for", "serif", 134.98), ("you", "serif", 135.06))], 135.42)),
]
BGFX = [(a - 0.05, b + 0.1) for a, b, _ in SIDES]   # soft ellipse darken while side text is up

# ---- full-screen pages on the grid (t_in, t_out, texts, strokes)
PAGES = []


def page(t0, t1, texts, strokes=()):
    PAGES.append((t0, t1, texts, list(strokes)))


_p = TextSeq([L(("THE", "grey", 14.15), ("QUICK", "grey", 14.2), ("VERSION", "grey", 14.25))], 16.36,
             (OW / 2, 380), sizes=(96, 96), stagger=0.03)
_q = TextSeq([L(("How", "sans", 14.42), ("prop", "sans", 14.54), ("firms", "sans", 14.66), ("work", "serif", 15.42))],
             16.36, (OW / 2, 540), sizes=(110, 190))
page(14.10, 16.40, [_p, _q], [underline(_q, 15.75, 16.36)])

_a = TextSeq([L(("9", "serif", 29.32), ("out", "serif", 29.50), ("of", "serif", 29.70), ("10", "serif", 29.80))],
             30.98, (OW / 2, 470), sizes=(110, 250))
_b = TextSeq([L(("traders", "sans", 29.96), ("fail", "sans", 30.26))], 30.98, (OW / 2, 700), sizes=(110, 190))
page(28.82, 31.00, [_a, _b])

_a = TextSeq([L(("TRADING", "grey", 51.92), ("MANUALLY", "grey", 51.98))], 54.44, (OW / 2, 330), sizes=(96, 96),
             stagger=0.03)
_b = TextSeq([L(("2020", "serif", 50.76))], 54.44, (OW / 2, 500), sizes=(110, 260), stagger=0.06)
_c = TextSeq([L(("loss", "sans", 53.28), ("after", "sans", 53.66), ("loss", "sans", 53.96))], 54.44, (OW / 2, 730),
             sizes=(100, 150))
page(50.62, 54.48, [_a, _b, _c])

_a = TextSeq([L(("The", "sans", 75.96), ("strategy", "sans", 76.22), ("wasn't", "sans", 76.54), ("the", "sans", 76.84),
                ("problem.", "sans", 76.94))], 78.0, (OW / 2, 430), sizes=(96, 150))
_b = TextSeq([L(("I", "serif", 77.48), ("was.", "serif", 77.62))], 78.0, (OW / 2, 640), sizes=(110, 260))
page(75.90, 78.05, [_a, _b], [underline(_b, 77.95, 78.0)])

MONTAGE = (122.10, 125.66)
MONT_IMGS = [  # (file, centre x, centre y, width, rotation, pop time)
    ("member2.jpg", 330, 300, 560, -4, 122.18),
    ("member6.jpg", 960, 280, 560, 3, 122.46),
    ("member9.jpg", 1590, 300, 520, -3, 122.74),
    ("member18.jpg", 380, 760, 560, 3, 123.02),
    ("IMG_0639.jpg", 960, 640, 520, -2, 123.30),
    ("member19.jpg", 1560, 760, 560, 4, 123.58),
    ("member7.jpg", 620, 520, 520, -5, 123.86),
    ("member16.jpg", 1320, 500, 540, 2, 124.14),
    ("member17.jpg", 960, 860, 500, -3, 124.42),
    ("member11.jpg", 1700, 560, 460, -2, 124.70),
]
MONT_LABEL = TextSeq([L(("MEMBERS", "grey", 122.12), ("RUNNING", "grey", 122.16), ("IT", "grey", 122.2),
                        ("RIGHT", "grey", 122.24), ("NOW", "grey", 122.28))], 125.6, (OW / 2, 60), sizes=(80, 80),
                     stagger=0.02)

FULLSCREEN = [(a, b, "page", i) for i, (a, b, _, _) in enumerate(PAGES)] + [(MONTAGE[0], MONTAGE[1], "montage", 0)]

# ---- cards / photos over the (dimmed) footage
CARD_DIM = [(2.70, 5.95), (18.00, 27.15), (35.50, 41.36), (43.56, 49.10), (81.90, 88.75), (90.30, 97.00),
            (103.40, 105.10)]
PHOTO_DIM = [(62.70, 65.75), (97.10, 100.00)]


def count_7000(t):
    if t < rt(3.30):
        return "$0"
    v = int(round(7000 * e_out((t - rt(3.30)) / 0.55) / 10) * 10)
    return f"${v:,}"


STRIKES = [  # (x0, y0, x1, y1, t0, t_out, colour)
    (275, 545, 645, 525, 48.32, 49.08, RED), (775, 545, 1145, 525, 48.50, 49.08, RED),
    (1275, 545, 1645, 525, 48.76, 49.08, RED),
    (275, 545, 645, 525, 91.00, 96.98, RED), (775, 545, 1145, 525, 92.70, 96.98, RED),
    (1275, 545, 1645, 525, 94.60, 96.98, RED),
]
STROKES = [Stroke(curve(*s[:4], 6), s[4], s[5], dur=0.3, colour=s[6], width=7) for s in STRIKES]
LINKS = [  # small connectors between cards in a row
    (667, 540, 753, 540, 19.95, 26.95), (1167, 540, 1253, 540, 22.30, 26.95),
    (667, 540, 753, 540, 36.55, 41.2), (1167, 540, 1253, 540, 39.30, 41.2),
    (667, 540, 753, 540, 84.30, 88.6), (1167, 540, 1253, 540, 85.90, 88.6),
]
STROKES += [Stroke(curve(x0, y0, x1, y1, 0), t0, t1, dur=0.35, colour=(150, 190, 240), width=4)
            for x0, y0, x1, y1, t0, t1 in LINKS]

UNDER_TEXT = [
    TextSeq([L(("not", "sans", 26.16), ("your", "sans", 26.34), ("own", "sans", 26.46), ("capital", "serif", 26.60))],
            27.05, (OW / 2, 800), sizes=(64, 100)),
    TextSeq([L(("an", "sans", 47.5), ("algorithm", "sans", 47.6), ("doesn't", "serif", 47.94), ("feel", "serif", 48.32),
               ("it", "serif", 48.76))], 49.0, (OW / 2, 800), sizes=(64, 100)),
    TextSeq([L(("it", "sans", 88.80), ("just", "sans", 88.9), ("doesn't", "sans", 89.0), ("trade", "serif", 89.1))],
            88.7, (OW / 2, 800), sizes=(64, 100)),
]


def cards_over(fr, t):
    """all cards/photos drawn over the footage."""
    y = 540
    # hook: $7,000 lost
    if 2.7 <= t <= 5.95:
        pop_in(fr, ui_card(620, 400, count_7000(t), "lost before trading paid me a cent", style="serif", accent=True,
                           icon="down", main_px=150, sub_px=30), 960, y, t, 2.82, 5.95)
    # fee / pass / fail
    pop_in(fr, ui_card(420, 300, "Pay a fee", "to take their evaluation", icon="dollar", main_px=58, sub_px=29),
           460, y, t, 18.18, 27.15)
    pop_in(fr, ui_card(420, 300, "Pass", "keep most of the profits", style="serif", accent=True, icon="chart",
                       main_px=110, sub_px=29), 960, y, t, 20.14, 27.15)
    pop_in(fr, ui_card(420, 300, "Fail", "you only lose the fee", style="serif", icon="down", main_px=110,
                       sub_px=29), 1460, y, t, 22.52, 27.15)
    # the one trade
    pop_in(fr, ui_card(420, 300, "A loss", "the trade goes against you", style="serif", icon="down", main_px=100,
                       sub_px=29), 460, y, t, 35.64, 41.36)
    pop_in(fr, ui_card(420, 300, "Go bigger", "to win it back", icon="chart", main_px=58, sub_px=29),
           960, y, t, 36.72, 41.36)
    pop_in(fr, ui_card(420, 300, "Breached", "the drawdown limit", style="serif", accent=True, main_px=100,
                       sub_px=29), 1460, y, t, 39.52, 41.36)
    # fear / greed / need to be right
    pop_in(fr, ui_card(420, 300, "Fear", "", style="serif", icon="brain", main_px=110), 460, y, t, 43.62, 49.10)
    pop_in(fr, ui_card(420, 300, "Greed", "", style="serif", icon="dollar", main_px=110), 960, y, t, 44.00, 49.10)
    pop_in(fr, ui_card(420, 300, "Need to be right", "", main_px=46), 1460, y, t, 45.26, 49.10)
    # fixed rules
    pop_in(fr, ui_card(420, 300, "Fixed rules", "the same every time", icon="gear", main_px=58, sub_px=29),
           460, y, t, 82.12, 88.75)
    pop_in(fr, ui_card(420, 300, "No setup?", "no trade", style="serif", icon="chart", main_px=96, sub_px=30),
           960, y, t, 83.26, 88.75)
    pop_in(fr, ui_card(420, 300, "Some weeks", "zero trades", style="serif", accent=True, icon="clock", main_px=90,
                       sub_px=30), 1460, y, t, 86.04, 88.75)
    # what it takes away
    pop_in(fr, ui_card(420, 300, "Revenge trades", "", main_px=50), 460, y, t, 90.52, 97.0)
    pop_in(fr, ui_card(420, 300, "Going too big", "", main_px=50), 960, y, t, 92.18, 97.0)
    pop_in(fr, ui_card(420, 300, "Staring at charts", "", main_px=46), 1460, y, t, 93.94, 97.0)
    # passed / payouts
    pop_in(fr, ui_card(700, 130, "Prop firm evaluations passed", check=True, align="l", main_px=40), 960, 460, t,
           103.46, 105.10, rise=50)
    pop_in(fr, ui_card(700, 130, "Payouts received", check=True, align="l", main_px=40, accent=True), 960, 620, t,
           104.40, 105.10, rise=50)
    # photos beside him
    pop_in(fr, photo_card("IMG_8640.jpg", 470, 600, rz=-3), 1520, 470, t, 62.94, 65.75)
    pop_in(fr, photo_card("IMG_9170.jpg", 420, 560, rz=-4), 1500, 480, t, 97.30, 100.0)
    pop_in(fr, photo_card("IMG_2377.jpg", 400, 540, rz=3), 1560, 500, t, 98.52, 100.0)
    pop_in(fr, photo_card("957E2BE4-21CF-40D0-BC94-DEB64836BD57.jpg", 440, 480, rz=-2), 1490, 520, t, 99.30, 100.0)
    for s in STROKES:
        s.draw(fr, t)
    for s in UNDER_TEXT:
        s.draw(fr, t)


# ---- the offer: split screen (AB) with Ricky's check cards
SPLIT = (135.45, 150.80)
OFFER = [
    ("Lifetime access to all my algorithms", 136.46),
    ("Licensed to your own trading accounts", 138.96),
    ("Prop firm roadmap to your first payouts", 141.00),
    ("Step-by-step setup guide", 143.26),
    ("1-on-1 consulting call with me", 145.02),
    ("Direct access to me after you join", 147.24),
]
OFFER_TITLE = TextSeq([L(("Here's", "sans", 135.48), ("what", "sans", 135.74), ("you", "serif", 135.84),
                         ("get", "serif", 135.94))], 150.6, (1440, 150), sizes=(70, 110))

# ---- CTA
CTA = [TextSeq([L(("Fill", "sans", 152.26), ("out", "sans", 152.34), ("the", "serif", 152.44),
                   ("application", "serif", 152.52))], 156.0, (OW / 2, 820), sizes=(80, 130)),
       TextSeq([L(("DOWN", "grey", 152.92), ("BELOW", "grey", 152.98))], 156.0, (OW / 2, 960), sizes=(90, 90),
               stagger=0.03)]
CTA_DIM = (150.85, 156.0)
SPOT = (100.0, 103.40)            # spotlight on his FTMO certificate (flipped frame coords)
SPOT_RECT = (20, 430, 380, 870)

# ---- captions (AB: 2-3 words, hard switch; Ricky: white Inter + one gold serif word)
GOLD = {"$7,000", "cent", "algorithm", "doesn't", "fail", "strategy", "loss", "back", "drawdown", "hard", "automate",
        "programmer", "advanced", "money", "failed", "years", "today", "simple", "point", "work", "payouts",
        "honest", "perfect", "machine", "month", "losses", "lying", "people", "work", "reason", "algorithm",
        "join", "touch", "capital", "evaluation", "profits", "fee", "bad", "bigger", "right", "human",
        "multiple", "manually", "myself", "once", "charts", "trade"}
NO_CAPS = ([(a, b) for a, b, _ in SIDES] + [(a, b) for a, b, _, _ in FULLSCREEN] + CARD_DIM +
           [SPLIT, CTA_DIM])


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
    groups, cur = [], []
    for i, w in enumerate(ws):
        if hidden(w["s"] + 0.05):
            if cur:
                groups.append(cur)
                cur = []
            continue
        cur.append(w)
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        chars = sum(len(x["w"]) for x in cur)
        brk = (len(cur) >= 3 or chars >= 14 or w["w"][-1] in ".,?!" or nxt is None or nxt["s"] - w["e"] > 0.25)
        if brk:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    out = []
    for gi, g in enumerate(groups):
        t0 = g[0]["s"]
        t1 = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else g[-1]["e"] + 0.4
        t1 = min(t1, g[-1]["e"] + 0.6)
        for a, b in NO_CAPS:
            if t0 < a < t1:
                t1 = a - 0.05
        out.append((t0, t1, [x["w"].strip(".,?!") for x in g]))
    return out


CAPTIONS = _caption_groups()


@functools.lru_cache(None)
def caption_sprite(words):
    words = list(words)
    gold_i = None
    for i, w in enumerate(words):
        if w.strip("$").lower() in GOLD or w in GOLD:
            gold_i = i
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


def draw_caption(fr, t):
    for t0, t1, words in CAPTIONS:
        t0, t1 = t0 - CAP_LEAD, t1 - CAP_LEAD
        if t0 <= t < t1:
            spr = caption_sprite(tuple(words))
            # tiny settle on entry (hard switch, 4-frame rise)
            dy = 10 * (1 - e_out((t - t0) / 0.13))
            blend_rgba(fr, spr, OW / 2 - spr.shape[1] / 2, 935 - 140 + dy, 1.0)
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
        self.i0 = max(0, int(t_start * FPS))
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{self.i0 / FPS:.4f}", "-i", RAW, "-an",
                                   "-vf", f"fps={FPS},hflip", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                                  stdout=subprocess.PIPE, bufsize=SW * SH * 3 * 4)
        self.next = self.i0
        self.cache = {}
        self.last = None

    def get(self, t):
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


def camera(fr, t):
    t0, t1, z0, z1, cx, cy = shot_at(t)
    z = z0 + (z1 - z0) * e_sm((t - t0) / max(0.01, t1 - t0)) if True else z0
    # slow AB-style drift: linear-ish but eased at the ends
    z = z0 + (z1 - z0) * ((t - t0) / max(0.01, t1 - t0))
    if abs(z - 1) < 1e-3:
        return fr
    w, h = OW / z, OH / z
    x0 = min(max(cx - w / 2, 0), OW - w)
    y0 = min(max(cy - h / 2, 0), OH - h)
    M = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
    out = cv2.warpAffine(fr, M, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    if z > 1.12:  # light unsharp to offset the upscale
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
    t0, t1, z0, z1, cx, cy = shot_at(t)
    z = z0 + (z1 - z0) * ((t - t0) / max(0.01, t1 - t0))
    w, h = OW / z, OH / z
    x0 = min(max(cx - w / 2, 0), OW - w)
    y0 = min(max(cy - h / 2, 0), OH - h)
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


def footage_frame(src, t):
    fr = camera(src.get(t), t)
    if SPOT[0] <= t <= SPOT[1]:
        fr = spotlight(fr, t)
    amt = max([ramp(t, a, b, 0.35, 0.3) for a, b in CARD_DIM] + [0.0])
    fr = card_dim(fr, amt)
    amt = max([ramp(t, a, b, 0.35, 0.3) for a, b in BGFX + PHOTO_DIM] + [ramp(t, *CTA_DIM, 0.6, 0.3) * 0.8, 0.0])
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
    fr = grid_bg(t)
    for s in PAGES[i][2]:
        s.draw(fr, t)
    for s in PAGES[i][3]:
        s.draw(fr, t)
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


def frame_at(tau, src):
    t = to_src(tau)
    for a, b, kind, i in FULLSCREEN:
        ta, tb = to_out(a), to_out(b)
        if abs(tau - ta) < TD / 2:
            u = 0.5 + (tau - ta) / TD
            src.get(t)
            return trans(footage_frame(src, t), full_frame(kind, i, t), u)
        if abs(tau - tb) < TD / 2:
            u = 0.5 + (tau - tb) / TD
            return trans(full_frame(kind, i, t), footage_frame(src, t), u)
        if a <= t < b:
            src.get(t)
            return full_frame(kind, i, t)
    fr = footage_frame(src, t)
    if SPLIT[0] <= t <= SPLIT[1]:
        fr = split_frame(src, t, fr)
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
    """(raw time, sound, dB under the voice level)."""
    wh, wh_s, pop, tick, ching, scr = (sfx_whoosh(0.55, 300, 6500), sfx_whoosh(0.9, 200, 4500), sfx_pop(),
                                       sfx_tick(), sfx_ching(), sfx_scratch())
    ev = []
    for a, b, kind, i in FULLSCREEN:  # whoosh in and out of every page
        ev += [(a - 0.3, wh, -17), (b - 0.3, wh, -20)]
    for t0 in (2.82, 18.18, 20.14, 22.52, 35.64, 36.72, 39.52, 43.62, 44.0, 45.26, 82.12, 83.26, 86.04, 90.52,
               92.18, 93.94, 103.46, 62.94, 97.30, 98.52, 99.30):
        ev.append((t0, pop, -21))
    for x in MONT_IMGS:
        ev.append((x[5], pop, -23))
    for k in range(9):  # count-up ticks on $7,000
        ev.append((3.30 + k * 0.05, tick, -26))
    for s in STRIKES:
        ev.append((s[4], scr, -22))
    for a, b, seqs in SIDES:  # AB: a soft click as the side text lands (chars already hold re-timed times)
        ev.append((("abs", seqs[0].chars[0]["t0"]), tick, -27))
        ev.append((("abs", seqs[1].chars[0]["t0"]), tick, -27))
    ev += [(SPLIT[0] - 0.25, wh_s, -17), (SPLIT[1] - 0.6, wh, -20)]
    for _, t0 in OFFER:
        ev.append((t0, pop, -23))
    ev += [(104.40, ching, -20), (SPOT[0], wh_s, -22), (152.44, ching, -22)]
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
    mus = load(music_path, start=SONG_START)
    f10 = int(0.01 * SR)
    mus[:f10] *= np.linspace(0, 1, f10)[:, None]
    while len(mus) < n:
        mus = np.concatenate([mus, mus])
    mus = mus[:n]
    m_rms = float(np.sqrt((mus ** 2).mean()))
    mus *= v_rms / m_rms * db(-16)
    duck = np.clip(env / (v_rms + 1e-9), 0, 1)
    duck = np.convolve(duck, np.ones(SR // 5) / (SR // 5), "same")
    mus *= (1 - 0.30 * duck)[:, None]
    tt = np.arange(n) / SR
    g = np.clip((total - 0.4 - tt) / 2.5, 0, 1)
    # a short breath in the music right before "I was."
    d0, d1 = to_out(77.05), to_out(77.62)
    g *= 1 - 0.75 * np.clip(np.minimum((tt - d0) / 0.25, (d1 + 0.6 - tt) / 0.6), 0, 1) * ((tt > d0) & (tt < d1 + 0.6))
    mus *= g[:, None]
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
