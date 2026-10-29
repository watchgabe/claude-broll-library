# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""broll.py: the tools behind the B-roll Library skill. Run with `uv run broll.py <command>` (uv installs Pillow on first run).

  config  [--lut PATH] [--library DIR]   what the run uses: the LUT for log footage, where finished clips go
  scan    <folder>                       every video under <folder>: a 4-frame strip each, and the picker page (scan.html)
  prep    <picks.json>                   the clips they picked: light preview copies, log or not, LUT-graded previews, overview sheets
  detail                                 close-up sheets (2 frames a second) for every candidate stretch in pass/candN.json
  build                                  Claude's checked picks (pass/doneN.json) into the review window (build.html)
  export  <plan.json>                    the finished clips, graded where they need it, sorted into the library, each one checked
  open    <page>                         open scan.html or build.html in the browser
  wait    picks|edits                    wait for the page's Save button (the file it downloads), copy it into the work folder, exit

Everything it makes lives in the work folder (~/B-Roll Sorter, or $BROLL_WORK). The footage is only ever read, never moved or changed.
"""
import argparse, concurrent.futures as cf, hashlib, json, math, os, pathlib, platform, re, shutil, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
WORK = pathlib.Path(os.environ.get("BROLL_WORK") or pathlib.Path.home() / "B-Roll Sorter")
VID = {".mp4", ".mov", ".m4v", ".mxf", ".mts", ".avi"}
MAC = platform.system() == "Darwin"
CAM = re.compile(r"^(C\d{4}|IMG_\d+|DJI_\d+|GX\d+|GH\d+|GOPR\d+|DSC\d+|MVI_\d+|A\d{3}C\d+|PXL_|VID_|\d{8}_\d{6}|[0-9a-f]{32}|[0-9A-F-]{36})", re.I)
LOG_SAT, LOG_SPREAD = .16, .70      # a frame this washed out and flat is log footage (when the camera didn't say)

def say(*a): print(*a, flush=True)
def kid(p): return hashlib.md5(str(p).encode()).hexdigest()[:16]
def cfg():
    f = WORK / "config.json"
    return json.loads(f.read_text()) if f.exists() else {}
def run(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, **kw)
def enc_h264(): return ["-c:v", "h264_videotoolbox", "-b:v", "2500k"] if MAC else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "24"]
def enc_final(): return (["-c:v", "hevc_videotoolbox", "-b:v", "50M", "-profile:v", "main10"] if MAC else ["-c:v", "libx265", "-crf", "16", "-preset", "medium"])
def lut_filter(lut): return "lut3d=file='" + lut.replace("\\", "/").replace(":", "\\:").replace("'", "\\'") + "'"

def probe(p):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration:stream=width,height,codec_name,pix_fmt:stream_side_data=rotation", "-of", "json", str(p)], timeout=60)
    d = json.loads(r.stdout or "{}"); s = (d.get("streams") or [{}])[0]; w, h = s.get("width"), s.get("height")
    rot = next((abs(int(x.get("rotation", 0))) for x in s.get("side_data_list", []) if "rotation" in x), 0)
    if rot in (90, 270) and w: w, h = h, w
    return float((d.get("format") or {}).get("duration") or 0), w, h

def labelled_grid(frames, times, out, font_px):
    from PIL import Image, ImageDraw, ImageFont
    try: font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc" if MAC else "arial.ttf", font_px)
    except Exception: font = ImageFont.load_default()
    w, h = Image.open(frames[0]).size; cols = 6 if w > h else 10; rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGB", (cols * w, rows * h)); dr = ImageDraw.Draw(sheet)
    for j, (f, t) in enumerate(zip(frames, times)):
        x, y = j % cols * w, j // cols * h; sheet.paste(Image.open(f).convert("RGB"), (x, y))
        dr.rectangle([x, y, x + font_px * 3.6, y + font_px + 6], fill="black"); dr.text((x + 4, y + 2), f"{int(t // 60)}:{t % 60:04.1f}", fill="yellow", font=font)
    sheet.save(out, quality=80)

def fill(template, out, **data):
    s = (HERE / "pages" / template).read_text()
    for k, v in data.items(): s = s.replace(f"/*{k}*/null", json.dumps(v).replace("</", "<\\/"))
    (WORK / out).write_text(s); return WORK / out

# ------------------------------------------------------------------ config
def c_config(a):
    WORK.mkdir(parents=True, exist_ok=True); c = cfg()
    if a.lut is not None:
        if a.lut and not pathlib.Path(a.lut).is_file(): sys.exit(f"No LUT at {a.lut}")
        c["lut"] = a.lut
    if a.library: c["library"] = str(pathlib.Path(a.library).expanduser())
    (WORK / "config.json").write_text(json.dumps(c, indent=1)); say(json.dumps(c, indent=1))

# ------------------------------------------------------------------ scan
def c_scan(a):
    root = pathlib.Path(a.folder).expanduser().resolve(); (WORK / "strips").mkdir(parents=True, exist_ok=True)
    lib = cfg().get("library")
    def skip(p):
        rel = p.relative_to(root).parts
        return any(x.startswith(".") or x.startswith("._") for x in rel) or (lib and str(p).startswith(lib)) or str(p).startswith(str(WORK))
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".") and not d.startswith("$") and d != "System Volume Information"]
        for f in fns:
            p = pathlib.Path(dp) / f
            if p.suffix.lower() in VID and not skip(p): files.append(p)
    say(f"{len(files)} videos under {root}. Making a 4-frame strip of each (about 2 a second)...")
    def one(p):
        k = kid(p); out = WORK / "strips" / f"{k}.jpg"
        try: st = p.stat(); dur, w, h = probe(p)
        except Exception: return None
        if dur <= 0 or not w: return None      # sidecars and fragments with no picture
        if not out.exists():
            from PIL import Image
            fr = []
            with tempfile.TemporaryDirectory() as td:
                for i, frac in enumerate((.1, .37, .63, .9)):
                    t = pathlib.Path(td) / f"{i}.jpg"
                    run(["ffmpeg", "-v", "error", "-y", "-skip_frame", "nokey", "-noaccurate_seek", "-ss", f"{dur * frac:.2f}", "-i", str(p), "-frames:v", "1",
                         "-vf", "scale=-2:180,format=yuvj420p", "-q:v", "5", str(t)], timeout=120)
                    if t.exists(): fr.append(Image.open(t).convert("RGB"))
                if fr:
                    im = Image.new("RGB", (sum(i.width for i in fr), 180)); x = 0
                    for i in fr: im.paste(i, (x, 0)); x += i.width
                    im.save(out, quality=72)
        rel = str(p.relative_to(root))
        return {"p": str(p), "rel": rel, "folder": str(pathlib.Path(rel).parent), "top": rel.split(os.sep)[0] if os.sep in rel else ".", "dur": round(dur, 1),
                "w": w, "h": h, "size": st.st_size, "mtime": int(st.st_mtime), "strip": f"strips/{k}.jpg" if out.exists() else "", "cam": bool(CAM.match(p.stem))}
    res, t0 = [], time.time()
    with cf.ThreadPoolExecutor(8) as ex:
        for n, r in enumerate(ex.map(one, files), 1):
            if r: res.append(r)
            if n % 100 == 0: say(f"  {n}/{len(files)} ({time.time() - t0:.0f} s)")
    data = {"root": str(root), "when": time.strftime("%b %-d, %-I:%M %p") if MAC else time.strftime("%b %d, %H:%M"), "items": res}
    (WORK / "scan.json").write_text(json.dumps(data))
    page = fill("scan.html", "scan.html", DATA=data)
    say(f"Done: {len(res)} clips with a picture, {sum(1 for r in res if r['cam'])} straight off a camera. Page: {page}")

# ------------------------------------------------------------------ prep
def gamma(p):
    try:
        with open(p, "rb") as f:
            head = f.read(3_000_000); f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 3_000_000)); tail = f.read()
        m = re.search(rb'CaptureGammaEquation" value="([^"]+)"', head + tail)      # Sony writes its picture profile into the file
        return m.group(1).decode() if m else ""
    except OSError: return ""

def flatness(p, dur):
    sat, spread = [], []
    for fr in (.2, .5, .8):
        b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * fr:.2f}", "-i", str(p), "-frames:v", "1", "-vf", "scale=96:96", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        if len(b) < 96 * 96 * 3: continue
        ss, ys = 0.0, []
        for i in range(0, 96 * 96 * 3, 3):
            R, G, B = b[i] / 255, b[i + 1] / 255, b[i + 2] / 255; mx, mn = max(R, G, B), min(R, G, B)
            ss += (mx - mn) / max(mx, 1e-3); ys.append(.2126 * R + .7152 * G + .0722 * B)
        ys.sort(); sat.append(ss / (96 * 96)); spread.append(ys[int(len(ys) * .98)] - ys[int(len(ys) * .02)])
    return (sum(sat) / len(sat), sum(spread) / len(spread)) if sat else (None, None)

def c_prep(a):
    picks = json.loads(pathlib.Path(a.picks).expanduser().read_text()); picks = picks.get("picks", picks) if isinstance(picks, dict) else picks
    picks = [p for p in picks if pathlib.Path(p).is_file()]
    lut = cfg().get("lut") or ""
    for d in ("proxies", "graded", "sheets", "pass"): (WORK / d).mkdir(parents=True, exist_ok=True)
    say(f"{len(picks)} picks. Making light preview copies to scrub (the slow part: a 4K clip takes about as long as it plays, 3 at a time)...")
    def one(p):
        k = kid(p); px = WORK / "proxies" / f"{k}.mp4"
        dur, w, h = probe(p)
        if not px.exists():
            tmp = px.with_suffix(".part.mp4")
            run(["ffmpeg", "-v", "error", "-y", "-i", p, "-map", "0:v:0", "-map", "0:a:0?", "-vf", "scale=-2:540,format=yuv420p", *enc_h264(), "-g", "12",
                 "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp)])
            if tmp.exists(): tmp.rename(px)
        g = gamma(p); s, sp = flatness(p, dur)
        log = ("log" in g.lower()) if g else (s is not None and s < LOG_SAT and sp < LOG_SPREAD)
        gr = WORK / "graded" / f"{k}.mp4"
        if log and lut and px.exists() and not gr.exists():
            tmp = gr.with_suffix(".part.mp4")
            run(["ffmpeg", "-v", "error", "-y", "-i", str(px), "-map", "0:v:0", "-map", "0:a:0?", "-vf", f"{lut_filter(lut)},format=yuv420p", *enc_h264(), "-g", "12",
                 "-c:a", "copy", "-movflags", "+faststart", str(tmp)])
            if tmp.exists(): tmp.rename(gr)
        view = gr if gr.exists() else px      # what Claude looks at: the clip as it will look
        sh = WORK / "sheets" / f"{k}.jpg"; d2 = probe(view)[0] or dur; step = max(1.0, d2 / 60)
        if not sh.exists():
            with tempfile.TemporaryDirectory() as td:
                run(["ffmpeg", "-v", "error", "-i", str(view), "-vf", f"fps=1/{step},scale=256:-2", "-q:v", "4", f"{td}/f%04d.jpg"])
                fr = sorted(pathlib.Path(td).glob("f*.jpg"))
                if fr: labelled_grid(fr, [j * step for j in range(len(fr))], sh, 18)
        return {"p": p, "dur": round(dur, 2), "step": round(step, 2), "sheet": str(sh), "gamma": g, "log": log,
                "proxy": f"proxies/{k}.mp4" if px.exists() else "", "graded": f"graded/{k}.mp4" if gr.exists() else ""}
    res, t0 = [], time.time()
    with cf.ThreadPoolExecutor(3) as ex:
        for n, r in enumerate(ex.map(one, picks), 1):
            res.append(r); say(f"  {n}/{len(picks)} ({time.time() - t0:.0f} s) {pathlib.Path(r['p']).name}: {r['gamma'] or ('log' if r['log'] else 'no profile')}")
    (WORK / "picks.json").write_text(json.dumps(res, indent=1))
    nb = max(1, math.ceil(len(res) / 20))
    for b in range(nb): (WORK / "pass" / f"todo{b + 1}.json").write_text(json.dumps([{"i": i + 1, **{k: r[k] for k in ("p", "sheet", "dur", "step")}} for i, r in enumerate(res) if i % nb == b], indent=1))
    say(f"Ready for Claude's first look: {nb} batch(es) in {WORK / 'pass'} (todo1.json ...). {sum(r['log'] for r in res)} log clips get the LUT" + ("" if lut else " once a LUT is set") + ".")

# ------------------------------------------------------------------ detail
def c_detail(a):
    picks = {r["p"]: r for r in json.loads((WORK / "picks.json").read_text())}; (WORK / "pass" / "detail").mkdir(parents=True, exist_ok=True)
    jobs = []
    for f in sorted((WORK / "pass").glob("cand*.json")):
        b = re.sub(r"\D", "", f.stem)
        for c in json.loads(f.read_text()):
            for n, (s, e) in enumerate(c.get("cands", [])): jobs.append((b, c["p"], n, float(s), float(e)))
    def one(j):
        b, p, n, s, e = j; r = picks[p]; view = WORK / (r["graded"] or r["proxy"]); out = WORK / "pass" / "detail" / f"{kid(p)}_{n}.jpg"
        with tempfile.TemporaryDirectory() as td:
            run(["ffmpeg", "-v", "error", "-ss", f"{s:.2f}", "-i", str(view), "-t", f"{e - s:.2f}", "-vf", "fps=2,scale=448:-2", "-q:v", "4", f"{td}/f%04d.jpg"])
            fr = sorted(pathlib.Path(td).glob("f*.jpg"))
            if fr: labelled_grid(fr, [s + i * .5 for i in range(len(fr))], out, 20)
        return {"batch": b, "p": p, "n": n, "a": s, "b": e, "sheet": str(out) if out.exists() else ""}
    with cf.ThreadPoolExecutor(8) as ex: res = list(ex.map(one, jobs))
    for b in sorted({r["batch"] for r in res}): (WORK / "pass" / f"verify{b}.json").write_text(json.dumps([r for r in res if r["batch"] == b], indent=1))
    say(f"{len(res)} close-up sheets for {len({r['p'] for r in res})} clips: {WORK / 'pass'}/verifyN.json")

# ------------------------------------------------------------------ build
def c_build(a):
    picks = json.loads((WORK / "picks.json").read_text()); first = {}
    for f in sorted((WORK / "pass").glob("done*.json")):
        for r in json.loads(f.read_text()):
            d = next((x["dur"] for x in picks if x["p"] == r["p"]), 0)
            ks = sorted([max(0, float(s)), min(d, float(e))] for s, e in r.get("keep", []))
            ks = [[round(s, 1), round(e, 1)] for s, e in ks if e - s >= 1]
            first[r["p"]] = {"keep": ks, "skip": bool(r.get("skip")) or not ks, "why": r.get("why", ""), "folder": r.get("folder", ""), "names": r.get("names", [])}
    (WORK / "firstpass.json").write_text(json.dumps(first, indent=1))
    scan = json.loads((WORK / "scan.json").read_text()) if (WORK / "scan.json").exists() else {"items": []}
    strips = {i["p"]: i["strip"] for i in scan["items"]}
    meta = {r["p"]: {"dur": r["dur"], "proxy": r["proxy"], "graded": r["graded"], "strip": strips.get(r["p"], ""), "gamma": r["gamma"], "log": r["log"]} for r in picks}
    page = fill("build.html", "build.html", PICKS=[r["p"] for r in picks], META=meta, FIRST=first)
    say(f"{sum(len(v['keep']) for v in first.values())} parts across {sum(1 for v in first.values() if not v['skip'])} clips, {sum(v['skip'] for v in first.values())} skipped. Page: {page}")

# ------------------------------------------------------------------ export
def c_export(a):
    plan = json.loads(pathlib.Path(a.plan).expanduser().read_text()); lut = cfg().get("lut") or ""
    lib = pathlib.Path(cfg().get("library") or (WORK / "Library")); made = []
    def dest(folder, name):
        clean = lambda s: re.sub(r'[\\/:*?"<>|]+', "-", s).strip(" .") or "Clip"
        d = lib / clean(folder or "Unsorted"); d.mkdir(parents=True, exist_ok=True); o = d / f"{clean(name)}.mp4"; n = 2
        while o.exists(): o = d / f"{clean(name)} ({n}).mp4"; n += 1      # never over an existing file
        return o
    def one(c):
        src, s, e = c["src"], float(c["in"]), float(c["out"]); out = dest(c.get("folder"), c.get("name") or pathlib.Path(src).stem)
        vf = (f"{lut_filter(lut)}," if c.get("lut") and lut else "") + "setpts=PTS-STARTPTS,format=yuv420p10le"
        r = run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s:.3f}", "-i", src, "-t", f"{e - s:.3f}", "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf, "-af", "asetpts=PTS-STARTPTS",
                 *enc_final(), "-bf", "0", "-tag:v", "hvc1", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
        if r.returncode: return {"out": str(out), "ok": False, "why": r.stderr[-300:]}
        st = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=start_time", "-of", "csv=p=0", str(out)]).stdout.strip()
        b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-frames:v", "1", "-vf", "scale=64:36", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
        bright = sum(b) / max(1, len(b))
        ok = abs(float(st or 0)) < 0.001 and bright > 12      # starts at 0 with a picture you can see: never a black thumbnail
        ql = None
        if MAC:      # and the thumbnail Finder itself will show
            with tempfile.TemporaryDirectory() as td:
                run(["qlmanage", "-t", "-s", "200", "-o", td, str(out)], timeout=60)
                pngs = list(pathlib.Path(td).glob("*.png"))
                if pngs:
                    from PIL import Image, ImageStat
                    ql = round(ImageStat.Stat(Image.open(pngs[0]).convert("L")).mean[0], 1); ok = ok and ql > 12
        return {"out": str(out), "ok": ok, "start": st, "first_frame_brightness": round(bright, 1), "finder_thumbnail": ql, "src": src, "in": s, "out_s": e}
    with cf.ThreadPoolExecutor(2) as ex:
        for n, r in enumerate(ex.map(one, plan), 1):
            made.append(r); say(f"  {n}/{len(plan)} {'ok ' if r['ok'] else 'CHECK'} {r['out']}" + ("" if r["ok"] else f"  ({r.get('why') or 'start ' + str(r.get('start')) + ', first frame ' + str(r.get('first_frame_brightness'))})"))
    (WORK / "export_log.json").write_text(json.dumps(made, indent=1))
    say(f"{sum(r['ok'] for r in made)} of {len(made)} clips in {lib}" + ("" if all(r["ok"] for r in made) else ". Fix the ones marked CHECK before saying it's done."))

def c_open(a):
    p = WORK / a.page
    if not p.exists(): sys.exit(f"No {p} yet")
    if MAC:
        chrome = pathlib.Path("/Applications/Google Chrome.app")
        subprocess.run(["open", "-a", "Google Chrome", str(p)] if chrome.exists() else ["open", str(p)])
    elif platform.system() == "Windows": os.startfile(str(p))
    else: subprocess.run(["xdg-open", str(p)])
    (WORK / f".opened-{a.page}").write_text(str(time.time()))
    say(f"Opened {p}")

def download_dirs():
    dirs = [pathlib.Path.home() / "Downloads"]      # and wherever Chrome was told to save
    sup = pathlib.Path.home() / ("Library/Application Support/Google/Chrome" if MAC else ".config/google-chrome")
    for pref in sup.glob("*/Preferences"):
        try:
            d = json.loads(pref.read_text(errors="ignore")).get("download", {}).get("default_directory")
            if d and pathlib.Path(d).is_dir(): dirs.append(pathlib.Path(d))
        except (OSError, ValueError): pass
    return list(dict.fromkeys(dirs))

def c_wait(a):
    page = "scan.html" if a.kind == "picks" else "build.html"
    mark = WORK / f".opened-{page}"
    since = float(mark.read_text()) if mark.exists() else time.time()
    dirs, t0, n = download_dirs(), time.time(), 0
    say(f"Waiting for the {page} Save button (looking in {', '.join(str(d) for d in dirs)})...")
    while time.time() - t0 < 4 * 3600:
        found = [f for d in dirs for f in d.glob(f"broll-{a.kind}*.json")]
        if MAC and n % 8 == 0:      # saved somewhere else: Spotlight finds it
            r = run(["mdfind", "-onlyin", str(pathlib.Path.home()), f"kMDItemFSName == 'broll-{a.kind}*.json'"], timeout=30)
            found += [pathlib.Path(x) for x in r.stdout.splitlines() if x.strip()]
        found = [f for f in found if f.is_file() and f.stat().st_mtime > since - 2]
        if found:
            f = max(found, key=lambda f: f.stat().st_mtime)
            try: data = json.loads(f.read_text())
            except ValueError: time.sleep(1); continue      # still being written
            (WORK / f"{a.kind}.json").write_text(json.dumps(data, indent=1))
            got = len(data.get("picks") or data.get("clips") or [])
            say(f"Saved: {got} clips, from {f}. Copied to {WORK / (a.kind + '.json')}"); return
        n += 1; time.sleep(2)
    sys.exit(f"Nothing saved from {page} in 4 hours. Ask them to press its Save button, or where Chrome saved broll-{a.kind}.json.")

if __name__ == "__main__":
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"): sys.exit("ffmpeg isn't installed. Install it first (Mac: brew install ffmpeg).")
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    x = sp.add_parser("config"); x.add_argument("--lut"); x.add_argument("--library")
    x = sp.add_parser("scan"); x.add_argument("folder")
    x = sp.add_parser("prep"); x.add_argument("picks")
    sp.add_parser("detail"); sp.add_parser("build")
    x = sp.add_parser("export"); x.add_argument("plan")
    x = sp.add_parser("open"); x.add_argument("page")
    x = sp.add_parser("wait"); x.add_argument("kind", choices=["picks", "edits"])
    a = ap.parse_args(); WORK.mkdir(parents=True, exist_ok=True)
    {"config": c_config, "scan": c_scan, "prep": c_prep, "detail": c_detail, "build": c_build, "export": c_export, "open": c_open, "wait": c_wait}[a.cmd](a)
