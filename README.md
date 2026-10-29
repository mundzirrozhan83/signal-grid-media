# Signal Grid media

Public media for the Signal Grid page, written each evening by the Signal Grid Bot.

- `media/YYYY-MM-DD/` — the day's post video (sg-…-1.mp4) and pictures (sg-…-2.png, sg-…-3.png). Kept for 14 days.
- `claimed.json` — stories the Signal Grid Bot has claimed in the last 7 days. The n8n news workflow reads it so both bots never post the same story.
- `kit/render.py` — the renderer that draws the pictures and the 15-second video in code (headless Chromium + ffmpeg). Each post can carry its own illustration of the story ("art" in the spec, an .svg drawn by the bot). Fonts: Archivo and IBM Plex (SIL Open Font License, see kit/fonts).

History is squashed on every run to keep the repo small.
