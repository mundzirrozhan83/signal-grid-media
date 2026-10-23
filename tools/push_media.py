#!/usr/bin/env python3
"""Signal Grid media pusher.

Run from the repo root by the nightly "Signal Grid media push" step, which has
GitHub push access (the Signal Grid Bot's own scheduled sessions do not).

Input: a manifest JSON file, a list of
  {"doc_id": "sg-2026-10-22-pm-1", "file": "/path/to/downloaded/asset.mp4",
   "headline": "...", "source_url": "...", "slot": "22:00", "created_at": ISO}
For each entry it copies the file to media/<date>/<doc_id>.<ext>, adds the story
to claimed.json (kept 7 days), deletes media folders older than 14 days, makes one
orphan commit and force-pushes main. It prints {doc_id: public_url} as JSON.

Usage: python3 tools/push_media.py manifest.json [--no-push]
"""
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys

RAW = "https://raw.githubusercontent.com/mundzirrozhan83/signal-grid-media/main/"
STOP = set("""a an the and or but of to in on for with at by from as is are was were be been
its it this that these those into over after before about than more most new now says say
first two three after will can could has have had not no out up""".split())


def keywords(headline):
    words = re.findall(r"[a-z0-9$][a-z0-9$.\-]*", headline.lower())
    out = []
    for w in words:
        w = w.strip(".-")
        if len(w) > 2 and w not in STOP and w not in out:
            out.append(w)
    return out[:7]


def main():
    manifest = json.load(open(sys.argv[1]))
    push = "--no-push" not in sys.argv
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    urls = {}

    claimed_path = "claimed.json"
    claimed = json.load(open(claimed_path)) if os.path.exists(claimed_path) else {"stories": []}
    cutoff7 = (now - dt.timedelta(days=7)).isoformat()
    stories = [s for s in claimed.get("stories", []) if s.get("claimed_at", "") >= cutoff7]
    known = {s.get("url") for s in stories}

    for e in manifest:
        m = re.match(r"sg-(\d{4}-\d{2}-\d{2})", e["doc_id"])
        if not m:
            raise SystemExit(f"bad doc_id {e['doc_id']}")
        day = m.group(1)
        ext = os.path.splitext(e["file"])[1].lower() or ".bin"
        rel = f"media/{day}/{e['doc_id']}{ext}"
        os.makedirs(os.path.dirname(rel), exist_ok=True)
        shutil.copyfile(e["file"], rel)
        urls[e["doc_id"]] = RAW + rel
        if e.get("source_url") and e["source_url"] not in known:
            stories.append({
                "url": e["source_url"],
                "headline": re.sub(r"^\W*NO MEDIA LINK\s*[–-]\s*", "", e.get("headline", "")).strip(),
                "keywords": keywords(e.get("headline", "")),
                "claimed_at": e.get("created_at") or now.isoformat(),
                "slot": e.get("slot", ""),
            })
            known.add(e["source_url"])

    claimed = {"updated_at": now.isoformat(), "stories": stories}
    json.dump(claimed, open(claimed_path, "w"), indent=2, ensure_ascii=False)

    cutoff14 = (now - dt.timedelta(days=14)).date().isoformat()
    for d in os.listdir("media"):
        if re.match(r"\d{4}-\d{2}-\d{2}$", d) and d < cutoff14:
            shutil.rmtree(os.path.join("media", d))

    if push:
        def git(*a):
            subprocess.run(["git", *a], check=True)
        git("config", "user.email", "noreply@anthropic.com")
        git("config", "user.name", "Claude")
        git("fetch", "-q", "--depth", "1", "origin", "main")
        git("checkout", "-q", "--orphan", "tmp")
        git("add", "-A")
        git("commit", "-q", "-m", f"Signal Grid media {now.date().isoformat()} (nightly push)")
        git("branch", "-D", "main")
        git("branch", "-m", "main")
        git("push", "-q", "-f", "origin", "main")
    print(json.dumps(urls, indent=2))


if __name__ == "__main__":
    main()
