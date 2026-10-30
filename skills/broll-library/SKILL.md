---
name: broll-library
description: Sort a B-roll library from raw footage. Scans a drive or folder, shows every clip as a filmstrip so the person picks the ones with B-roll, then Claude finds the best 6-15 second moments in each (by their rules), they review and adjust them in a browser window, and the finished clips are cut from the originals and sorted into folders by what's in them. Use when someone says "sort my B-roll", "build my B-roll library", "find B-roll on my drive", "go through my footage", or asks for the B-roll skill.
---

# B-roll Library

You turn someone's raw footage into a sorted B-roll library. They do two things only: tick the clips they want, and review your
picks. You do everything else and never make them run a command.

Tools: `uv run ~/.claude/skills/broll-library/broll.py <command>` (it installs what it needs on first run). Everything it makes
lives in `~/B-Roll Sorter`. **Their footage is only ever read**: never move, rename, re-encode or delete an original.

Say what's happening in one warm line before anything that takes more than a minute, then get on with it. Don't check in mid-run.

## 0 · Check
`ffmpeg -version`, `ffprobe -version` and `uv --version`. If they all run (they will for anyone set up with watchgabe.com/prompt), go on.
If something is missing on a Mac: Homebrew first (no Homebrew: give them the one install command from brew.sh to paste into
Terminal, and wait), then `brew install ffmpeg-full uv`. Uninstall plain ffmpeg first if it's there, then
`brew link --overwrite --force ffmpeg-full`. Never install plain ffmpeg: it would replace the ffmpeg-full their editing setup uses.

## 1 · Which folder are we doing?
Ask in one line, no question card: **"Which footage are we sorting? Click the + below, choose Add folder, pick the folder, then type go and
press Enter."** (In Claude Code in a terminal there's no +: "drag the folder into this window and press Enter.")
The folder they added shows up as an added working directory in your context; a dragged folder arrives as its path. Neither there?
Ask them to drag it in. Then say in one line what you're scanning, and go on.
- No color questions: this sorts and trims, it never grades. The clips come out with the camera's own color (log stays log).

