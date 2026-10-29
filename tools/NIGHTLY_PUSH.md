# Nightly Signal Grid media push

Jay asked for this on 22 Oct 2026 as the permanent fix for missing Signal Grid media. The Signal Grid Bot's scheduled sessions cannot push to this repo. A one-shot scheduled message wakes Jay's Claude chat, which can push, at about 9:15pm Malaysia time each night (after the bot's 8:41pm run). Run every step without asking.

1. With ArtifactData, query the Control Centre (url https://claude.ai/artifact/EJGfHFYuJQ25SrneDVWnAC), collection "posts". Find every post created in the last 2 days with status "draft", media_url "" and a non-empty preview_url.
   If there are none: check the "activity" collection for a Signal Grid Bot row from today. If the bot has not reported yet and this wake-up is not already "RETRY 2", use send_later to send the same wake-up message again in 20 minutes, starting with "RETRY 1" (or "RETRY 2" after RETRY 1). Otherwise go to step 9 and stay quiet (no message to Jay).
2. For each post, download its preview with the Artifact tool (action "read", url = the Control Centre, path = the preview_url without "/_blob/").
3. This repo is already fresh, because the wake-up step fetched it. Write a manifest JSON with one entry per post: {doc_id, file (the downloaded asset), headline, source_url (sources[0]), slot, created_at}. From the repo root, run: python3 tools/push_media.py <manifest>.
4. Check that every printed URL returns HTTP 200 (use curl).
5. Run one ArtifactData batch with each write pinned to the version you read: set media_url to the new URL, and remove a leading "⚠️ NO MEDIA LINK – " from the headline, keeping the rest of the headline exactly as written.
6. If a Signal Grid Bot approval exists for these posts with a title starting "Media not uploaded", set executed to true. Do not touch its status.
7. Add one row to the "activity" collection: bot "Media Pusher", bot_id "media-pusher", kind "done" or "error", a 1-sentence message, at = now.
8. Send Jay one short SendUserMessage: "✅ Tonight's Signal Grid media is attached: N posts are ready to Post (the video is for 10pm)". If anything failed, send "⚠️ Signal Grid media push failed: <reason>" and say what you tried.
9. KEEP THE QUEUE FULL, every run, even quiet ones. Use list_triggers (enabled true) to find the scheduled tasks named "Signal Grid media push YYYY-MM-DD". Make sure one exists for each of the next 14 nights. Create any missing ones with send_later: at = that date 13:15 UTC, name = "Signal Grid media push <date>", initiation "human_request", message = the standard wake-up text below with <date> filled in.

Standard wake-up text:
"NIGHTLY SIGNAL GRID MEDIA PUSH for <date> (Jay's standing request from 22 Oct 2026). Without asking: refresh /home/claude/signal-grid-media (git fetch --depth 1 origin main and git reset --hard origin/main, or git clone --depth 1 https://github.com/mundzirrozhan83/signal-grid-media there if it is missing), then follow tools/NIGHTLY_PUSH.md in that repo exactly. If the repo or that file cannot be read, still do this: find Control Centre posts (https://claude.ai/artifact/EJGfHFYuJQ25SrneDVWnAC) that are drafts with empty media_url and a preview_url, download the previews, push them to media/<date>/<doc_id>.<ext> in the repo, fill media_url, and tell Jay the result."
