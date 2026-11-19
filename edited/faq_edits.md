# FAQ videos

The four raw FAQ videos (`faq` release), edited in the same style as the VSL and thank-you video, with **no music**.
The audio is Jan's voice only (cleaned up like the VSL) plus the same soft sound effects as the thank-you video
(whoosh on light leaks, pops on cards, a marker scratch on strike-throughs). Each is at -14 LUFS.
**1920×1080, 30 fps, H.264, BT.709.**

Rebuild with [`tools/edit_faq.py`](../tools/edit_faq.py). It's the thank-you engine; the cue sheet is picked by the raw
file's name. Run it from a folder holding that FAQ's `words.json` / `words_aligned.json` (`tools/snap_words.py`),
`fonts/` and `imgjpg/`. Use `audio none OUT.wav` for the voice-only mix.

| File | Length | Graphics |
| --- | --- | --- |
| `faq_how_much_time.mp4` | 0:15 | "Honestly \| *almost none*"; *Set up* (once, at the start) → Learn it; page "Everything runs *automatically*"; "you don't need to" over *Watch charts* / *Trade by hand*, both struck out; "that's \| *about it*" |
| `faq_is_this_legit.mp4` | 0:14 | page "FAIR QUESTION / Yes, this is *legit.*"; push-ins; ✓ Prop firm challenges passed, ✓ *Payouts received* (with a ching); "OTHER TRADERS USING MY SYSTEMS" montage of member payouts and certificates; push-ins on "I wouldn't put my name on something…" |
| `faq_what_is_inside.mp4` | 0:22 | page "What do you *actually get?*"; *Full algo portfolio* → *CFDs* (with MetaTrader) → *Futures* (everything is covered); *Prop firms* vs *Cash accounts*, "pick what *suits you*"; split screen "You also *get*": complete prop firm roadmap, to your first payout, my consulting along the way, setup guide to get you started |
| `faq_who_is_this_for.mp4` | 0:18 | "tired of \| *trading manually*" (red); red *Emotions* → *No time* → *12 hours a day*; page "then this is *for you.*"; "the next level \| *by automating*"; *Fixed rules* vs *Your emotions* (struck out) |

All four use:

- the same readable phrase captions (gold key word; red for the negatives in "who is this for");
- warm light leaks into and out of every page;
- smooth staircase push-ins on his face;
- the background blurred and darkened behind cards.
