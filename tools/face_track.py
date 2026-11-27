"""Track the speaker's face through a video (twice a second) so text and zooms follow him.

    python tools/face_track.py RAW out.json [hflip]
Writes [[t, cx, cy, face_w], ...] in full-resolution pixels, gaps filled and smoothed.
"""
import json
import subprocess
import sys

import cv2
import numpy as np

raw, out = sys.argv[1], sys.argv[2]
flip = len(sys.argv) > 3 and sys.argv[3] == "hflip"
W, H, STEP = 960, 540, 0.5
vf = f"fps={1 / STEP},scale={W}:{H}" + (",hflip" if flip else "")
p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", raw, "-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                     stdout=subprocess.PIPE)
cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
rows, i = [], 0
while True:
    buf = p.stdout.read(W * H)
    if len(buf) < W * H:
        break
    g = np.frombuffer(buf, np.uint8).reshape(H, W)
    fs = cc.detectMultiScale(g, 1.1, 5, minSize=(90, 90))
    if len(fs):
        x, y, w, h = max(fs, key=lambda f: f[2] * f[3])
        rows.append([i * STEP, (x + w / 2) * 2, (y + h / 2) * 2, w * 2])
    else:
        rows.append([i * STEP, None, None, None])
    i += 1
a = np.array([[r[0]] + [np.nan if v is None else v for v in r[1:]] for r in rows], float)
ok = ~np.isnan(a[:, 1])
for k in (1, 2, 3):
    a[:, k] = np.interp(a[:, 0], a[ok, 0], a[ok, k])
    # gentle smoothing (moving median then mean over ~2 s)
    med = np.array([np.median(a[max(0, j - 2):j + 3, k]) for j in range(len(a))])
    a[:, k] = np.convolve(np.pad(med, 2, mode="edge"), np.ones(5) / 5, "valid")
json.dump(a.round(1).tolist(), open(out, "w"))
print(f"{len(a)} samples, detected {ok.mean() * 100:.0f}%; x {a[:, 1].min():.0f}-{a[:, 1].max():.0f}, "
      f"y {a[:, 2].min():.0f}-{a[:, 2].max():.0f}, face w {a[:, 3].min():.0f}-{a[:, 3].max():.0f}")
