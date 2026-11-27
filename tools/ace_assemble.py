"""Assemble Ace's VSL from the best takes of the raw recording session (mic checks, retakes and notes to the editor
are left out), trimming dead air inside each take. Writes a clean 1080p30 base video + its audio.

    python tools/ace_assemble.py RAW OUTDIR
"""
import json
import subprocess
import sys

import numpy as np

RAW, OUT = sys.argv[1], sys.argv[2]
SR = 48000
# (raw start, raw end, what he says) -- the chosen take of every line, in script order
TAKES = [
    (30.00, 37.40, "For two years, trading didn't work for me. I paid $1,200 for a mentorship and then couldn't pass an eval for over a year and a half."),
    (40.70, 47.30, "So I'm not going to open this with a wall of payouts like all the gurus do. Instead, I'm going to show you my actual students' results."),
    (54.40, 61.06, "And I'll tell you this right now. If you follow my strategy, I guarantee you'll be able to pass a $100,000 funded account."),
    (64.55, 68.45, "I'm so confident in that, that if you don't, I'll give you every single cent back."),
    (74.35, 77.35, "Stick around and I'll show you exactly why I can make that promise."),
    (87.45, 90.45, "Brandon came in with zero trading experience."),
    (93.60, 97.15, "After working with me, he got his first payout in two weeks."),
    (99.05, 106.70, "Zlade failed for seven months. He came to me on the eighth month, was able to pass three evals and he got paid."),
    (184.20, 200.55, "If you've been buying eval after eval, if you've been $200 away from passing, if you've watched one bad day wipe away all of your good ones, and then you tell yourself just one more account, I know exactly where you are, because I lived there for over a year and a half."),
    (214.70, 222.45, "I worked the popcorn machine at a movie theater for $10 an hour. I hated it so much that I swore I would never work a job ever again."),
    (226.60, 230.35, "I saved up my money, put it into a live account and then blew it."),
    (261.40, 273.10, "So I did what everyone else does. I paid $1,200 for a mentorship who ran me through a couple of 20-minute videos and then left me. No check-ins, no follow-ups, no nothing."),
    (284.60, 288.35, "That's when I swore nobody who trusted me would ever be treated like that."),
    (299.80, 305.55, "So here's my deal. I'll personally work with you step by step until you're funded $100,000."),
    (310.30, 313.20, "You don't need years of experience. Brandon had zero."),
    (355.45, 362.05, "You don't need to learn 50 different concepts, you just need to follow simple rules that make decisions for you so you're not guessing."),
    (395.55, 399.92, "And every single week I review your trades with you so you're not alone like I was."),
    (417.25, 424.15, "If you follow the strategy and aren't able to pass a $100,000 account, I will refund you every single cent."),
    (445.20, 447.35, "Now, why would I make that guarantee?"),
    (450.20, 452.35, "Because of what I figured out after that year."),
    (462.70, 474.55, "I was about to graduate college. My family was nagging me, asking me, are you making money yet? And honestly, the plan was to graduate college, get a job that I didn't like, and keep trading on the side. But that's when everything clicked."),
    (497.00, 500.30, "My problem wasn't the strategy that I was trading. It was me."),
    (572.60, 580.90, "I FOMO'd, I revenge traded, and so I stopped working on myself and decided to make something simple where the rules make the decisions, not my emotions."),
    (582.90, 587.10, "I passed, I got paid, and I've been getting paid every single month since."),
    (625.00, 635.98, "And it's not just working for me. Koi was in the military, he got out and started trading ICT, was getting payouts every now and then. He joined in July and was instantly able to get two payouts back to back."),
    (650.15, 658.05, "Now I want to make this very clear: this is not a signal group. I genuinely want to teach you and help you learn and become consistently profitable."),
    (682.45, 686.95, "And it's not a Discord where you're just going to join and then watch videos and be left on your own."),
    (715.65, 722.40, "If you're genuinely willing to put in the work, and you're not just here to try to get rich quick, and you genuinely want to be profitable long term,"),
    (735.80, 738.55, "click the link below and fill out a short application."),
    (755.45, 759.20, "We'll hop on a quick call, I'll look at where you're at and you'll get a clear yes or no."),
    (766.70, 768.20, "Both answers are fine."),
    (777.00, 783.40, "And remember, it's risk-free, because if you're not able to pass a $100,000 account, you get every single cent back."),
    (790.90, 791.75, "I'll see you on the call."),
]
PAD, MIN_SIL = 0.12, 0.32