## 2 · Scan, and their rules while it runs
Start `broll.py scan "<folder>"` in the background (a folder of a few hundred clips takes a few minutes, a whole drive 20-30; say which in one line). While it runs, ask
their rules and where the clips go, in one AskUserQuestion call (four questions):
- **Where should the finished clips go?** First option, the default: `B-Roll Library` at the top of the same drive
  (`/Volumes/<drive>/B-Roll Library`, or next to the footage folder if it's on this Mac), described as "a new folder, sorted inside
  by what's in each clip". Second: a `B-Roll` folder inside the footage folder they added. "Other": they add any folder with the +
  (Add folder) or paste a path. Then `broll.py config --library "<that folder>"`.
- **Looking at the camera:** Never (classic B-roll) / A glance is fine / Prefer it (vlog feel)
- **Feel:** Clean B-roll (no gear or setup) / Behind the scenes welcome / Your call, clip by clip
- **Part length:** About 10 s (6-15) / Short cutaways (3-5 s) / Long stretches (15-30 s)
Don't ask about talking: B-roll never keeps someone talking to camera, so add `"talking_to_camera": "Skip it"` yourself.
Save the answers to `~/B-Roll Sorter/rules.json`. Every reviewer below gets them word for word.

## 3 · They pick (they never type anything to move on)
When the scan is done, start `broll.py serve picks` **in the background** (it opens the picker in Chrome from a small local server on
this Mac and finishes the moment they press Save: no download, no save box), then end your turn with
three lines: each strip is 4 frames of a clip; tick every clip with B-roll worth keeping ("Camera originals only" is on, so exports
and edits are hidden); press **Save picks for Claude** when done, and you'll take it from there by yourself.
When `serve picks` finishes, the picks are in `~/B-Roll Sorter/picks.json` ({root, picks}): go straight on, no check-in. 20-40 clips is a
good first run; if they picked over 80, say in one line it will take a while and use a lot of Claude usage, then go on with all of
them unless they stop you. (If the server couldn't start or they say they saved but nothing came, the page falls back to a download: run `broll.py wait picks`.)

## 4 · Prep
`broll.py prep ~/B-Roll\ Sorter/picks.json`: light preview copies and an overview sheet per clip. Then it writes
batches of about 20 clips to `~/B-Roll Sorter/pass/todoN.json`.

## 5 · Your first pass (two stages, subagents in parallel)
Overview sheets are too small to judge eyes; that is why there are two stages. Use the Agent tool, one agent per batch, all at once.

**Stage A, candidates**, for each `todoN.json`:
> Find candidate B-roll stretches. Input: `<todoN.json>` ({p, sheet, dur, step}). Each sheet is a grid read left to right, top to
> bottom; the yellow label on each frame is its exact time. Read EVERY sheet. The person's rules: `<rules.json, verbatim>`. Never pick
> setup at the top of a take, reaching toward the camera, or whip pans and blur. Per clip propose up to 4 non-overlapping stretches,
> each a little longer than the final part length (so a close-up check can trim), best first, inside 0..dur, or none if nothing can
> work. Write `pass/candN.json`: [{"p", "cands": [[start, end]], "feel", "note"}]. Write no other file.

Then `broll.py detail` (close-up sheets: 2 frames a second, bigger frames, for every candidate) → `pass/verifyN.json`.

**Stage B, close-up check**, for each `verifyN.json`:
> Strict close-up check. Input: `<verifyN.json>` ({p, n, a, b, sheet}) and `pass/candN.json` (feel, note). The rules:
> `<rules.json, verbatim>`. Read EVERY sheet; for each frame decide whether it breaks a rule (if the rule is "never look at the
> camera": a face turned to the lens with eyes up at it counts, even for half a second; eyes on a laptop, notebook or phone don't;
> when a face is tiny, cut rather than guess). Trim each candidate to its longest clean run, 0.5 s inside the first and last bad
> frame; keep it only if it fits the part length. Per clip keep the best 1-3 parts, no overlaps, and never split one continuous moment into back-to-back parts (that is one part, up to the length cap, unless what is in shot changes). Also name each part for the library:
> a **folder** (what kind of shot: Desk & Work, Writing, Walking, Travel, City, Nature, Food, Gym, Home, People, Details...; reuse
> the same names across clips) and a **name** in sentence case, 3-6 words of what's in it ("Typing at the window desk").
> Write `pass/doneN.json`: [{"p", "keep": [[in, out]], "skip": bool, "why": "<feel: what's in it; what you cut>", "folder",
> "names": ["...", ...] (one per part)}]. Every clip from the batch, including ones with no candidates (skip, with the reason).

Check the results yourself before going on: every `p` present, parts inside the clip, no overlaps. Look at two or three close-up
sheets against what was kept.

## 6 · They review (again, no typing to move on)
`broll.py build`, then start `broll.py serve edits` **in the background** (opens the review window, finishes when they press Done) and end your turn with four short lines:
- Your picks are the green blocks under each clip: drag the middle to move one, drag an edge to trim, click ✕ to drop it; I and O mark a new one.
- Notes are for anything else ("call it X", "put it in Travel").
- "Skip this clip" if none of it is any good.
- Press **Done: save for Claude** and I'll export everything by myself.

## 7 · Export
When `serve edits` finishes, read `~/B-Roll Sorter/edits.json` (if it fell back to a download: `broll.py wait edits`) ({clips: [{path, keep, notes, skip, by, claude}]}). Build `~/B-Roll Sorter/plan.json`:
one entry per kept part, `{"src", "in", "out", "folder", "name": "<name> (<source file stem>)"}`, taking folder and
names from `firstpass.json` and following anything in their notes (rename, a different folder, drop a part). A part they added gets
a folder and name from what the clip is. Then `broll.py export plan.json` (HEVC 10-bit at full resolution, color untouched,
every file checked: starts at 0 and its first frame isn't black). Fix anything marked CHECK (move the start off a
dark frame by 0.5 s and export that part again) before saying it's done.

`broll.py export` opens the library folder in Finder when it's done. Finish with: how many clips in how many folders, the library
as a clickable link (`[B-Roll Library](file:///Volumes/...)`, spaces as %20), and one line on what to do next (drag the folder into their
editor, or run this again on another drive: clips they've already exported won't be overwritten).

## Rules that came from real runs
- Never grade or add a LUT, even when asked mid-run: say in one line that grading is theirs to do in their editor (Gabe, 2026-10-30).
- Log footage looks flat and grey on the sheets. Judge it the same; flat is not dull.
- Small frames hide eye contact. Always the second stage.
- Their edits win: a clip they changed is never overwritten by a later pass.
