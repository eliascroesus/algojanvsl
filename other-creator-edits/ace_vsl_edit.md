# ace_vsl_edit.mp4 (another creator's VSL)

Edit of `AceVSL1.mp4` (`other-creator-raw-vsl` release): 13:24 of raw webcam recording (1080p60) → a **3:05 VSL**,
1920×1080, 30 fps, about -14 LUFS. It's the same style as Jan's VSL: AB Nasdaq's structure and Ricky's design (black +
gold, Inter + EB Garamond italic, orange cards, grid pages), plus the light leaks and staircase zooms from the
thank-you edit.

## 1. The cut (`tools/ace_assemble.py`)

The raw was the whole recording session: a mic check, "am I centred?", several retakes of most lines, and notes to the
editor ("redo that", "don't include the weird peace sign", "start spamming payouts now"). The script picks **the best
complete take of each line** (33 takes, listed in the script with what he says) and puts them in script order. It
trims dead air inside takes on true silence, so it ends up with 52 pieces.

- Picture and sound are cut to the same frame for every piece, so the sound stays in sync across all the cuts.
- Final take order: hook → the guarantee → Brandon and Zlade → "if you've been buying eval after eval…" → his story
  (popcorn machine, blown account, the mentorship that left him) → the deal → why the guarantee (college, "it was me",
  FOMO / revenge trading → simple rules) → Koi → "not a signal group / not a Discord" → who it's for → application →
  risk-free → "I'll see you on the call" (the take without the peace sign).

## 2. The edit (`tools/edit_ace.py`)

- **Captions:** readable phrases, gold key word; red for "failed", "blew", "couldn't", "revenge" and the like.
- **Hook:**
  - "For two years | *trading didn't work*" (red);
  - a red **-$1,200** card "for a mentorship";
  - "couldn't pass an eval | *for 1.5 years*";
  - "A wall of payouts / like all the gurus do", struck out;
  - page "INSTEAD / My students' *results*".
- **Guarantee:** page "I GUARANTEE YOU'LL PASS / ***$100,000*** / funded account", then "*Every single cent back* / if you
  don't pass".
- **Student results:** each starts in red and ends in gold:
  - BRANDON: Zero experience → *First payout in 2 weeks*;
  - ZLADE: Failed 7 months → *3 evals passed* → *Got paid*;
  - KOI: Ex-military (started trading ICT) → Payouts now & then (never consistent) → *2 payouts back to back*.
- **The pain:**
  - "buying eval | *after eval*";
  - red "*$200 away* from passing";
  - red page "One bad day / *wipes out the good ones*" with a falling chart;
  - "just one more | *account*".
- **His story:**
  - page "POPCORN MACHINE, MOVIE THEATER / ***$10*** / an hour";
  - "never work a job | *ever again*";
  - "Live account", struck out;
  - -$1,200 mentorship → "20-minute videos / then he left me";
  - red *No check-ins / No follow-ups / No nothing*.
- **The deal:** a split screen, "Here's *my deal*", builds line by line:
  - 1-on-1 until funded
  - no years of experience needed
  - no 50 concepts to learn
  - simple rules that decide for you
  - weekly trade reviews
  - pass $100,000 or every single cent back
- **Why the guarantee:**
  - "are you making | *money yet?*";
  - Graduate college → *A job I didn't like* → Trade on the side;
  - page "THEN IT CLICKED / My problem wasn't the strategy. / ***It was me.***";
  - FOMO and Revenge trading, struck out → *Simple rules* decide, not my emotions;
  - ✓ Passed ✓ Got paid ✓ *Paid every single month since*.
- **What it isn't:** page "TO BE VERY CLEAR / This is not a *signal group*" (struck through);
  "consistently | *profitable*"; "Just a Discord where you're left on your own", struck out.
- **Close:**
  - "THIS IS FOR YOU IF" ✓ willing to put in the work ✓ not here to get rich quick ✓ want to be profitable long term;
  - "Click the link *below* / FILL OUT A SHORT APPLICATION";
  - *A quick call* → *Clear yes or no*;
  - page "AND REMEMBER / ***Risk-free*** / pass $100,000 or *every single cent back*";
  - "See you *on the call*" over a held last frame that fades out.
- **Camera:** opens slightly tight and eases out. Staircase push-ins land on the heavy lines ("I'm so confident…",
  "I lived there…", "nobody who trusted me…", "why would I make that guarantee?"). Each resets under a light leak or a
  smooth pull-out.
- **Sound:**
  - "Me and the Devil", opening on the symphony, louder through the hook, then about 18 dB under his voice;
  - soft whooshes on the light leaks, pops on cards, scratches on strike-throughs;
  - a "ching" on each payout and on "every single cent back".

## Things to check with him

- **Student names** are spelled as the transcript heard them: **Brandon**, **Zlade** and **Koi**.
- **No payout screenshots:** he planned to "flash student proof / spam payouts" at 0:27 but none were uploaded, so the
  student stories are shown as cards. Upload the screenshots (to the same release) and they can be dropped in.
- **Music:** the song is the same one as Jan's videos; send another if he has his own.