# silences across the whole raw (voice-level threshold)
log = subprocess.run(["ffmpeg", "-hide_banner", "-i", RAW, "-vn", "-af", f"silencedetect=n=-38dB:d={MIN_SIL}",
                      "-f", "null", "-"], capture_output=True, text=True).stderr
sil, st = [], None
for ln in log.splitlines():
    if "silence_start:" in ln:
        st = float(ln.split("silence_start:")[1].split()[0])
    elif "silence_end:" in ln and st is not None:
        sil.append((st, float(ln.split("silence_end:")[1].split()[0])))
        st = None

pieces = []
for a, b, _ in TAKES:
    cur = a
    for s, e in sil:
        if e <= a or s >= b:
            continue
        s2, e2 = max(s, a) + PAD, min(e, b) - PAD
        if s2 > cur and e2 - s2 > 0.15 and s > a and e < b:
            pieces.append((cur, s2))
            cur = e2
    pieces.append((cur, b))
pieces = [(round(round(a * 30) / 30, 4), round(round(b * 30) / 30, 4)) for a, b in pieces if b - a > 0.08]
total = sum(b - a for a, b in pieces)
print(f"{len(TAKES)} takes, {len(pieces)} pieces, {total:.1f} s")
json.dump(dict(takes=TAKES, pieces=pieces), open(f"{OUT}/edl.json", "w"), indent=1)

# video: each piece cut frame-exact at 30 fps on its own (low memory), then joined
import os
os.makedirs(f"{OUT}/pieces", exist_ok=True)
with open(f"{OUT}/pieces/list.txt", "w") as lf:
    for i, (s_, e_) in enumerate(pieces):
        fn = f"{OUT}/pieces/p{i:03d}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, s_ - 2):.3f}", "-i", RAW, "-ss",
                        f"{s_ - max(0, s_ - 2):.3f}", "-t", f"{e_ - s_:.3f}", "-an", "-vf", "fps=30", "-c:v",
                        "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p", fn], check=True)
        lf.write(f"file 'p{i:03d}.mp4'\n")
# exact length of every video piece (frames / 30), so sound and picture stay in sync across all cuts
vdur = []
for i in range(len(pieces)):
    n = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_packets", "-show_entries",
                            "stream=nb_read_packets", "-of", "csv=p=0", f"{OUT}/pieces/p{i:03d}.mp4"],
                           capture_output=True, text=True).stdout.strip())
    vdur.append(n / 30)
pieces = [(s_, s_ + d) for (s_, _), d in zip(pieces, vdur)]
json.dump(dict(takes=TAKES, pieces=pieces), open(f"{OUT}/edl.json", "w"), indent=1)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{OUT}/pieces/list.txt", "-c", "copy",
                f"{OUT}/base_video.mp4"], check=True)
# audio: cut with 6 ms crossfades
a = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", RAW, "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le",
                                  "-"], capture_output=True, check=True).stdout, np.float32).reshape(-1, 2)
fade = int(0.006 * SR)
out = np.zeros((0, 2), np.float32)
for s, e in pieces:
    seg = a[int(s * SR):int(e * SR)]
    seg = seg.copy()
    f4 = int(0.004 * SR)
    seg[:f4] *= np.linspace(0, 1, f4)[:, None]
    seg[-f4:] *= np.linspace(1, 0, f4)[:, None]
    n = int(round((e - s) * SR))
    seg = np.pad(seg, ((0, max(0, n - len(seg))), (0, 0)))[:n]
    out = np.concatenate([out, seg])
import wave
with wave.open(f"{OUT}/base_audio.wav", "wb") as wf:
    wf.setnchannels(2)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes())

subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{OUT}/base_video.mp4", "-i", f"{OUT}/base_audio.wav", "-c:v",
                "copy", "-c:a", "pcm_s16le", "-shortest", f"{OUT}/base.mov"], check=True)
print("done")
