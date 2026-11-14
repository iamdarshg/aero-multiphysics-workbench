# Instagram Reel Capture — `DfOLEP6v3AR`

**Reel:** https://www.instagram.com/reel/DfOLEP6v3AR/?srtk=MTlodmt1NmNxdmdyYg==
**Captured:** 2026-11-14 (Asia/Calcutta)
**Tooling:** Playwright 1.60.0 (Python) + headless/headed Chromium 131 UA, ffmpeg for frame analysis
**Verdict up front:** **Caption retrieved verbatim.** It is *not* a description of an agentic
planning→execution→validation→hotfix workflow. It is comment-bait. The actual method is spoken
and shown on screen in the video, never written into the caption.

---

## 1. What loaded vs. what was blocked

| Pass | URL | HTTP | Result |
|---|---|---|---|
| Headless Chromium | live reel URL | 200 | Page rendered; **signup overlay present**; metadata + caption fully present in DOM |
| Headed (visible) Chromium | live reel URL | 200 | Identical DOM and text to headless run |
| Headless Chromium | `/embed/captioned/` | 200 | **No signup overlay**; full caption in `div.Caption`; no truncation |

**Blocked:** nothing material. A "Never miss a post from azizbuildss / Sign up for Instagram to
stay in the loop" signup modal was injected over the live page, and `loginLinkCount: 3` with a
`/accounts/login` link was detected — but it is a *soft* wall: it did not remove the Open Graph
metadata, and it did not gate the embed view. No login was required to read the caption.

**Not present:** `script[type="application/ld+json"]` blocks — **0** found. So the JSON-LD step of
the extraction plan produced nothing; it is not a reliable channel for Insta reels.
`aria-label`s were UI chrome only ("Video player", "Adjust volume", "Like", "Comment", "Share",
"Save", "Clip") — no caption content. The `<video>` element exposed only a `blob:` src
(`preload="none"`), so its attributes carried no content either.

**Which channel actually produced the caption:** the Open Graph meta tags *and* the embed
`div.Caption` — they agree character-for-character. The embed view is the cleaner source
(no truncation markers, full hashtag anchors present).

Reel facts read from the page: creator `@azizbuildss` ("Aziz Umarov"), posted **November 1, 2026**,
**2.9K likes**, **2,924 comments**, audio labelled **"Original audio"**, video **61.07 s, 720×1280**.

---

## 2. VERBATIM CAPTION

> The following is the exact caption text as served by Instagram, copied byte-for-byte. The
> apostrophe in "i'll" is the typographic `’` (U+2019), not an ASCII quote. Line breaks are the
> real ones from the embed `div.Caption` (`<br><br>` separators).

```
comment HACK and i’ll send you the agent board script and our exact setup

#hackathon #programming #coding
```

`og:title`, verbatim, for cross-check (note the creator prefix and escaped quotes):

```
Aziz Umarov on Instagram: "comment HACK and i’ll send you the agent board script and our exact setup

#hackathon #programming #coding"
```

`og:description`, verbatim:

```
azizbuildss on November 1, 2026: "comment HACK and i’ll send you the agent board script and our exact setup

#hackathon #programming #coding". 
```

**That is the entire caption.** There is no workflow description in it — no planning stage, no
execution stage, no validation stage, no hotfix stage. It is a lead-magnet: comment "HACK" and the
creator DMs you the board script. The promised script/doc is **not in the reel**.

---

## 3. Creator and on-screen text

**Creator:** `@azizbuildss` — display name "Aziz Umarov". (One visible commenter: `max.guillamet`,
comment "hack".)

### 3a. Burned-in overlay labels (full-screen captions, verbatim, high confidence)

These are large white-text-on-black captions composited over the footage:

```
WIN HACKATHONS
ON EASY MODE

1: Split the folders

2: Pin one board

3: Tag the teammate

BOARD MESSAGES

HIT OVER 2,000
BOARD MESSAGES
```

So the reel advertises **three** setup steps, not a four-stage agent pipeline. Timings: title
card 0–12 s; "1: Split the folders" ≈13–26 s; "2: Pin one board" ≈27–32 s; "3: Tag the teammate"
≈33–36 s; the "BOARD MESSAGES / HIT OVER 2,000" cards ≈48–58 s.

### 3b. Screen-recording inserts (verbatim where fully legible)

Small screen-recording panels fade in over the footage. Legible text, quoted exactly:

