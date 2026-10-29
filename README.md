# Your B-roll, sorted by Claude

Point Claude at your footage. It shows you every clip as a filmstrip, you tick the ones with B-roll, and Claude finds the best
moments in each (never you staring into the lens, unless you want that), lets you check and adjust them, then exports them
color graded and sorted into folders: Desk & Work, Travel, Gym, City... Your original files are never moved or changed.

You need: a Mac, Google Chrome, the Claude app (Code tab) or Claude Code, and your footage on this Mac or a plugged-in drive.

## 1 · Paste this into Claude Code

```
Install the B-roll Library skill from https://github.com/watchgabe/claude-broll-library and run it for me.

1. Clone the repo into ~/Developer/claude-broll-library (or pull it if it's already there).
2. Copy skills/broll-library into ~/.claude/skills/broll-library so it's there in every session.
3. Check ffmpeg and uv. If either is missing, install them with Homebrew (brew install ffmpeg uv). If Homebrew is missing, give me
   the one command to paste into Terminal and wait for me.
4. Then follow ~/.claude/skills/broll-library/SKILL.md from the top. Do everything yourself and only stop for my answers.
```

It asks you three things (where your footage is, where the library should go, and whether you shoot log), then scans. A big drive
takes 20-30 minutes the first time.

## 2 · Pick

A page opens in Chrome with every clip as a 4-frame strip. Tick the ones with B-roll, press **Save picks for Claude**, and tell
Claude "picks saved". Start with 20-40 clips.

## 3 · Review

Claude asks four quick questions (looking at the camera? clean or behind-the-scenes? talking? how long?), finds the best parts,
and opens a review window. Drag the green blocks to move or trim them, delete the ones you don't want, flip between LUT and No LUT,
then press **Done: save for Claude** and tell Claude "edits saved".

## 4 · Done

Your clips land in the library folder, sorted by what's in them, named by what's in them, and checked one by one.
Next time just say: **"Sort my B-roll"**.

---

Already set up AI video editing with the editing prompt? This is the second half: that one edits what you say, this one builds the
B-roll library it cuts to.
