# vsl_edit.mp4

Edit of Jan's raw VSL (`raw-vsl` release, `VSL.mp4`, 1920×1080, 2:35).
**1920×1080 (native, no upscale), 30 fps, H.264 2-pass 4.5 Mbps (kept under GitHub's 100 MB file limit), BT.709**, about 2:34, audio at -14 LUFS.
Rebuild with [`tools/edit_vsl.py`](../tools/edit_vsl.py) (instructions at the top of the script).

**Structure** follows the AB Nasdaq reference VSL. **Look** follows Ricky's editing style
([`ricky-style-reference/`](../ricky-style-reference/)). The other videos (thank-you, FAQs) are not edited yet.

## What was done

- **Flipped horizontally.** The raw was recorded mirrored: the FTMO "Passed Verification" plaque behind Jan read
  backwards. Now it reads correctly and is used as proof.
- **Pauses trimmed:** 9 gaps over 0.3 s, 1.7 s in total. His delivery was already tight.
- **Camera (AB):** a new framing every 3-5 s on sentence breaks: wide and close shots, both with slow push-ins or
  pull-outs, plus punch-ins on "we failed", "we failed again" and "they're simply lying to you". The camera holds
  still while text sits beside his head.
- **Captions (AB):** 2-3 words at a time with a hard switch, bottom centre, over a soft dark fade. In Ricky's style:
  white Inter Display plus one key word in gold EB Garamond italic with a glow. Captions step aside while other
  graphics are up.
- **Text beside his head (AB side text, Ricky style)**, 9 times: "I failed | *10 challenges*",
  "2.5 years building | *an algorithm*", "trade their | *capital*", "not a skill problem | *being human*",
  "took myself | *out of the equation*", "not some | *holy grail*", "October was | *a bad month*",
  "get rich quick? | *this isn't it*", "this is | *for you*". The background darkens softly around him while it's up.
- **Full-screen pages** (Ricky's STEP page, AB's keynote cards): "How prop firms *work*", "*9 out of 10* traders fail",
  "*2020*, loss after loss", "The strategy wasn't the problem. *I was.*"
- **Cards** (orange to black, glowing rim, popping in one at a time on the words, background blurred and darkened):
  - "*$7,000*" counting up
  - Pay a fee → *Pass* → Fail, with "not your own *capital*"
  - A loss → Go bigger → *Breached*
  - Fear / Greed / Need to be right, struck out on "an algorithm doesn't feel it"
  - Fixed rules → No setup? → *Some weeks* zero trades
  - Revenge trades / Going too big / Staring at charts, each struck out
  - "Prop firm evaluations passed ✓" and "Payouts received ✓"
- **Photos from the results-and-images release:**
  - The developer-team photo on "developing teams".
  - Three lifestyle photos on "runs while you're at work".
  - A spotlight and slow push onto his FTMO certificate on "I used it to pass multiple prop firm evaluations".
- **Proof montage:** 10 student payouts and certificates popping in on "I'm not the only one who runs them"
  ("MEMBERS RUNNING IT RIGHT NOW").
- **Offer split screen (AB):** Jan slides to the left, and a grid panel builds "Here's what *you get*" line by line as he
  says each item.
- **CTA:** "Fill out *the application*", "DOWN BELOW", with the background softened around him.
- **Transitions:** zoom-blur in and out of pages and the montage. Everything else is a straight cut.

## Sound

- Voice: low cut and light compression, then the whole mix is normalized to -14 LUFS.
- Music: **"Me and the Devil" (instrumental)** from 0:00. The song is longer than the video, so it doesn't loop. It
  sits about 16 dB under his voice, dips slightly while he talks, and drops for a beat right before "*I was.*"
  It fades out at the end.
- Sound effects (synthesized, nothing to license), all quiet:
  - a soft whoosh in and out of each page
  - a pop on each card and photo
  - ticks on the $7,000 count-up
  - a marker scratch on each strike-through
  - a soft click as side text lands
  - a "ching" on "payouts" and on "the application"

## Music licence

"Me and the Devil" is not royalty-free. In a paid ad or on YouTube it can get a copyright claim or be muted. It is
not stored in this repo (the repo is public). To change the song, pass a different file to the `audio` step.