- `[Aziz's Firstmate worker] Board tooling + monorepo scaffold PR is up: #34 (closes #2). Adds AGENTS.md, tools/board (post/read/unread/wait), Claude Code hooks, README hookup steps. After it merges, pull main and see README 'Hook your agent up to the board'.`
- `[Aziz's Firstmate worker] #16 contract: orchestrator/src/store.ts will export async StateStore reducers claimTask/renewLease/completeTask/setAgentTarget/createEscalation/appendAudit/transitionInvoice plus heartbeat/reapExpired and payment receipts. Claims`
- `[Aziz's Codex] Assigned by Aziz via firstmate: default handoff voices on, unlock on first office gesture; scoped`
- `[Diego's Claude Code] @azizu06 #122 (909ac9b) and #118 (d97fa9a): RealVsSim grid now repeat(2, minmax(0, 1fr)). ... Re-review please.` (adjacent label: `reply`, `5 min later`)
- `spacetime/README.md. No Coinbase content or code changes.`
- `Ready PR only, no merge.`

A four-column ownership table, as rendered:

| Column | Stream | Owner | Paths |
|---|---|---|---|
| `B. Office + human UI` | `stream:B-office` | `Diego ( DiegoL-Mendoza )` | `web/ : R3F office, audit wall, inbox tray, approval card, pay page` |
| `C. State + integrations` | `stream:C-state` | `Anthony ( MarioTeachesTyping )` | `spacetime/, CRS and Nessie clients, reconciliation` |
| `D. Data, proof,` … | `stream:D-proof` | `Tomi ( tomiwaaluko , acting PM )` | `fixtures/, seed company, answer key, eval,` … |

Other inserts: a GitHub issue search box showing `is:issue state:open`; a hackathon track card
listing `Source AI`, `Full Sail: Pathways & Perception, A Serious Games & Simulation Challenge`,
`NVIDIA: Best Use of Jetson Nano`, `Encompass: Data Capturing Hardware`; an email with subject
`Hyphenate track prize`, body `Hi Abduaziz,` / `Congratulations on finishing in the top 20 of the Hyphenate track at CalHacks`;
and event footage captioned `CAL HACKS` / `1,900+ HACKERS`.

A doc table-of-contents is visible near the end:

```
What the board is
The 3 steps
  1. Split the folders and write down who owns what
  3. Tag the teammate
Setup in 5 minutes
Copy these
Commands
```

(Step 2, "Pin one board", is scrolled out of frame in that shot — it appears as an overlay label
instead. "Setup in 5 minutes" and "Commands" are section headings, not step numbers.)

### 3c. Burned-in speech subtitles — FRAGMENTARY, NOT A TRANSCRIPT

The video carries a burned-in caption bar transcribing the speaker. I sampled it at 1 fps at
native 720×1280 and read the frames. **This is a fragment list, not a transcript**: each frame
holds a 1–4 word phrase, captions are clipped at the frame edge, and I sampled 1 frame per second,
so phrasing between samples is missing. Read in order, top-to-bottom, left-to-right:

```
1  nobody at hackathons        2  is doing this
3  but my team                 4  our ai agents
5  into one group              6  how we won
7  4 sponsor tracks            8  at a single
9  then a track                10 prize at
11 one of the                 12 collegiate hackathons
13 and this was               14 all with barely
15 (none)                     16 (none)
17 the repo and               18 gave each person
19 (none)                    20 that into the
21 agent reads so             22 agent reads so
23 two agents never           24 (unclear — "finish"?)
25 (unclear — "then we dinner"?)
26 one github issue           27 board and the
28 agents post there          29 something or needs
30 something or needs         31 something and it
32 needs by their             33 github username
34 each agent waits           35 tag
36 since my agent             37 hands work straight
38 agent without (either?)    39 of us having
40 (unclear — "text"?)
41 so i can                   42 my entire part
43 just talking to            44 my agents and
45 agent the (entire?)        46 time talking to
47 the sponsors judging       48 (none)
49 hit over 2,000             50 board messages
51 messages across (both?)    52 hackathons
53 agent board script         54 and our exact
55 setup in (one?)            56 comment hack and
57 and I'll send it           58 don't forget to
59 your teammates             60 follow for more
```

Fragments I am **not** confident about are marked with `?` / `(unclear)`. Words in parentheses are
my best reading of clipped glyphs and should not be quoted as the creator's exact wording.

