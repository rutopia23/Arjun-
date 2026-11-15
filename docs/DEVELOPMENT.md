# Development guide

How to set up, change, test and extend Arjun. Read [ARCHITECTURE.md](ARCHITECTURE.md) and
[SAFETY_AND_PRIVACY.md](SAFETY_AND_PRIVACY.md) first: several rules here exist because of them.

Contents: [Setup](#setup) · [Everyday commands](#everyday-commands) · [Running one service](#running-one-service) ·
[Testing](#testing) · [Linting](#linting-and-types) · [Recipes](#recipes-how-do-i) · [Conventions](#conventions) ·
[Gotchas](#gotchas) · [Git and docs workflow](#git-and-docs-workflow)

## Setup

Windows 10/11, PowerShell, Python **3.12**, Node.js 18+. (The stack is also written to run in Docker/Linux; the
helper scripts are PowerShell.)

```powershell
git clone <repo> ; cd Arjun
python -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\pip install -r services\core-api\requirements.txt `
                          -r services\reasoning\requirements.txt `
                          -r services\voice-agent\requirements.txt
.venv\Scripts\pip install httpx tzdata pytest ruff        # scheduler deps + dev tools
cd web ; npm install ; cd ..
copy .env.example .env        # then edit .env, see CONFIGURATION.md
```

`dev-up.ps1` expects the venv at `.venv\Scripts\python.exe`. Pins that matter: `livekit-agents==1.8.6`,
`livekit-plugins-gnani==1.8.6` (and silero/sarvam plugins 1.8.6), `livekit-api==1.2.1`. Do not bump the LiveKit
pins casually: the Gnani plugin version must match, and the worker's behaviour is validated only on 1.8.6.

## Everyday commands

```powershell
scripts\dev-up.ps1                      # everything: core-api :8000, reasoning :8001, scheduler, voice-agent, web :5173
scripts\dev-up.ps1 -Only reasoning      # just one (core-api | reasoning | scheduler | voice-agent | web)
scripts\dev-up.ps1 -Phone               # + Cloudflare tunnel for a phone (needs ARJUN_ACCESS_CODE)
.venv\Scripts\python scripts\seed_heerabai.py --apply    # demo user "Aaji" (user 1), synthetic
```
Each service opens in its own PowerShell window (title `arjun <service>`) and also logs to `logs\`. Closing a
window stops that service. The script overrides `DATABASE_URL` (SQLite), `CORE_API_URL` and `REASONING_URL` for local runs.

## Running one service

From the service folder with the venv:

```powershell
cd services\core-api;   ..\..\.venv\Scripts\python -m uvicorn core_api.main:app --port 8000 --reload
cd services\reasoning;  ..\..\.venv\Scripts\python -m uvicorn reasoning_svc.main:app --port 8001 --reload
cd services\voice-agent; ..\..\.venv\Scripts\python agent.py dev          # `start` for production
cd services\scheduler;  ..\..\.venv\Scripts\python scheduler.py
cd web;                 npm run dev                                       # vite --host
```
These need the right environment variables (`CORE_API_KEY`, `CORE_API_URL`, ...). `dev-up.ps1` sets them from `.env`;
when running by hand, export them in the shell first. core-api exits if `CORE_API_KEY` is empty.

Text-only exploration without voice: call reasoning directly (see [API.md](API.md) examples) or run
`python scripts/converse_test.py` (in-process, in-memory database, synthetic user).

## Testing

Run each suite from its folder (they have separate `conftest.py`s and import paths):

| Suite | Command | Notes |
|---|---|---|
| core-api | `cd services\core-api ; ..\..\.venv\Scripts\python -m pytest` | in-memory SQLite; `ARJUN_TESTING=1` is set by the tests (the only way to run without `CORE_API_KEY`) |
| reasoning | `cd services\reasoning ; ..\..\.venv\Scripts\python -m pytest` | many tests run `ARJUN_ASK_BEFORE_ACTING=1` (the older yes/no mode); the LLM is faked |
| voice-agent | `cd services\voice-agent ; ..\..\.venv\Scripts\python -m pytest` | tests are alongside the code (`test_*.py`); no live Gnani calls |
| scheduler | `cd services\scheduler ; ..\..\.venv\Scripts\python -m pytest` | |
| web | `cd web ; npm test` (`vitest run`) · `npx tsc --noEmit` | `npm run build` also runs `scripts/check_no_browser_speech.py` |
| lint | `ruff check .` at the repo root | `ruff.toml`: line length 100, py311, rules E F I B |
| eval | `.venv\Scripts\python eval\run_eval.py` | intent / slot / distress cases, synthetic |

Counts on 2026-11-15 (STATUS.md): core-api 367, reasoning 1479, voice-agent 445, scheduler 7, Vitest 266.

Rules:
* **Run them after changes** and do not claim something works unless it was run. Mark unverified code as unverified.
* The eval sets were written with the parser, so passing them proves regression safety, **not** real-speech accuracy.
* Live checks (real Prisma/Timbre/Sarvam, phone, Twilio) are separate and manual; record outcomes in STATUS.md and
  `eval/results/RESULTS.md` only when measured.
* More evaluations: `scripts/eval_companion.py`, `eval_context.py`, `eval_dialogues.py`, `eval_lang.py`,
  `eval_logic.py`, `eval_qa.py`, `eval_calls.py`, `eval_all.py`; timing: `voice_report.py`, `voice_latency_report.py`;
  `eval_realvoice.py` needs your own synthetic WAV clips and labels and never prints WER.

## Linting and types

* Python: `ruff check .` (E501 and B008 are ignored on purpose: long Devanagari templates, FastAPI `Depends`).
* TypeScript: strict; `npx tsc --noEmit` must be clean. Build step also forbids browser speech APIs on the elder page.
* The safety word file `services/voice-agent/safety_words.py` is **generated**; `python scripts/gen_safety_words.py --check`
  fails when it is stale.

## Recipes: how do I...

### Add a new intent the user can speak
1. **Schema**: add the intent to `shared/schemas/intent.json` so LLM output validates.
2. **Rules fallback**: recognise it in `reasoning_svc/parser.py` (and the lexicon helpers in `textutil.py`).
3. **Dispatch**: add a branch in `TurnEngine._dispatch` (`turn.py`). If it writes data, go through core-api's
   propose/confirm path, never directly.
4. **Reply**: add fixed templates to `replies.py` for mr/hi/en (and `replies_langs.py` keys; missing keys fall back to English).
5. **Prompt**: if the LLM should choose it, update the understanding prompt in `evon.py`.
6. **Tests**: reasoning tests for the rule path and an LLM-faked path; add an eval case.

### Add a new action the ledger can execute
Add the `action_type` to `_validate_payload` and the confirm/undo handlers in `core-api/main.py`, add schema
validation, add tests in `services/core-api/tests`. Medicine create/edit **must not** be added (family-only).

### Add a table or column
Add the model in `models.py`. For a new **column on an existing table**, also add a row to `db.ADDED_COLUMNS`
(nullable or with a default). There are no migrations; do not rename or drop columns.

### Add a core-api endpoint
Put it in the matching router module (or a new one); use `APIRouter(dependencies=[Depends(require_key)])`; include
the router in `main.py`. Keep transcripts out of the payloads. Add tests. Update [API.md](API.md).

### Add a language
Reply templates (`replies_langs.py`), safety words (`safety_langs.py`, then regenerate `safety_words.py`), the
`pattern` regexes for `language`/`reply_language` in core-api and reasoning (`^(mr|hi|en|bn|gu|kn|ml|pa|ta|te|or)$`),
`web/src/elder/strings.ts` and `i18n.ts`. Mark it **unverified** until a native speaker reviews it.

### Add a voice command for an app or link
`reasoning_svc/appcmd.py` (rules, word lists unverified), `app_replies.py` (fixed lines), then the family adds the
link in the dashboard (`applinks.py` validates https and the host allowlist). The elder page performs the `action`
(`web/src/elder/useAppActions.ts`, `media.ts`).

### Change a family dashboard card
`web/src/family/` (Dashboard.tsx composes cards). Data comes through `web/src/api.ts` → `/core/...`. Anything that
shows mood/summary/facts must respect the consent flag.

### Change speech settings
Environment first (`.env`: [CONFIGURATION.md](CONFIGURATION.md)). Endpointing values are placeholders: change them only
with real samples from elderly speakers. TTS selection is in `agent.py: working_tts`/`make_tts`.

### Reset local data
`python scripts/clean_demo_db.py` (dry run) then `--apply` (backs up first). The local database is `arjun.db` in
the core-api working directory (`services/core-api/arjun.db` when started by `dev-up.ps1`). Never delete it blindly:
look first.

## Conventions

* **Time**: naive household-local datetimes; use `clock.local_now()` / `get_now` (so tests can override). Never bare `datetime.now()` in services.
* **Errors**: a failure must never mean silence. Voice-agent and reasoning return fixed lines on dependency errors.
* **Templates over generation** for care, safety and medicines; the LLM only for companion talk and understanding.
* **No yes/no questions**: act, read back in ONE line, let "नको" undo. Still ask for missing details.
* **No secrets** in code, logs, URLs, headers of outbound calls (a Telegram request URL contains the bot token:
  never log it).
* **Marathi first**: write user-facing Marathi carefully; Hindi/English next; other languages marked unverified.
* **Copy rules**: address her with `address_as`; never invent "ताई"; never say Arjun has feelings or family.
* Service boundaries are HTTP contracts. Do not import one service's package from another (the duplicated
  `ratelimit.py` and `langid.py` are intentional).
* Comments explain **why** (decisions are dated); update STATUS.md and the README "known limitations" when behaviour
  or verification status changes.

## Gotchas

* **`localhost` is slow on Windows** (~2 s per connection, IPv6 first). Use `127.0.0.1` in service URLs.
* **Fresh room per session**: the agent is dispatched at room creation. Reusing a room name = no agent.
* **LiveKit Console with "No agent selected"** never dispatches our worker. Use the app or `make_token.py`.
* **Two tabs = two sessions** fighting for the mic. Close extras.
* **Browsers block audio until a tap**; proactive speech needs the kiosk device (`elder-kiosk.ps1`).
* **A worker killed by a network drop** is not restarted locally (FFI panic `timed out waiting for
  ReadyForRoomEventRequest`). Restart it with `scripts\dev-up.ps1 -Only voice-agent`.
* **core-api restart clears the room map**; open the elder URL once before testing a family-call link.
* **Reasoning restart clears session memory** (history, summary, drafts). Facts in core-api persist.
* **Scheduler restart** forgets "opener sent today".
* **Windows soxr crash** ("Assertion failed LSX_FFT_BR == NULL"): the fix (warm the resampler once per process,
  `audiowarm.py`) passes unit tests but is **not confirmed live**.
* **Prisma confuses Marathi and Hindi**: `langid.py` corrects with word evidence; never trust the STT label alone.
* **Timbre accepts only `timbre-v2.5` / `timbre-v3.0`**, and needs a voice. `Avinash` (v3.0) is unverified on our key;
  `Omkar` (v2.5) is verified.
* **`LLM_MAX_TOKENS`**: the example file says 80, the code default is 250. 80 can cut a reply mid-sentence.
* **Sarvam is non-Gnani**: keep disclosing it; never demo with `ARJUN_VOICE_PROVIDER=sarvam`.
* **Do not edit `safety_words.py` by hand** (generated).
* **`.env` quoting**: `dev-up.ps1` strips surrounding quotes; comments must be on their own line.

## Git and docs workflow

* Branch from `main`; one task at a time; verify (tests + lint + `tsc`) before committing. `CLAUDE_CODE_TASKS.md`
  (if present) lists the task order; feature freeze items (BP/sugar, export for doctor, strip photos, RSS news
  extras, full pgvector RAG, migrations, nginx replicas, S3 cache, general telephony, SMS/WhatsApp, Evon fine-tuning)
  must not be started without asking.
* Never commit `.env`, databases (`*.db`), audio, `logs/` or `node_modules` (all git-ignored). There are many
  `_pytest_*` scratch folders in the repo root from earlier runs: they are local scratch, not part of the product.
* When behaviour or verification status changes, update: `STATUS.md` (dated entry), the README "Known limitations"
  (`docs/DETAILS.md`), and the relevant page under `docs/`.
