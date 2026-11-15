# Operations guide

Running, watching, troubleshooting and demoing Arjun on a Windows laptop (the current deployment), plus pointers for
Docker and the cloud. Short companion: [RUNBOOK.md](RUNBOOK.md) (the day-to-day cheat sheet).

Contents: [Starting and stopping](#starting-and-stopping) · [Health checks](#health-checks) · [Logs](#logs) ·
[Elder device](#the-elder-device) · [Phone and tunnel](#phone-and-tunnel) · [Telegram, calls, voice cloning](#optional-integrations) ·
[Troubleshooting](#troubleshooting-by-symptom) · [Backups and data](#data-backups-and-reset) ·
[Pre-demo checklist](#pre-demo-checklist) · [Docker and cloud](#docker-and-cloud) · [Costs and limits](#costs-quotas-and-limits)

## Starting and stopping

```powershell
cd D:\Arjun
scripts\dev-up.ps1                    # all services, in order, one window each
scripts\dev-up.ps1 -Only voice-agent  # restart one service
scripts\dev-up.ps1 -Phone             # + Cloudflare quick tunnel and phone links (needs ARJUN_ACCESS_CODE)
```
Order and ports: core-api **:8000** → reasoning **:8001** → scheduler → voice-agent (**:8002** helper) → web
**:5173**. The script waits for core-api and reasoning to answer `/health`, then starts the rest, then prints
`BASE_URL ok: <url> (HTTP n)` (retrying about 30 s while the web server comes up).

**Stop** = close the `arjun …` PowerShell windows (each service lives in its own window). Every new PowerShell
window starts in `C:\WINDOWS\system32`: `cd` to the repo first. Running `dev-up.ps1` twice can leave **duplicate
windows/workers**; two voice workers both register as `arjun` and split jobs. Close the old window first.

First time only: `.venv\Scripts\python scripts\seed_heerabai.py --apply` (demo user "Aaji", user 1) and optionally
`scripts\seed_apps.py --apply` (family links).

### URLs
| What | URL |
|---|---|
| Elder screen | http://localhost:5173/?user=1 (tap-to-talk test mode: `&handsfree=0`) |
| Family dashboard | http://localhost:5173/?view=family&user=1 (redirects to `/family-dashboard`) |
| core-api docs / reasoning docs | http://127.0.0.1:8000/docs · http://127.0.0.1:8001/docs |

## Health checks

```powershell
foreach($u in 'http://127.0.0.1:8000/health','http://127.0.0.1:8001/health'){ Invoke-RestMethod $u }   # status ok
Get-NetTCPConnection -State Listen -LocalPort 8000,8001,8002,5173 | Select LocalPort,OwningProcess
Select-String logs\voice-agent.log -Pattern 'registered worker' | Select -Last 1                      # worker registered with LiveKit
```
Reasoning `/health` also shows `llm_configured`, `llm_provider`, `llm_model`, `ask_before_acting`. The voice worker is
healthy when its log ends with `registered worker {"agent_name": "arjun", ... "region": "..."}`; it is **not** an
HTTP service you can curl for health (port 8002 only serves the briefing helper).

`Test-NetConnection <your-livekit-host> -Port 443` checks the route to LiveKit when sessions will not start.

## Logs

| File | What |
|---|---|
| `logs\core-api.log`, `reasoning.log`, `scheduler.log`, `web.log` | per-service output from `dev-up.ps1` |
| `logs\voice-agent.log` | worker stdout (LiveKit agent logs, tracebacks, FFI panics) |
| `logs\voice-agent.app.log` | our own lines: `voice:` step lines (lengths, language, timings; **never the words**), TTS choice, errors |
| `logs\tunnel.log` | Cloudflare tunnel output (the URL) |
| `eval\results\turns.jsonl` | one JSON timing line per turn (read by `scripts\voice_report.py` / `voice_latency_report.py`) |

```powershell
Get-Content logs\voice-agent.app.log -Tail 60
Get-Content logs\voice-agent.log -Tail 40 -Wait
```
Logs are git-ignored and contain no secrets. Reasoning logs one JSON trace line per turn (user id, intent, route,
timings), not text.

### Reading the `voice:` lines (`ARJUN_DEBUG_VOICE=1`, default)
| You see | Meaning | Try |
|---|---|---|
| no `user listening -> speaking` | no speech detected | Chrome mic icon: right microphone, not muted; one tab only |
| `speaking` but "Prisma returned no words" | STT returned nothing | valid `GNANI_API_KEY`; try `GNANI_STT_IMPL=v3` |
| `stt final: N chars` but no `turn -> reasoning` | words ignored (video playing / family in room / held fragment) | speak a full sentence; stop the video |
| `turn -> reasoning` but no `turn answered` | reasoning down or slow | reasoning window/log; `/health` |
| `reply voice: ...` but nothing heard | TTS or speaker | `error detail:` line; volume; tap the page once |
| `cloned voice synthesis failed (...)` | Arjun spoke in its own voice | the bracket says why |
| `held for more speech` | a sentence ending in आणि/पण/की is waiting | wait ~4 s or finish the sentence |
| `ignored_media` | media mode dropped it | say "अर्जुन" first |
| `family_in_room: Arjun stays quiet` | a family member is in the room | expected |

## The elder device

* Dedicated, always-open device (a tablet/old phone or the laptop): proactive speech (reminders, medicine prompts)
  needs it because **browsers block audio until a tap**. On Windows use `scripts\elder-kiosk.ps1` (full-screen,
  autoplay allowed in its own Chrome profile; asks once for the microphone). Use it only on the elder's own device.
* The page connects by itself and keeps listening (hands-free): `ARJUN_IDLE_CLOSE_S=0` means the session never
  closes on its own. Always-on cost in Gnani credits is **unmeasured**; `60` restores an idle close.
* One tab only. Two tabs = two sessions fighting for the mic.
* Language of the screen is chosen by the page/profile; each spoken reply follows the language of the turn.
* Elder UI rules (large text, one decision per screen, no timeouts) are in [SERVICES.md](SERVICES.md#web).

## Phone and tunnel

A phone needs HTTPS for the microphone. Set `ARJUN_ACCESS_CODE` (6+ chars) in `.env`, then `scripts\dev-up.ps1 -Phone`:

1. Starts the stack, then a Cloudflare quick tunnel to :5173 (own window, output in `logs\tunnel.log`).
2. Waits up to 30 s for `https://<random>.trycloudflare.com`, writes it to `BASE_URL` (only that line changes), and
   restarts core-api so family-call links use it. If a tunnel is already running and answers 200 it is reused.
3. Prints the two links, **with the code**: elder `…/?user=1&k=<code>`, family `…/?view=family&user=1&k=<code>`.
4. First open swaps the code for a 12 h HttpOnly cookie and removes `k` from the address bar.

Notes: the tunnel address changes on every start; use the freshly printed links. "हा दुवा चालत नाही" = old/wrong link
or an elder link used for the family view. A core-api restart clears its room map (open the elder URL once before a
family-call test). Close the "arjun tunnel" window when finished. A Tailscale Funnel (`*.ts.net`) is also allowed by the
dev server and works as a stable `BASE_URL`. Synthetic data only.

## Optional integrations

* **Telegram** (family alerts, join-call button, voice briefings): create a bot with @BotFather, put
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ENABLED=1`, and a working non-quick-tunnel `BASE_URL`. Test:
  `scripts\telegram_test.py` or `POST /users/{id}/alert/test`. core-api logs `BASE_URL ok/unreachable/quick-tunnel` at startup.
* **Emergency auto-calls**: `CALLS_ENABLED=1`, `TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM`. The family fills **Emergency
  settings** (help number, label, address, call-family switch) in the dashboard. Trial Twilio accounts call only
  verified numbers. **Untested with a real call.** Arjun never dials 112.
* **Voice cloning**: set `VOICE_CLONE_KEY` (Fernet; **never change it later**). Dashboard → Family & memories → A
  familiar voice. Record 20–30 s of the person speaking **Marathi** in a quiet room; consent text is recorded. If
  Marathi sounds Hindi-like set `ARJUN_CLONED_VOICE_LANGUAGES=hi,en`. `ARJUN_CLONED_VOICE=0` disables use. Hearing a
  cloned reply is **not yet live-verified**.
* **YouTube**: `YOUTUBE_API_KEY` in `.env`, restart core-api. Without it a search opens the results page. Daily cap 80
  uncached searches.
* **Family accounts**: `ARJUN_AUTH=1` + `ARJUN_SIGNUP_CODE`; the dashboard opens on a login/sign-up page; the first
  account owns existing elders.
* **Apps/links**: dashboard → "Apps and links" (https only; an unknown website needs an explicit tick and shows a
  warning). WhatsApp opens her chat; she taps the green button herself.

## Troubleshooting by symptom

| Symptom | Likely cause → fix |
|---|---|
| **Arjun never speaks / never joins** | The voice worker is not running (check `Get-CimInstance Win32_Process` for `agent.py`, or the log for `registered worker`). Restart `-Only voice-agent`, then **reload the page** (new room). |
| Worker died after `FFI Panic: invalid request: timed out waiting for ReadyForRoomEventRequest` | The connection to LiveKit dropped (Wi-Fi, VPN/proxy, antivirus HTTPS inspection, sleep). Fix the network (`Test-NetConnection … -Port 443`), restart the worker. It is **not** auto-restarted locally. |
| `Failed to export logs batch … Read timed out`, `job shutdown is taking too much time` | Telemetry flush to LiveKit timing out at session end: network trouble, usually harmless on its own. |
| `event loop blocked … ssl.py create_default_context` | A ~2 s SSL context load at startup. Harmless. |
| Worker registered but no job when you tap | The page used an old room, or another worker has the job. One worker, new session, `agent_name` must be `arjun`. LiveKit Console "No agent selected" never dispatches. |
| core-api window closes immediately | `CORE_API_KEY` empty (or `ENV=prod` checks failed: the message names the variables). |
| Dashboard shows nothing / 401 | key not injected: the dashboard must be opened through the web server (:5173), not core-api directly; through a tunnel use the link with `k=`. |
| `429 too many turns` | A stuck recognizer loop; per-user `/turn` limit (2/s, burst 6). Safety text is exempt. |
| Replies are generic fixed lines | No LLM configured (`/health` → `llm_configured: false`), or the LLM timed out / was rate limited (rules answered). Set `SARVAM_API_KEY`. |
| Marathi reply spoken with a Hindi accent or wrong language | Prisma mislabelled; `langid.py` corrects with word evidence. Check `voice:` lines for the detected language. |
| First reply slow | First TTS connection (~1 s) and TLS context; the worker prewarms at startup. |
| TTS error / silence | `Timbre` probe failed → fallback `timbre-v2.5`/`Omkar` is automatic; if both fail check the Gnani key/credits (`scripts\check_gnani.py`). |
| Reminder time passed, nothing spoken | Delivery needs an **open voice session** on the elder device. Check the dashboard delivery status: queued/shown_only/undelivered; `fired` ≠ heard. |
| Medicine says "unconfirmed" | She did not confirm after `max_reminders`; only the family is told. Expected. |
| Telegram alert has no join button | `BASE_URL` empty/unreachable/quick-tunnel (see core-api startup line). |
| Elder page asks to tap | Browser autoplay rule; use the kiosk profile for always-on devices. |
| Video keeps playing but Arjun ignores you | Media mode: say **"अर्जुन"** first, or a bare "थांबव". |
| Port already in use | An old service is still running; close its window or `Get-NetTCPConnection -LocalPort <p>` and stop that process. |
| `tsc`/build fails with browser-speech message | `scripts/check_no_browser_speech.py`: the elder page must not use browser speech. |
| Mic audio reaches the agent but no transcript (2026-11-08, **open**) | See `voice:` lines; try `GNANI_STT_IMPL=v3`, new key, one tab. |

When asking for help, collect: `/health` of both services, `.env` **names** (never values), the tail of
`voice-agent.log` and `voice-agent.app.log`. (`arjun-diagnose.ps1`, if you have it, gathers these with keys removed.)

## Data, backups and reset

* Local data = SQLite `arjun.db` (in `services\core-api`, where `dev-up.ps1` starts core-api). Back it up by copying
  the file while core-api is stopped. `scripts\clean_demo_db.py` (dry run; `--apply` backs up first) resets to one
  synthetic user.
* Postgres in Docker: volume `pgdata`.
* `ensure_columns` adds new columns to old databases at startup; there are **no migrations**, and nothing is dropped
  (a table shaped differently is "set aside").
* Raw audio is never stored. `eval/results/turns.jsonl` holds timings only.

## Pre-demo checklist

Before recording or posting a demo (contest rules: Gnani voice, honest claims, synthetic data):

1. Tests green: core-api, reasoning, voice-agent, scheduler; `ruff check .`; `npx tsc --noEmit`; `npm test`;
   `python eval/run_eval.py`.
2. `/health` on both services; worker registered; `GNANI_TTS_*` and the active voice in `voice-agent.app.log`
   ("TTS active for this session: model=… voice=…") is what you expect.
3. `ARJUN_VOICE_PROVIDER` is `gnani`. No browser speech. A single tab on a dedicated device.
4. Synthetic user only (`seed_heerabai.py`); no real numbers or recordings. Consenting relative on camera is open
   question 5.
5. **External distress test set (T12) passed** (required before any public demo). Lexicons are still
   native-speaker-unverified; say so.
6. Disclose: speech in = Gnani Prisma, speech out = Gnani Timbre, conversation LLM = Sarvam-105B (non-Gnani),
   Evon not used. Report **system** results, not WER (EULA 16).
7. Stable network (wired if possible): a drop kills the local worker. Do a full tap-to-talk dry run: reminder set,
   read back, undo, "aaj kay aahe", medicine list, help request, safety phrase, a story.
8. Telegram/Twilio: enable only what you can verify; otherwise say "not enabled" (never imply a call was made).
9. Keep the family dashboard open to show the feed, level and delivery honesty.

## Docker and cloud

* **Docker Compose** (`docker compose up --build`): postgres (pgvector/pg16), core-api :8000, reasoning :8001,
  scheduler, web :5173. **voice-agent is not included**; run it separately against the same `.env`. Change the default
  `CORE_API_KEY` (`dev-change-me`).
* **Cloud** (Vercel web + Railway core-api/reasoning/scheduler/voice-agent, LiveKit Cloud): see
  [DEPLOY_CLOUD.md](DEPLOY_CLOUD.md). **Unverified**: not deployed yet. core-api on SQLite needs a volume and one
  replica; set `ENV=prod` so startup refuses a half-configured service.

## Costs, quotas and limits

| Resource | Limit / note |
|---|---|
| Gnani credits | Prisma stream stays open all day in hands-free mode: **cost per day unmeasured**. `ARJUN_IDLE_CLOSE_S=60` to save |
| Sarvam | 4 concurrent, 60/min, then the rules answer; back-off after a 429; ~4–6 s budget per turn |
| YouTube | search.list = 100 of 10,000 daily units; 24 h cache; 80 uncached searches/day |
| core-api HTTP | 30 req/s per client, burst 60 |
| `/turn` | 2/s per user, burst 6 (safety exempt) |
| Twilio trial | verified numbers only |
| Contest | Deadline per CLAUDE.md: 2026-11-10 23:59 IST (no extensions) |
