#!/usr/bin/env python3
"""Signal Grid media kit: renders branded post images and short news videos in code.

  python3 render.py image spec.json out.png
  python3 render.py video spec.json out.mp4

Image spec: {"layout": "headline" | "stat", "kicker": "AI CHIPS", "headline": "...",
             "stat": "500 MW", "stat_label": "...", "points": ["...", "..."],
             "source": "Reuters", "context": "Not released yet"}
Video spec: {"kicker": "...", "hook": "...", "beats": [{"big": "...", "small": "...", "art": "beat.svg"} x3],
             "why": "...", "source": "...", "art": "story.svg"}

"art" (optional, image and video; also per beat in a video): path to an illustration of THIS story's subject,
relative to the spec file or absolute. An .svg file is drawn inline (draw it on a transparent background in the
Signal Grid palette: #0B0817 ink, #5B21B6 / #7C3AED / #8B5CF6 / #A78BFA / #C4B5FD violets, #F5F3FF highlights);
a .png / .jpg / .webp file is shown as a picture. Images put the art in a hero band above the headline; videos
show it above the words in every scene, and a beat with its own "art" swaps to it for that beat.

Everything is drawn from HTML/CSS by headless Chromium (Playwright) and encoded by ffmpeg.
Every video frame is a pure function of its frame number, so a re-render is identical.
"""
import json, os, subprocess, sys, tempfile, html

KIT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(KIT, "fonts")

