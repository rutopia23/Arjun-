# Arjun - a voice care companion for elderly Indians

**One-page pitch: [PITCH.md](PITCH.md)** · **Documentation index: [docs/README.md](docs/README.md)** · Spec: [CLAUDE.md](CLAUDE.md)

Arjun is a voice companion that helps elderly Indians (Marathi, code-mixed, Hindi, English) manage their day and
share life stories just by talking. It has two halves:

- **A reliable assistant**: reminders, today's schedule, medicines, help requests, family calls.
- **A warm listener**: it listens to stories and interests and keeps a private Memory Book.

> **Arjun is a bridge to people, not a replacement for them.** It always says it is an AI, gives no medical advice,
> and never discourages human contact. Built for the Gnani AI "Great Indian AI Internship Challenge".

**Voice stack:** speech in = Gnani **Prisma** (STT), speech out = Gnani **Timbre** (TTS), both through LiveKit.
Open conversation uses a hosted, **non-Gnani** LLM (Sarvam-105B). Care actions, times, medicines, confirmations and
safety are rules plus SQL and never wait for an LLM.

All demo data is synthetic. Never put real phone numbers, Aadhaar/PAN or recorded calls in it.

---

## Contents
1. [How it works](#how-it-works)
2. [Repository layout](#repository-layout)
3. [Hard boundaries](#hard-boundaries-short-version)
4. [Quick start (Windows)](#quick-start-windows)
5. [Configuration](#configuration)
6. [Using the app](#using-the-app)
7. [Running on a phone](#running-on-a-phone)
8. [Docker and cloud](#docker-and-cloud)
9. [Tests and checks](#tests-and-checks)
10. [Troubleshooting](#troubleshooting)
11. [More documentation](#more-documentation)

---

## How it works

```
Elder device (React, one big button)
   -> LiveKit room -> voice-agent (Python worker "arjun")
        -> Gnani Prisma STT
        -> reasoning  POST /turn
             safety rules first (emergency, then distress)
             -> one LLM understanding call (intent, slots, reply)  [rule parser is the fallback]
             -> deterministic, SQL-backed action paths
        -> core-api (FastAPI + SQLAlchemy; SQLite locally, Postgres in Docker)
        -> reply text -> Gnani Timbre TTS -> speaker
scheduler : polls core-api for due reminders, medicines, check-ins, briefings
Family dashboard (React + TS) -> core-api
```

Key idea: **the model chooses the meaning, the code decides the action.** The LLM only *suggests*; core-api validates
and stores everything. Arjun executes at once, reads it back in one line ("ठेवली: उद्या सकाळी 10:00, डॉक्टर.
बदलायचं असेल तर 'नको' म्हणा."), and "नको" within the undo window (reasoning 150 s, core-api 180 s) undoes it.
Missing details (which day, AM or PM) are always asked, never guessed.

| Service | Port | Role |
|---|---|---|
| `core-api` | 8000 | System of record: reminders, appointments, medicines, contacts, stories, wellbeing, alerts, accounts |
| `reasoning` | 8001 | `/turn`: safety checks, understanding, dispatch, companion chat, summaries |
| `voice-agent` | 8002 (worker) | LiveKit worker `arjun`: Prisma in, Timbre out, endpointing, media mode, emergency calls |
| `scheduler` | - | Queues due reminders, medicine prompts, check-ins; fetches briefings |
| `web` | 5173 | Elder app and family dashboard (Vite + React + TypeScript, Tailwind) |

## Repository layout

```
services/core-api/      FastAPI + SQLAlchemy, tests in tests/
services/reasoning/     reasoning_svc: turn pipeline, rules, lexicons, LLM client
services/voice-agent/   LiveKit agent (agent.py) and speech glue
services/scheduler/     scheduler.py
web/                    Vite React app (src/), dev-server proxy and access lock (server/), Vercel functions (api/)
shared/schemas/         schemas shared between services
eval/                   evaluation sets and run_eval.py; results in eval/results/RESULTS.md
scripts/                dev-up.ps1, seeders, token maker, eval and report scripts
deploy/railway/         Railway configs      docs/  RUNBOOK, ENGINEERING, DEPLOY_CLOUD, GNANI_FEATURES, DETAILS
design/                 UI reference only    CLAUDE.md  the project spec and hard boundaries
```

## Hard boundaries (short version)

The full list is in [CLAUDE.md](CLAUDE.md); these are never "improved away":

1. **The LLM never touches the database.** It proposes; core-api validates and acts.
2. **Reminders, appointments, medicines and contacts come from SQL only.** Never from the model's memory.
3. **Never guess.** Ambiguous AM/PM, missing date, or "after the meal" with no meal -> ask.
4. **Arjun is an AI** and says so when asked. It never claims to be human or to have feelings or family.
5. **No medical advice.** Medicines are created by the family only, read back exactly as entered, never by voice.
6. **Safety checks run first on every turn**, rules only, and work with core-api and the LLM down. A physical
   emergency always alerts the family; emotional distress alerts only with consent. Both word lists are
   **unverified** until a native speaker reviews them.
7. **No engagement tricks** (streaks, "I missed you"). Stories are private by default.
8. **Secrets live in ONE root `.env`** (only `.env.example` is tracked). `GNANI_API_KEY` and `LIVEKIT_*` are read
   only by voice-agent, `LLM_API_KEY` / `SARVAM_API_KEY` only by reasoning. Never in React, Git or logs.
9. **Never invent numbers or claim delivery that did not happen.**

---

## Quick start (Windows)

The local stack runs without Docker and uses SQLite. `scripts\dev-up.ps1` is built for Windows PowerShell.

### Prerequisites
- Python **3.12** and Node.js **18+** (with npm)
- Accounts and keys: a **Gnani** API key (Prisma and Timbre), a **LiveKit Cloud** project (URL, API key, secret),
  and optionally a **Sarvam** key for open conversation. Without Sarvam, Arjun still works on rules but
  casual chat falls back to a few fixed lines.

### 1. Install dependencies
From the repo root:
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\pip install -r services\core-api\requirements.txt `
                          -r services\reasoning\requirements.txt `
                          -r services\voice-agent\requirements.txt
.venv\Scripts\pip install httpx tzdata          # scheduler
cd web; npm install; cd ..
```
`dev-up.ps1` expects the venv at `.venv\Scripts\python.exe`.

### 2. Configure `.env`
```powershell
copy .env.example .env
```
Set at least:
```
CORE_API_KEY=<any long random string>      # core-api refuses to start without it
GNANI_API_KEY=<your Gnani key>
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=<livekit key>
LIVEKIT_API_SECRET=<livekit secret>
SARVAM_API_KEY=<optional, turns on open conversation>
```
Check it: `.venv\Scripts\python scripts\check_env.py` (and `scripts\check_gnani.py` for the Gnani key).

### 3. Start everything
```powershell
scripts\dev-up.ps1
```
Starts, in order, each in its own window (logs also go to `logs\`): core-api :8000, reasoning :8001, scheduler,
voice-agent, web :5173. `-Only core-api|reasoning|scheduler|voice-agent|web` starts just one, which is useful to
restart a crashed service.

### 4. Seed the demo user (Aaji, user 1)
```powershell
.venv\Scripts\python scripts\seed_heerabai.py            # dry run
.venv\Scripts\python scripts\seed_heerabai.py --apply    # write it
.venv\Scripts\python scripts\seed_apps.py --apply        # optional: YouTube / news / family links
```

### 5. Open it
| What | URL |
|---|---|
| Elder app | http://localhost:5173/?user=1 |
| Family dashboard | http://localhost:5173/?view=family&user=1 |
| core-api docs | http://127.0.0.1:8000/docs |
| reasoning docs | http://127.0.0.1:8001/docs |

Tap the screen once and allow the microphone: browsers block audio until a tap, and that tap lets Arjun speak.
Each new session creates a fresh LiveKit room and the worker is dispatched to it, so reload the page for a new session.

---

## Configuration

Every variable is listed, with comments, in [.env.example](.env.example). The ones you will touch most:

| Variable | Purpose |
|---|---|
| `CORE_API_KEY` | Shared service secret. Required. |
| `GNANI_API_KEY`, `GNANI_TTS_MODEL`, `GNANI_TTS_VOICE` | Prisma and Timbre (defaults `timbre-v3.0` / `Avinash`, with fallback `timbre-v2.5` / `Omkar`) |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | LiveKit Cloud |
| `SARVAM_API_KEY` | Open conversation, unreadable turns, family summaries |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_PROVIDER_NAME` | Any other OpenAI-compatible provider instead of Sarvam |
| `ARJUN_ASK_BEFORE_ACTING=1` | Old spoken yes/no flow instead of act-then-undo |
| `ARJUN_AUTH=1` | Family login / sign-up page and multiple elders |
| `ARJUN_ACCESS_CODE` | Locks the phone tunnel (required for `-Phone`) |
| `TELEGRAM_*`, `BASE_URL` | Family alerts and the join-call link |
| `TAVILY_API_KEY` | Live search (weather, scores, approved news) |
| `YOUTUBE_API_KEY` | Plays the first YouTube match; without it a results page opens |
| `CALLS_ENABLED=1`, `TWILIO_*` | Emergency auto-calls (needs a Twilio account; untested with a real call) |
| `ARJUN_DEBUG_VOICE=1` | Detailed `voice:` lines in `logs\voice-agent.app.log` |

Local runs override `DATABASE_URL`, `CORE_API_URL` and `REASONING_URL` for you.

## Using the app

**Elder app.** One big button, text at 24 px or larger, everything also spoken, no timeouts. She just talks:
"उद्या सकाळी दहा वाजता डॉक्टर" sets an appointment, "माझी औषधं कोणती?" reads her medicines from SQL,
"मदत हवी आहे" sends a help request to the family, "नको" undoes the last thing. For a dedicated always-on device use
`scripts\elder-kiosk.ps1`.

**Apps by voice.** YouTube songs and bhajans, family-approved links, headlines from the family's feeds, and WhatsApp
(she taps the green button herself). Say "अर्जुन" first for a new request while a video plays.

**Family dashboard.** Reminders, appointments, medicines (only the family edits these), contacts, Memory Book (shared
stories only), "Apps and links", and a live feed with a seriousness level, mood and short summary per conversation,
never a transcript. Mood and summaries show only with the "share how she is doing" consent on. A physical emergency
shows a banner regardless.

## Running on a phone

A phone needs HTTPS for the microphone. Set `ARJUN_ACCESS_CODE` (6+ letters/digits) in `.env`, then:
```powershell
scripts\dev-up.ps1 -Phone
```
This starts a Cloudflare quick tunnel, writes its URL into `BASE_URL`, restarts core-api, and prints the elder and
family links with the code. Without a valid cookie the tunnel serves no API key. Close the "arjun tunnel" window when
finished.

## Docker and cloud

```
copy .env.example .env
docker compose up --build       # postgres, core-api :8000, reasoning :8001, scheduler, web :5173
```
Compose does **not** run the voice-agent: start the worker separately (`scripts\dev-up.ps1 -Only voice-agent`).
Cloud deployment (Vercel for the web app, Railway for the four services) is described in
[docs/DEPLOY_CLOUD.md](docs/DEPLOY_CLOUD.md), with configs in `deploy/railway/`. **That path is unverified:** it has
not been deployed yet.

## Tests and checks

Run from the repo root with the venv active, or call `.venv\Scripts\python -m pytest` directly:

```powershell
cd services\core-api;   pytest            # core-api (CORE_API_KEY not needed: tests set ARJUN_TESTING=1)
cd services\reasoning;  pytest
cd services\voice-agent; pytest
cd services\scheduler;  pytest
ruff check .                              # repo root
cd web; npx tsc --noEmit; npm test        # TypeScript and Vitest
.venv\Scripts\python eval\run_eval.py     # intent / slot / distress eval
```
Eval results (system level, measured) are in `eval/results/RESULTS.md`. Current verification counts and what has and
has not been run live are in [STATUS.md](STATUS.md). The eval sets were written alongside the parsers, so they do not
measure real elderly speech.

## Troubleshooting

| Symptom | Check |
|---|---|
| Arjun does not speak or start a conversation | Is the **voice-agent worker running**? Look for `registered worker {"agent_name": "arjun"...}` at the end of `logs\voice-agent.log`. If it is missing, run `scripts\dev-up.ps1 -Only voice-agent`. Then reload the page: each session needs a new room. |
| Worker died after "FFI Panic ... ReadyForRoomEventRequest" | The network to LiveKit dropped and killed the worker. Check `Test-NetConnection <your-livekit-host> -Port 443`, then restart the worker. It is not restarted automatically. |
| Worker joins no rooms | It registers as `agent_name="arjun"` and joins only rooms that explicitly dispatch it. The LiveKit Console with "No agent selected" never does. Use the app, or `scripts\make_token.py`. |
| core-api exits at startup | `CORE_API_KEY` is empty. |
| Mic audio reaches the agent but no transcript | Open question: see `logs\voice-agent.app.log` (`voice:` lines) and [docs/RUNBOOK.md](docs/RUNBOOK.md). |
| Page is silent on first load | Tap once; browsers block autoplay audio until then. |
| Telegram alerts have no join button | `BASE_URL` is unreachable, or is a quick-tunnel URL (set `ARJUN_ALLOW_QUICK_TUNNEL=1` if intended). |
| Slow first reply | The first TTS call opens a connection and builds a TLS context; the worker prewarms it at startup. |

## More documentation

Full index: [docs/README.md](docs/README.md).

| Topic | Page |
|---|---|
| Architecture, voice path, turn pipeline, delivery, emergency flow | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| File-by-file module guide for every service and the web app | [docs/SERVICES.md](docs/SERVICES.md) |
| Every HTTP/WebSocket endpoint | [docs/API.md](docs/API.md) |
| Every database table | [docs/DATA_MODEL.md](docs/DATA_MODEL.md) |
| Every environment variable | [docs/CONFIGURATION.md](docs/CONFIGURATION.md) |
| Safety, consent, privacy, honesty rules, verification status | [docs/SAFETY_AND_PRIVACY.md](docs/SAFETY_AND_PRIVACY.md) |
| Develop, test, extend, gotchas | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Run, log, troubleshoot, demo checklist | [docs/OPERATIONS.md](docs/OPERATIONS.md), [docs/RUNBOOK.md](docs/RUNBOOK.md) |
| Cloud deployment (unverified) | [docs/DEPLOY_CLOUD.md](docs/DEPLOY_CLOUD.md) |
| Latency, concurrency, Prisma audit | [docs/ENGINEERING.md](docs/ENGINEERING.md), [docs/GNANI_FEATURES.md](docs/GNANI_FEATURES.md) |
| Feature history and the full known-limitations list | [docs/DETAILS.md](docs/DETAILS.md) |
| Spec and hard boundaries (source of truth) | [CLAUDE.md](CLAUDE.md) |
| Dated verification log | [STATUS.md](STATUS.md) |
| Contest submission draft | [SUBMISSION.md](SUBMISSION.md) |

## Known limitations (summary)

Not live-verified on current code: a complete spoken STT-to-TTS conversation, apps by voice, the phone microphone
path, and the cloud deployment. The Hindi/Marathi safety lexicons and the bn/gu/kn/ml/pa/ta/te replies are unverified
by a native speaker. Emergency calls are untested with real Twilio. Openers and briefings are only logged, not spoken.
Gnani's published benchmark numbers are not reported (EULA clause 16): only system-level results. The full list is in
[docs/DETAILS.md](docs/DETAILS.md).