**What the fragment order implies, carefully:** the open is a claim that nobody else at hackathons
does this; their team put all their AI agents into one group and won four sponsor tracks plus a
track prize at a collegiate hackathon "with barely" (some cost/effort) — then the body moves to
GitHub issues, agents posting there, a GitHub username tag, each agent waiting, and the close is
the comment-HACK call to action. I am *inferring* the connective tissue; the words above are what
is actually on screen.

---

## 4. Does the reel describe planning → execution → validation → hotfix?

**No — not in text, and not in that shape.** Stated plainly, because it changes what's reproducible:

- The **caption** is four words of bait plus hashtags. Nothing else.
- The **overlay steps** are `1: Split the folders`, `2: Pin one board`, `3: Tag the teammate` —
  a *setup* procedure for a shared board, not an agent pipeline.
- The **screen recordings** show a GitHub-issue-centred coordination scheme: agents with distinct
  identities (`[Aziz's Firstmate worker]`, `[Aziz's Codex]`, `[Diego's Claude Code]`) posting to
  issues, PRs that are explicitly `Ready PR only, no merge.`, a review request answered
  `5 min later`, and a `tools/board (post/read/unread/wait)` CLI plus Claude Code hooks wired via
  `AGENTS.md`.
- The only artefact that smells like a state machine is a TypeScript contract listing
  `claimTask / renewLease / completeTask / setAgentTarget / createEscalation / appendAudit /
  transitionInvoice` plus `heartbeat / reapExpired`. That is task-claiming with leases, heartbeats
  and escalation — a work-distribution and liveness scheme. It is **not** the same thing as a
  plan/execute/validate/hotfix swarm, though it serves a comparable purpose.

So: the reel is a **board-mediated multi-agent handoff** pattern (folder split → ownership table →
one pinned board → agents tagged by GitHub username → agents claim and post → PR with review
handoff). Any plan/validate/hotfix framing would be *mine*, not the creator's, and I am not
supplying one.

**Video/audio caveat, per instructions:** the substantive method is carried by spoken audio and by
small screen recordings. I read what is legible in frames; I did **not** transcribe the audio, and
I will not describe what the audio "probably" says beyond the burned-in subtitle fragments in §3c.

---

## 5. Artefacts

| File | What it is |
|---|---|
| `capture.py` | **The exact script used** — headless then headed pass, meta/JSON-LD/video/aria/text extraction, login-wall detection, HTML + screenshot dumps |
| `frames.py` | First frame sampler (16 frames @ 3.8 s) + contact sheet |
| `frames_dense.py` | 44-frame sampler, text-band and screen-strip tiles |
| `download_video.py` | Grabs the real MP4 behind the `blob:` URL via network interception |
| `raw-results.json` | Full structured output of every extraction pass |
| `page-live-headless.html`, `page-live-headed.html`, `page-embed.html` | Raw DOM dumps |
| `shot-live-headless.png`, `shot-live-headed.png`, `shot-embed.png` | Page screenshots |
| `reel.mp4` | The 6.8 MB, 720×1280, 61.07 s source video |
| `contact-sheet.png`, `sheet-band-1/2.png`, `sheet-strip-1/2.png` | Frame tiles used to read overlays |
| `tr-1/2/3.png` | Subtitle-band tiles at 1 fps (source of §3c) |
| `cap-1/2.png`, `wcap-1/2.png`, `ucap-1/4.png`, `tcap-1..4.png` | Intermediate subtitle crops |
| `sub-1..4.png` | Subtitle tiles |

**Reproduce:**

```
python capture.py        # metadata + caption + login-wall report
python download_video.py # the mp4
python frames.py         # 16-frame contact sheet
```

---

## 6. Method notes (what actually worked, for next time)

1. **`/embed/captioned/` is the reliable path.** Full caption, no signup modal, no truncation, and
   the `div.Caption` markup is stable. Try it before fighting the main page.
2. **`og:title` / `og:description` alone are usually enough** for a reel caption, and they survive
   the signup overlay.
3. **JSON-LD is absent** on reel pages — don't budget for it.
4. **Burned-in subtitles are the only cheap route to the spoken content.** They are not in any
   meta tag. Reading them needs native-resolution frames via ffmpeg, not element screenshots — the
   caption bar is ~50 px tall at 720p and illegible in a scaled page screenshot.
5. The `blob:` video src means the mp4 must be captured by watching network responses; once you
   have it, ffmpeg `crop`+`tile` turns 61 s of video into 3 readable sheets.
6. `tile=2x8` with `fps=1` and a tight crop is the efficient shape: ~1000×1400 per sheet, text
   stays legible after downscale.