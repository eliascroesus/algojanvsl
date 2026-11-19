# thankyou_edit.mp4

Edit of Jan's raw thank-you video (`thank-you` release, `thankyou.mp4`, 1920×1080, 1:40).
**1920×1080, 30 fps, H.264, BT.709**, about 1:38, audio at -14 LUFS.
Rebuild with [`tools/edit_thankyou.py`](../tools/edit_thankyou.py). It's the VSL engine with its own cue sheet, and
it runs the same way as `tools/edit_vsl.py`.

**Structure** follows AB Nasdaq's thank-you video (`thank-you-reference` release). **Look** follows Ricky's style and
matches the VSL.

## What was done

- **Flipped** like the VSL (the raw was mirrored). Pauses over 0.3 s trimmed (4 cuts, 1.7 s).
- **Camera (AB):**
  - it opens tight on his face and eases out to wide while he says "thank you";
  - smooth two-step staircase zooms on the key lines: "one step closer… your life around", "phone in hand… miss
    that text", "went through them… a few years ago", "on this call… your trading objectives";
  - each staircase resets under a light leak or with a smooth pull-out;
  - he stays calm and wide for the doubts.
- **Light leaks (AB):** a warm film burn (orange to pale yellow, made in code) on every cut into and out of a page and
  the split screen, plus the zoom resets. There are no other transitions.
- **Pages** (Ricky's grid page):
  - "YOU'VE TAKEN ACTION / *90%* / of traders couldn't do"
  - "What are the *next steps?*"
  - "WHAT YOU'RE THINKING / Is this actually *legit?* / Is this really going to *work?*"
  - a **red** page, "Dangerous strategies that *blow your account*", with a falling chart line drawing behind it
  - "MY TRACK RECORD / *2.5 years* backing every algorithm", with a rising gold equity line
- **Cards:**
  - *Your emotions* (red, struck out) → *The system* does the executions for you
  - *Your application* is being reviewed by my team, with a gold progress line filling underneath; captions stay on,
    like AB's application card
  - *Text message* straight from my team to your phone
  - *A lot of money* spent trying different things out (red)
  - A nice website → *No track record* → *Backtests only* (red), "not *reliable at all*"
  - Check your email → Accept the invite → *In your calendar* (steps 1-3)
- **Text beside his head:** "Thank you | *for applying*", "selling you | *bots that don't work*" (red),
  "a little bit | *differently*", "it's solid | *very robust*".
- **"Inside *the program*":** a split screen like the VSL's offer, building line by line:
  - every algorithm I personally use
  - the ones I pass prop challenges with
  - the same ones that got me my payouts
  - 1-on-1 consultation with me
  - setup guide to your first payout
- **Close:** "THANKS FOR APPLYING / See you *soon*".
- **Captions:** the same readable phrase captions as the VSL. Gold marks the key word and red marks the negative
  words ("stupid", "dangerous", "skeptical"). They step aside for pages and card rows and stay on over the
  application and text-message cards.

## Sound

- **Music:** "Me and the Devil" (instrumental), the same as the VSL: it opens on the symphony (5.54 s into the song).
  It's louder through "thank you for applying" (about 10 dB under his voice), then eases down to a bed about
  16-17 dB under his voice, dipping slightly while he talks, and fades out at the end.
- **Sound effects:** AB uses none, so ours are kept soft:
  - a quiet whoosh on each light leak
  - a pop on each card and list line
  - a marker scratch on the strike-through
  - soft clicks on the side text
  - one "ching" on "payouts"
- **Voice:** the same clean-up as the VSL; the mix is at -14 LUFS.

Not royalty-free: see the music note in [`vsl_edit.md`](vsl_edit.md).
