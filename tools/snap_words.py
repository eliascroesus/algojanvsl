"""Re-time word starts on the audio: Whisper's word times can be ~0.1-0.25 s off, so each start is moved to the
clearest quiet-to-voice onset within -0.08..+0.14 s of it (only when there is one) (onsets are where text should land).

    python tools/snap_words.py words.json audio16k.wav words_aligned.json
"""
import json
import sys

import numpy as np
from scipy.io import wavfile

src, wav, out = sys.argv[1:4]
W = [w for w in json.load(open(src)) if w["w"].strip()]
sr, a = wavfile.read(wav)
a = a.astype(np.float32) / 32768
h = sr // 100  # 10 ms frames
e = np.sqrt(np.convolve(a ** 2, np.ones(h) / h, "same")[::h])
db = 20 * np.log10(e + 1e-9)
fr = lambda t: int(round(t * 100))
moved = []
prev = -1.0
for i, w in enumerate(W):
    s0 = w["s"]
    lo = max(s0 - 0.08, prev + 0.08)
    hi = min(s0 + 0.14, w["e"] - 0.04) if w["e"] - 0.04 > lo else s0
    best, score = None, 0.0
    for f in range(fr(lo), fr(hi) + 1):
        if f < 3 or f + 3 >= len(db):
            continue
        quiet = db[f - 3:f].min()
        rise = db[f + 2] - quiet
        if quiet < -25 and db[f + 2] > -24 and rise > score:
            best, score = f, rise
    new = (best - 1) / 100 if best is not None and score >= 10 else s0
    new = max(new, prev + 0.05)
    moved.append(new - s0)
    W[i] = dict(w, s=round(new, 3), e=max(w["e"], new + 0.05))
    prev = new
json.dump(W, open(out, "w"), indent=0)
m = np.array(moved)
print(f"{len(W)} words, moved: mean {m.mean():+.3f}s, |moved|>0.05 s: {(abs(m) > 0.05).sum()}")
