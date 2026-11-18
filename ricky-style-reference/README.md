# Style reference: Ricky's edits (rickyvideoediting)

Analysis of [eliascroesus/rickyvideoediting](https://github.com/eliascroesus/rickyvideoediting): its approved
style guide (`STYLE.md`), the two finished edits and the Python render engine behind them
(`tools/edit_youtube_paid_me.py`). Frames in [`frames/`](frames/) are taken from the finished
"How much YouTube paid me" edit (the Level B, "light highlights" version).

## What the repo is

- A full editing workspace: `raw-videos/` (Git LFS + GitHub Releases for big files), `edited-videos/`,
  a library of **32 music tracks** (Kevin MacLeod, CC BY 4.0: tension, suspense, intense action, stings,
  plus 3 chill beds that were *rejected*) and **796 sound effects** (CC0: whooshes, pops, hits, booms,
  risers, glitches, UI clicks, heartbeats, clocks), plus a synthesized cinematic SFX pack (`tools/synth_cinematic.py`).
- **No After Effects / Premiere.** Every motion graphic is drawn frame by frame in Python
  (OpenCV + Pillow + numpy), then muxed with ffmpeg. One script per video holds the scene list, text
  timings, cards and the audio mix, so changes are precise and repeatable.
- Two finished edits: *How much YouTube paid me* (10:01, Level B) and *How to make stores* (7:35, Level A raw).

## The core idea: keep it raw, add only what earns its place

Ricky's feedback was always **"less"**. Two approved levels:

| Level | What's added |
|---|---|
| **A: Raw** (latest preference) | Nothing except STEP pages at each section, with a soft whoosh. Invisible fixes only: stabilize, trim pauses > 0.6 s, de-echo, -14 LUFS. |
| **B: Light highlights** | A + ~one highlight every 1-2 min, never stacked: hook-number zoom, blur-then-reveal of money, one full-screen text page, cards, text beside the head (2-4×). |

## Design system

**Colour: 60 / 30 / 10**

| Role | Colour |
|---|---|
| 60% background | near-black `#060607`-`#0B0D12` |
| 30% text | white `#F2F2F2`, slate grey `#968C9C` |
| 10% accent | gold `#FAAC30` (special words), card orange `#E8681A` → black |

**Typography: always two fonts together**

- **Inter Display SemiBold**, white: the normal words.
- **EB Garamond Bold Italic**, gold with a deep two-layer glow: the *one* key word or number.
- Pattern: `Find a` *`viral product`* · `last month I made` *`$40,000`* · `join the` *`Discord`*.
- Never a screen full of white captions; white only appears *next to* a gold word.

## Motion graphics (what each element is and how it moves)

| Element | Look | Motion | Frames |
|---|---|---|---|
| **STEP page** | Black page, warm orange glow rising from the bottom (+ a faint one top-left), thin grid that fades toward the edges and drifts slowly sideways (7 px/s). Grey `STEP 01` label, white sans + gold serif title, huge faint outlined serif `01` behind. | Letters write on one by one (35 ms stagger): each rises ~45% of its height, goes blurred → sharp and **yellow → final colour**, posterized to **15 fps** for a hand-made, choppy feel. Gold underline draws on (trim path) 1 s in. ~4.5 s total, voice keeps playing. | `13`-`15`, `17` |
| **Full-screen text page** | Same grid page; one key sentence. | Same write-on, then a white line **strikes through** the gold words. | `03`, `04` |
| **Cards** | Rounded rect (r 30-70 px), orange top-left → black gradient, faded grid inside, glowing orange edge brightest top-left, faint line icon (play, $, TV) clipped at the right edge. Big gold serif number or white sans phrase + one small grey line. **No tiny all-caps labels.** | `pop_in`: starts at 74% scale, tilted back 32° in 3D, rises 90 px; expo-out (fast entry, long settle). Several cards come **one at a time** on the words, linked by short drawn lines; numbers can count up ($0 → $100 with ticks) and get struck out in red. Exit: tilt away + fade (0.35 s). | `08`, `09`, `16` |
| **Background behind cards** | Footage blurred (12 px), double vignette, darkened to 45%. Only while cards are on screen. | Fades in and out with the cards. | `08`, `16` |
| **Text beside the head** | White sans words on the left of his face, gold serif word on the right, at face height, tilted in 3D (ry ±14-16°, rz up to 4°), can tuck *slightly* behind his head (person cut-out mask) but never be hidden. | Same letter write-on. Background softly darkened + blurred through a **wide feathered ellipse** around him, no hard cut-out edge. Camera stays still. | `10`-`12`, `19` |
| **Hook number zoom** | Rest of the screen dimmed + blurred (spotlight), thin orange underline draws under the number. | One slow push-in (1× → 2×) onto "122.8M". | `01`, `02` |
| **Blur → reveal** | Money number blurred until he says it. | Unblur + zoom onto it, underline draws, then back out. | `05`, `06` |
| **Transitions** | Only into/out of STEP & UI pages. | 0.4 s **zoom-blur crossfade**: outgoing frame zooms in 8% + blurs, incoming zooms 95 → 100%. Everything else is a straight cut. | `20` |

**Easing** everywhere: cubic-out / expo-out for entries (fast in, slow settle), quintic in-out for camera
moves, smoothstep for fades. Nothing linear, nothing bouncy.

**Screen shares stay raw:** full frame, no zoom, no captions, no music. At most a row of cards for the
one key number (`16`). Compare `18`, untouched.

## Sound

- Music: dark and mature only (an intense instrumental for hook/money moments, "Crypto" by Kevin MacLeod
  under explainers). **Upbeat/playful tracks were rejected** ("childish").
- Music fades **in slowly over 5-7 s, out over 3-5 s**, drops to silence right before a big reveal,
  and is **never** under screen shares.
- SFX are quiet and sparse, synthesized in code: soft whoosh (transitions/pages), soft pop (each card),
  ticks (count-ups), a ching on a money reveal. **No bass drops / booms at the start** ("too AI-ish").
- De-echo where his mic picked up his speakers, loudness normalized to **-14 LUFS** (true peak -1.2).

## Camera

Default **no camera movement**. Only: one push into the hook number and one slow zoom before a reveal.
Paper shots are stabilized (gentle 1.08-1.14 framing). No punch-ins, no drifting, no zoom on first face shot.

## Export

2560×1440, 30 fps, H.264 CRF 14 preset slow, AAC 320 kbps, 4K sources downscaled with Lanczos.

## Rejected (don't do these)

Grey grid pages with cheap grey cards; small all-caps labels; thin lemon-yellow text; lots of white
captions or captions over screen shares; text hidden behind the head; hard haloed cut-outs; zooms and
spotlights all over tutorials; phone mockups replacing real screens; constant punch-ins / drifting;
bass drops; upbeat music; music popping in.

## What this means for Jan's VSL, thank-you and FAQ videos

Ricky's style is built for long YouTube tutorials. A VSL / thank-you / FAQ video is closer to the talking-head
sections, so the parts that carry over directly are:

- **The design system:** black + gold, Inter + EB Garamond italic, the glow, the 15 fps letter write-on.
- **Text beside the head** for key claims ("I made | *$X*", "this is | *not* a course").
- **Cards** for numbers, proof and lists (results, prices, "what you get"), with the background dimmed.
- **STEP-style pages** as section headers (e.g. *"Who this is* **for**", *"What happens* **next**" on the thank-you video).
- **Restraint:** dark music under the voice, slow fades, quiet whoosh/pop SFX, -14 LUFS, no booms, no busy camera.

The style of the VSL / thank-you **reference videos** you're uploading should decide pacing and how many
graphics we add. This system can supply the look of those graphics.