LOGO = """<svg viewBox="20 20 160 130" aria-hidden="true">
<polygon points="30,80 100,120 100,136 30,96" fill="#3B2A86"/><polygon points="100,120 170,80 170,96 100,136" fill="#21175A"/>
<polygon points="100,40 170,80 100,120 30,80" fill="#1A1240" stroke="#A78BFA" stroke-width="3" stroke-linejoin="round"/>
<polyline points="44,64 78,64 90,36 108,92 120,64 156,64" fill="none" stroke="#A78BFA" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
<polyline points="44,64 78,64 90,36 108,92 120,64 156,64" fill="none" stroke="#F5F3FF" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

BASE_CSS = f"""
@font-face {{ font-family: Archivo; src: url('file://{FONTS}/archivo.woff2') format('woff2'); font-weight: 100 900; font-stretch: 62% 125%; }}
@font-face {{ font-family: Plex; src: url('file://{FONTS}/ibm-plex-sans-latin-400-normal.woff2'); font-weight: 400; }}
@font-face {{ font-family: Plex; src: url('file://{FONTS}/ibm-plex-sans-latin-500-normal.woff2'); font-weight: 500; }}
@font-face {{ font-family: Plex; src: url('file://{FONTS}/ibm-plex-sans-latin-600-normal.woff2'); font-weight: 600; }}
@font-face {{ font-family: PlexMono; src: url('file://{FONTS}/ibm-plex-mono-latin-600-normal.woff2'); font-weight: 600; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 100%; height: 100%; overflow: hidden; }}
body {{ background: #0B0817; color: #F5F3FF; font-family: Plex, sans-serif; -webkit-font-smoothing: antialiased; }}
.grid {{ position: absolute; inset: 0; background-image: linear-gradient(rgba(167,139,250,.07) 1px, transparent 1px), linear-gradient(90deg, rgba(167,139,250,.07) 1px, transparent 1px); background-size: 54px 54px; }}
.glow {{ position: absolute; border-radius: 50%; filter: blur(120px); }}
.brand {{ display: flex; align-items: center; gap: 18px; }}
.brand svg {{ width: 74px; height: 62px; }}
.brand b {{ font: 800 34px/1 Archivo; font-stretch: 118%; letter-spacing: .06em; }}
.kicker {{ font: 600 26px/1 PlexMono; letter-spacing: .16em; text-transform: uppercase; color: #C4B5FD; padding: 12px 18px; border: 2px solid rgba(196,181,253,.45); border-radius: 999px; }}
.mono {{ font-family: PlexMono; letter-spacing: .08em; text-transform: uppercase; }}
"""

FIT_JS = """
function fit(el, maxPx, minPx, maxH) {
  let s = maxPx; el.style.fontSize = s + 'px';
  while (s > minPx && el.scrollHeight > maxH) { s -= 2; el.style.fontSize = s + 'px'; }
}
"""

def esc(s):
    return html.escape(str(s or ""))

import base64, re
def art_html(path, base_dir, cls="art"):
    """Inline an .svg, or embed a raster image as a data URI. Returns '' when there is no usable file."""
    if not path:
        return ""
    full = path if os.path.isabs(path) else os.path.join(base_dir, path)
    if not os.path.isfile(full):
        print("warning: art not found:", full, file=sys.stderr)
        return ""
    ext = os.path.splitext(full)[1].lower()
    if ext == ".svg":
        svg = open(full, encoding="utf-8").read()
        svg = re.sub(r"<\?xml[^>]*>|<!DOCTYPE[^>]*>", "", svg)
        svg = re.sub(r"<script.*?</script>", "", svg, flags=re.S | re.I)
        return f'<div class="{cls}">{svg}</div>'
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext)
    if not mime:
        print("warning: unsupported art type:", full, file=sys.stderr)
        return ""
    data = base64.b64encode(open(full, "rb").read()).decode()
    return f'<div class="{cls}"><img src="data:{mime};base64,{data}" alt=""></div>'

def pulse_svg(width, cls="pulse"):
    return f"""<svg class="{cls}" viewBox="0 0 1000 120" preserveAspectRatio="none" style="width:{width}px;height:120px">
<polyline points="0,60 380,60 430,10 500,110 550,60 1000,60" fill="none" stroke="#7C3AED" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" opacity=".55"/>
<polyline points="0,60 380,60 430,10 500,110 550,60 1000,60" fill="none" stroke="#EDE9FE" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>"""

# ---------------------------------------------------------------- image
def image_html(spec, base_dir="."):
    art = art_html(spec.get("art"), base_dir)
    layout = spec.get("layout", "headline")
    if layout == "stat" and not spec.get("stat"):
        layout = "headline"
    points = [p for p in (spec.get("points") or []) if str(p).strip()][:3]
    pts = "".join(f'<li><span class="dot"></span><span>{esc(p)}</span></li>' for p in points)
    ctx = f'<div class="ctx"><span class="mono">Context</span> {esc(spec.get("context"))}</div>' if spec.get("context") else ""
    if layout == "stat":
        middle = f"""<div class="stat" id="stat">{esc(spec.get('stat'))}</div>
<div class="statlabel">{esc(spec.get('stat_label'))}</div>
<h1 id="h" class="small">{esc(spec.get('headline'))}</h1>"""
    else:
        middle = f"""<h1 id="h">{esc(spec.get('headline'))}</h1>"""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}
body {{ width: 1080px; height: 1350px; }}
.wrap {{ position: absolute; inset: 0; padding: 72px 76px 64px; display: flex; flex-direction: column; }}
.top {{ display: flex; justify-content: space-between; align-items: center; }}
.mid {{ flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 28px; min-height: 0; }}
h1 {{ font: 800 92px/1.02 Archivo; font-stretch: 112%; letter-spacing: -.01em; max-height: 560px; overflow: hidden; text-wrap: balance; }}
h1.small {{ font-size: 56px; font-weight: 700; color: #EDE9FE; max-height: 260px; }}
.stat {{ display: inline-block; align-self: flex-start; font: 900 220px/0.9 Archivo; font-stretch: 125%; color: #C4B5FD; letter-spacing: -.02em; white-space: nowrap; }}
.statlabel {{ font: 600 30px/1.3 PlexMono; color: #A78BFA; letter-spacing: .1em; text-transform: uppercase; }}
ul {{ list-style: none; display: grid; gap: 18px; }}
li {{ display: grid; grid-template-columns: 22px 1fr; gap: 18px; font: 500 34px/1.35 Plex; color: #DDD6FE; }}
.dot {{ width: 14px; height: 14px; margin-top: 15px; border-radius: 3px; background: #8B5CF6; transform: rotate(45deg); }}
.pulse {{ display: block; margin: 6px 0 4px -76px; }}
.foot {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 30px; border-top: 2px solid rgba(167,139,250,.25); padding-top: 26px; }}
.src {{ font: 600 24px/1.3 PlexMono; letter-spacing: .1em; text-transform: uppercase; color: #A78BFA; }}
.ctx {{ font: 400 26px/1.35 Plex; color: #C4B5FD; max-width: 640px; }}
.ctx .mono {{ font-size: 20px; color: #8B5CF6; margin-right: 8px; }}
.art {{ height: 470px; display: flex; align-items: center; justify-content: center; margin: 22px 0 6px; }}
.art svg, .art img {{ max-width: 100%; max-height: 100%; width: auto; height: 100%; display: block; object-fit: contain; }}
.art img {{ border-radius: 22px; }}
body.has-art h1 {{ font-size: 72px; max-height: 250px; }}
body.has-art h1.small {{ font-size: 46px; max-height: 120px; }}
body.has-art .stat {{ font-size: 150px; }}
body.has-art .mid {{ gap: 18px; justify-content: flex-start; padding-top: 10px; }}
body.has-art li {{ font-size: 30px; }}
body.has-art .pulse {{ height: 60px !important; margin-top: 0; margin-bottom: 0; }}
</style></head><body class="{'has-art' if art else ''}">
<div class="grid"></div>
<div class="glow" style="width:760px;height:760px;left:-260px;top:-220px;background:#5B21B6;opacity:.55"></div>
<div class="glow" style="width:620px;height:620px;right:-240px;bottom:-200px;background:#7C3AED;opacity:.35"></div>
<div class="wrap">
  <div class="top"><div class="brand">{LOGO}<b>SIGNAL GRID</b></div><div class="kicker">{esc(spec.get('kicker') or 'AI & TECH')}</div></div>
  {art}
  <div class="mid">{middle}{pulse_svg(1080)}<ul>{pts}</ul></div>
  <div class="foot">{ctx or '<div></div>'}<div class="src">Source<br>{esc(spec.get('source'))}</div></div>
</div>
<script>{FIT_JS}
function layout() {{
const h = document.getElementById('h'); const A = document.body.classList.contains('has-art');
const small = h.classList.contains('small');
fit(h, small ? (A ? 46 : 56) : (A ? 76 : 96), A ? 36 : 44, small ? (A ? 120 : 260) : (A ? 250 : 560));
const st = document.getElementById('stat'); if (st) {{ let s = A ? 150 : 220; while (s > 90 && st.getBoundingClientRect().width > 928) {{ s -= 6; st.style.fontSize = s + 'px'; }} }}
}}
</script></body></html>"""

def render_image(spec, out, base_dir="."):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp:
        page_path = os.path.join(tmp, "card.html")
        open(page_path, "w").write(image_html(spec, base_dir))
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1080, "height": 1350})
            pg.goto("file://" + page_path)
            pg.evaluate("document.fonts.ready.then(() => layout())")
            pg.wait_for_timeout(150)
            pg.screenshot(path=out, type="png")
            b.close()

# ---------------------------------------------------------------- video
FPS, SECONDS, W, H = 30, 15, 1080, 1920

def video_html(spec, base_dir="."):
    beats = (spec.get("beats") or [])[:3]
    while len(beats) < 3:
        beats.append({"big": "", "small": ""})
    main_art = art_html(spec.get("art"), base_dir, "art")
    beat_arts = [art_html(b.get("art"), base_dir, "art") for b in beats]
    has_art = bool(main_art or any(beat_arts))
    # art layers: 0 = story art (hook, why, beats without their own), 1..3 = per-beat art
    art_layers = (f'<div class="artl" id="a0">{main_art}</div>' if main_art else "") + "".join(
        f'<div class="artl" id="a{i+1}">{a}</div>' for i, a in enumerate(beat_arts) if a)
    beat_divs = "".join(
        f'<div class="beat" id="b{i}"><div class="mask"><div class="big" id="bb{i}">{esc(b.get("big"))}</div></div>'
        f'<div class="mask"><div class="small" id="bs{i}">{esc(b.get("small"))}</div></div></div>' for i, b in enumerate(beats))
    data = json.dumps({"beats": len([b for b in beats if b.get("big")]), "art": has_art, "main": bool(main_art),
                       "beatArt": [bool(a) for a in beat_arts]})
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}
body {{ width: {W}px; height: {H}px; }}
.layer {{ position: absolute; inset: 0; }}
.top {{ position: absolute; left: 80px; right: 80px; top: 150px; display: flex; justify-content: space-between; align-items: center; }}
.scene {{ position: absolute; left: 80px; right: 80px; top: 470px; height: 900px; display: flex; flex-direction: column; justify-content: center; }}
.mask {{ overflow: hidden; padding-bottom: 8px; }}
#hook {{ font: 800 118px/1.0 Archivo; font-stretch: 110%; letter-spacing: -.01em; text-wrap: balance; }}
.beat {{ position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: center; gap: 26px; }}
.big {{ font: 900 150px/0.95 Archivo; font-stretch: 120%; color: #C4B5FD; letter-spacing: -.02em; text-wrap: balance; }}
.small {{ font: 500 50px/1.3 Plex; color: #EDE9FE; text-wrap: balance; }}
#why {{ position: absolute; inset: 0; display: flex; flex-direction: column; justify-content: center; gap: 30px; }}
#whyk {{ font: 600 34px/1 PlexMono; letter-spacing: .16em; color: #A78BFA; text-transform: uppercase; }}
#whyt {{ font: 700 84px/1.08 Archivo; font-stretch: 108%; text-wrap: balance; }}
#pulsewrap {{ position: absolute; left: 0; width: {W}px; height: 120px; }}
#end {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 34px; text-align: center; }}
#end svg {{ width: 300px; height: 244px; }}
#endname {{ font: 900 96px/1 Archivo; font-stretch: 125%; letter-spacing: .05em; }}
#endcta {{ font: 500 44px/1.3 Plex; color: #DDD6FE; }}
#src {{ position: absolute; left: 80px; right: 80px; bottom: 210px; font: 600 28px/1.3 PlexMono; letter-spacing: .1em; color: #A78BFA; text-transform: uppercase; }}
#bar {{ position: absolute; left: 80px; bottom: 170px; height: 6px; border-radius: 3px; background: #8B5CF6; }}
.artl {{ position: absolute; left: 80px; right: 80px; top: 300px; height: 660px; display: flex; align-items: center; justify-content: center; opacity: 0; }}
.artl .art {{ width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }}
.artl svg, .artl img {{ max-width: 100%; max-height: 100%; width: auto; height: 100%; display: block; object-fit: contain; }}
.artl img {{ border-radius: 28px; }}
body.has-art .scene {{ top: 1000px; height: 640px; }}
</style></head><body class="{'has-art' if has_art else ''}">
<div class="grid" id="grid"></div>
<div class="glow" id="g1" style="width:900px;height:900px;background:#5B21B6;opacity:.55"></div>
<div class="glow" id="g2" style="width:700px;height:700px;background:#7C3AED;opacity:.35"></div>
<div class="top" id="top"><div class="brand">{LOGO}<b>SIGNAL GRID</b></div><div class="kicker">{esc(spec.get('kicker') or 'AI & TECH')}</div></div>
{art_layers}
<div id="pulsewrap">{pulse_svg(W, "pl")}</div>
<div class="scene">
  <div class="mask" id="hookm"><div id="hook">{esc(spec.get('hook'))}</div></div>
  {beat_divs}
  <div id="why"><div class="mask"><div id="whyk">Why it matters</div></div><div class="mask"><div id="whyt">{esc(spec.get('why'))}</div></div></div>
</div>
<div id="end">{LOGO}<div id="endname">SIGNAL GRID</div><div id="endcta">Follow for the AI &amp; tech news<br>that actually matters</div></div>
<div id="src">Source: {esc(spec.get('source'))}</div>
<div id="bar"></div>
<script>{FIT_JS}
const D = {data};
function layout() {{
if (D.art) {{
fit(document.getElementById('hook'), 100, 56, 600);
for (let i = 0; i < 3; i++) {{ fit(document.getElementById('bb' + i), 130, 60, 330); fit(document.getElementById('bs' + i), 48, 32, 230); }}
fit(document.getElementById('whyt'), 74, 44, 520);
}} else {{
fit(document.getElementById('hook'), 124, 70, 860);
for (let i = 0; i < 3; i++) {{ fit(document.getElementById('bb' + i), 160, 70, 520); fit(document.getElementById('bs' + i), 52, 34, 300); }}
fit(document.getElementById('whyt'), 88, 52, 700);
}}
}}
const $ = id => document.getElementById(id);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const eo = x => 1 - Math.pow(1 - clamp(x), 3);           // ease out: arrive slowly enough to read
const ei = x => Math.pow(clamp(x), 3);                   // ease in: leave fast
const prog = (t, a, b) => clamp((t - a) / (b - a));
// timeline (seconds)
const T = {{ hookOut: 2.9, beats: [[3.0, 5.2], [5.3, 7.5], [7.6, 9.8]], why: [9.9, 12.3], end: 12.4, total: {SECONDS} }};
function reveal(el, t, a, b, out) {{   // masked type: rises in, leaves upward fast
  const i = eo(prog(t, a, a + 0.45)), o = out ? ei(prog(t, out - 0.3, out)) : 0;
  el.style.transform = `translateY(${{(1 - i) * 110 - o * 110}}%)`;
  el.style.opacity = i * (1 - o);
}}
function render(t) {{
  // background breathes (micro-motion on every hold)
  $('g1').style.left = (-300 + 60 * Math.sin(t * .5)) + 'px'; $('g1').style.top = (-200 + 40 * Math.cos(t * .4)) + 'px';
  $('g2').style.right = (-260 + 50 * Math.cos(t * .6)) + 'px'; $('g2').style.bottom = (-160 + 40 * Math.sin(t * .5)) + 'px';
  $('grid').style.backgroundPosition = `0 ${{-t * 12}}px`;
  // the signal pulse carries the film: it sits under the hook, then becomes each beat's divider, then the end card's floor
  const py = D.art ? (t < T.end ? 920 : 1500) : (t < T.hookOut ? 1340 : t < T.end ? 1290 : 1500);
  const handoff = t < T.hookOut ? 0 : t < T.end ? eo(prog(t, T.hookOut, T.hookOut + .4)) : eo(prog(t, T.end, T.end + .5));
  const fromY = D.art ? (t < T.end ? 920 : 920) : (t < T.end ? 1340 : 1290);
  $('pulsewrap').style.top = (fromY + (py - fromY) * handoff) + 'px';
  const pl = document.querySelector('.pl');
  const sweep = (t * 0.55) % 1;  // pulse travels left to right forever
  pl.style.transform = `translateX(${{(sweep - 0.5) * 120}}px) scaleY(${{1 + 0.18 * Math.sin(t * 6)}})`;
  // hook: finished picture at frame 0 (works as a still), small settle, exits on a beat
  const hs = 1.04 - 0.04 * eo(prog(t, 0, .8));
  $('hook').style.transform = `scale(${{hs}}) translateY(${{-ei(prog(t, T.hookOut - .3, T.hookOut)) * 115}}%)`;
  $('hook').style.transformOrigin = 'left center';
  $('hook').style.opacity = 1 - ei(prog(t, T.hookOut - .3, T.hookOut));
  // beats
  T.beats.forEach(([a, b], i) => {{
    const on = i < D.beats && t >= a - .01 && t < b + .01;
    $('b' + i).style.visibility = on ? 'visible' : 'hidden';
    if (on) {{ reveal($('bb' + i), t, a, b, b); reveal($('bs' + i), t, a + .18, b, b);
      $('bb' + i).style.letterSpacing = (-0.02 + 0.01 * eo(prog(t, a, b))) + 'em'; }}
  }});
  const [wa, wb] = T.why; const won = t >= wa - .01 && t < wb + .01;
  $('why').style.visibility = won ? 'visible' : 'hidden';
  if (won) {{ reveal($('whyk'), t, wa, wb, wb); reveal($('whyt'), t, wa + .15, wb, wb); }}
  // art: the story's picture holds the top half; a beat with its own art swaps to it, everything fades for the end card
  if (D.art) {{
    const fadeEnd = 1 - eo(prog(t, T.end - .3, T.end + .2));
    const beatO = T.beats.map(([a, b], i) => D.beatArt[i] ? eo(prog(t, a - .25, a + .15)) * (1 - ei(prog(t, b - .15, b + .1))) : 0);
    const anyBeat = Math.max(0, ...beatO);
    const firstBeat = D.beatArt.indexOf(true);
    document.querySelectorAll('.artl').forEach(l => {{
      const n = +l.id.slice(1);
      let o = n === 0 ? 1 - anyBeat : beatO[n - 1];
      if (!D.main && n === firstBeat + 1 && anyBeat === 0) o = 1;   // no story art: hold the first beat's art
      l.style.opacity = o * fadeEnd;
      l.style.transform = `translateY(${{8 * Math.sin(t * .9)}}px) scale(${{1 + 0.04 * clamp(t / T.total)}})`;   // slow push-in
    }});
  }}
  // end card
  const e = eo(prog(t, T.end, T.end + .6));
  $('end').style.opacity = e; $('end').style.transform = `translateY(${{(1 - e) * 60}}px) scale(${{0.96 + 0.04 * e + 0.006 * Math.sin(t * 2)}})`;
  $('top').style.opacity = 1 - eo(prog(t, T.end - .2, T.end + .3));
  $('src').style.opacity = 1 - eo(prog(t, T.end - .2, T.end + .3));
  $('bar').style.width = (920 * clamp(t / T.total)) + 'px';
}}
render(0);
</script></body></html>"""

def audio_track(path):
    """Quiet synth bed + one soft whoosh per scene change, mixed to about -14 LUFS."""
    cuts = [2.9, 5.2, 7.5, 9.8, 12.3]
    pad = ("aevalsrc='0.20*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.25*t))+0.14*sin(2*PI*164.8*t)*(0.6+0.4*sin(2*PI*0.18*t+1))"
           "+0.08*sin(2*PI*220*t)*(0.5+0.5*sin(2*PI*2*t))':s=48000:d=%d" % SECONDS)
    gate = "+".join(f"between(t,{c-0.25:.2f},{c+0.35:.2f})*sin(PI*(t-{c-0.25:.2f})/0.6)" for c in cuts)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "lavfi", "-i", pad,
           "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.6:d={SECONDS}:r=48000",
           "-filter_complex",
           f"[1]volume='{gate}':eval=frame,highpass=f=400,lowpass=f=3500[w];"
           f"[0]lowpass=f=900,afade=t=in:d=0.4,afade=t=out:st={SECONDS-1.2}:d=1.2[p];"
           "[p][w]amix=inputs=2:weights='1 0.5':normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
           "-map", "[a]", "-ac", "2", "-c:a", "aac", "-b:a", "160k", path]
    subprocess.run(cmd, check=True)

def render_video(spec, out, base_dir="."):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp:
        page_path = os.path.join(tmp, "film.html")
        open(page_path, "w").write(video_html(spec, base_dir))
        frames = os.path.join(tmp, "f")
        os.makedirs(frames)
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.goto("file://" + page_path)
            pg.evaluate("document.fonts.ready.then(() => { layout(); render(0); })")
            pg.wait_for_timeout(200)
            for f in range(FPS * SECONDS):
                pg.evaluate(f"render({f / FPS})")
                pg.screenshot(path=os.path.join(frames, f"{f:04d}.jpg"), type="jpeg", quality=92)
            b.close()
        audio = os.path.join(tmp, "a.m4a")
        audio_track(audio)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(frames, "%04d.jpg"),
                        "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                        "-c:a", "copy", "-shortest", "-movflags", "+faststart", out], check=True)

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("image", "video"):
        sys.exit(__doc__)
    spec = json.load(open(sys.argv[2]))
    base = os.path.dirname(os.path.abspath(sys.argv[2]))
    (render_image if sys.argv[1] == "image" else render_video)(spec, sys.argv[3], base)
    print("wrote", sys.argv[3], os.path.getsize(sys.argv[3]), "bytes")
