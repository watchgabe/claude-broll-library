# Your B-roll, sorted by Claude

Point Claude at your footage. It shows you every clip as a filmstrip, you tick the ones with B-roll, and Claude finds the best
moments in each (never you staring into the lens, unless you want that), lets you check and adjust them, then cuts them
from the originals and sorts them into folders: Desk & Work, Travel, Gym, City... Your original files are never moved or changed, and the color is left as you shot it, for you to grade your way.

You need: a Mac, Google Chrome, the Claude app (Code tab) or Claude Code, and your footage on this Mac or a plugged-in drive.

The easiest way in: **https://watchgabe.com/broll** (the same prompt, with a copy button).

## 1 · Paste this into Claude Code

```
Set me up to sort my B-roll library, then run it. Do everything yourself and only stop for my answers.

1. First ask me one question: have I already set up AI video editing with Claude (the prompt from watchgabe.com/prompt)? If yes, check that ffmpeg, ffprobe, uv and git all run, and if they do, skip to step 3. If no, or if anything is missing, do step 2.

2. Check for Homebrew. If it's missing, give me the one command to paste into Terminal and wait for me, then make sure brew runs in your own shell (add /opt/homebrew/bin to my shell profile if it doesn't). Install ffmpeg-full, uv and git with Homebrew. If plain ffmpeg is installed, uninstall it first. ffmpeg-full is keg-only, so link it with brew link --overwrite --force ffmpeg-full and confirm ffmpeg -version and ffprobe -version both work. Never install plain ffmpeg.

3. Clone https://github.com/watchgabe/claude-broll-library into ~/Developer/claude-broll-library (or pull it if it's already there), and copy its skills/broll-library folder into ~/.claude/skills/broll-library so it's there in every session.

4. Follow ~/.claude/skills/broll-library/SKILL.md from the top.
```

If you've already set up AI video editing, it skips the installs. Then it asks which drive and which folder to do, and scans it: a few minutes for a folder, 20-30 for a whole drive.

## 2 · Pick

A page opens in Chrome with every clip as a 4-frame strip. Tick the ones with B-roll and press **Save picks for Claude**.
That's it: Claude carries on by itself. Start with 20-40 clips.

## 3 · Review

While the scan runs, Claude asks four quick questions (looking at the camera? clean or behind-the-scenes? talking? how long?).
After you pick, it finds the best parts by itself
and opens a review window. Drag the green blocks to move or trim them, delete the ones you don't want,
then press **Done: save for Claude**. Claude exports everything by itself.

## 4 · Done

Your clips land in the library folder, sorted by what's in them, named by what's in them, and checked one by one.
Next time just say: **"Sort my B-roll"**.
