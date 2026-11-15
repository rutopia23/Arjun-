# Configuration reference

All configuration is **environment variables from ONE root `.env`** (copy `.env.example`; only `.env.example` is
tracked in Git, never `.env`). `scripts\dev-up.ps1` reads it and gives each service **only the variables it
needs**; Docker Compose passes a smaller set (see [Docker](#docker-compose-notes)). `.env.example` is the
authoritative list with comments; this page explains meaning, defaults, who reads each variable and the pitfalls.

Check your file without printing secrets: `.venv\Scripts\python scripts\check_env.py`; test the Gnani key:
`scripts\check_gnani.py`.

Contents: [Minimum setups](#minimum-setups) · [Who reads what](#who-reads-what-secret-scoping) ·
[Shared](#shared-core-api-reasoning-scheduler) · [core-api](#core-api) · [reasoning](#reasoning) ·
[voice-agent](#voice-agent) · [scheduler](#scheduler) · [web](#web) · [Emergency, Telegram, Twilio](#family-alerts-telegram-and-emergency-calls) ·
[ENV=prod](#envprod-startup-checks) · [Docker](#docker-compose-notes)

## Minimum setups

| Goal | Set |
|---|---|
| **Rules-only text** (no voice, no LLM) | `CORE_API_KEY` |
| **+ open conversation** | add `SARVAM_API_KEY` (or `LLM_BASE_URL`+`LLM_MODEL`+`LLM_API_KEY`) |
| **Full voice** (what the contest needs) | add `GNANI_API_KEY`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| **Family alerts** | add `TELEGRAM_ENABLED=1`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `BASE_URL` |
| **Phone over a tunnel** | add `ARJUN_ACCESS_CODE` (6+ chars) and run `dev-up.ps1 -Phone` |
| **Family login** | `ARJUN_AUTH=1`, `ARJUN_SIGNUP_CODE` |

## Who reads what (secret scoping)

| Secret | Read by | Never read by |
|---|---|---|
| `CORE_API_KEY` | core-api, reasoning, scheduler, web dev proxy | the browser bundle |
| `GNANI_API_KEY` | **voice-agent**; core-api in exactly ONE place: `voices.create_embedding` (voice cloning, *proposed exception*, enforced by `tests/test_voices.py::test_gnani_key_only_in_create_embedding`) | reasoning, scheduler, web |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` / `LIVEKIT_URL` | voice-agent; core-api (to sign elder tokens at `/livekit/token`) | reasoning, web |
| `LLM_API_KEY`, `SARVAM_API_KEY`, `EVON_API_KEY` | **reasoning only** | everyone else |
| `TAVILY_API_KEY` | reasoning only | |
| `TELEGRAM_BOT_TOKEN`, `TWILIO_*`, `YOUTUBE_API_KEY`, `VOICE_CLONE_KEY` | core-api only | |

voice-agent loads *only* `GNANI_*`, `LIVEKIT_*`, `ARJUN_*` (and a few named helpers) from `.env` itself and exits
naming any missing required variable. Keys are never logged or printed.

---

## Shared (core-api, reasoning, scheduler)

| Variable | Default | Meaning |
|---|---|---|
| `CORE_API_KEY` | – (**required**) | Shared service secret. core-api exits at startup if empty (tests set `ARJUN_TESTING=1`). Use ≥ 32 random characters for `ENV=prod` |
| `CORE_API_URL` | `http://core-api:8000` (code) | Where core-api is. Local runs override to `http://127.0.0.1:8000`. Use `127.0.0.1`, **not** `localhost`: on Windows `localhost` costs ~2 s per connection (IPv6 tried first, measured 2026-10-24) |
| `REASONING_URL` | `http://reasoning:8001` | Where reasoning is (voice-agent, scheduler). Local override `http://127.0.0.1:8001` |
| `ARJUN_TZ` | `Asia/Kolkata` | Household timezone used by every service clock (containers run in UTC) |
| `ARJUN_CITY` | empty | City for spoken weather (Open-Meteo, no key) when the user profile has none |
| `ARJUN_LOGIC_EVAL_USER_ID` | – | User id used by `scripts/eval_logic.py` |

## core-api

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./arjun.db` | SQLAlchemy URL. Compose uses `postgresql+psycopg://arjun:arjun@postgres:5432/arjun`. `dev-up.ps1` forces SQLite locally |
| `ARJUN_AUTH` | `0` | `1` = family accounts, sessions and paired elder devices; the dashboard shows a login page |
| `ARJUN_SIGNUP_CODE` | empty | Sign-up code; required when `ARJUN_AUTH=1` in prod. First ever account owns existing elders |
| `ARJUN_ALLOW_OPEN_SIGNUP` | – | `1` allows sign-up without a code (**never in prod**) |
| `CORS_ALLOW_ORIGINS` | empty | Comma list of exact origins (the Vercel site). Empty = no CORS headers. `*` is ignored/refused |
| `BASE_URL` | empty | Public URL of the web app, used to build the family join link. Empty = Telegram alerts have no join button. core-api refuses `*.trycloudflare.com` quick-tunnel URLs in family links unless `ARJUN_ALLOW_QUICK_TUNNEL=1` |
| `ARJUN_ALLOW_QUICK_TUNNEL` | `0` | Allow quick-tunnel URLs in links (they die when the tunnel restarts) |
| `JOIN_SECRET` | empty | Signs the 30-minute family-call join link |
| `UNDO_TTL_S` | `180` | How long a done action can still be undone (core-api side) |
| `PENDING_TTL_S` | `300` | How long an unanswered pending action lives |
| `CORE_RATE_LIMIT` | `1` | `0` disables the per-client HTTP rate limit |
| `CORE_RATE_PER_S` / `CORE_RATE_BURST` | `30` / `60` | Token bucket; 429 + `Retry-After` when exceeded. `/health` and WebSockets exempt |
| `FEED_RECHECK_S` | `5` | The feed WebSocket re-reads the table this often even without a push |
| `ARJUN_VOICE_TURNLOG_PATH` | `eval/results/turns.jsonl` | Read-only turn timings for the numeric performance card |
| `ARJUN_CHECKINS_ENABLED` | – | `1` enables proactive day check-ins (also needs the family's per-person switch `daily_checkins`) |
| `ARJUN_CHECKIN_MAX_PER_DAY` | `14` | Cap on check-in questions per day |
| `ARJUN_CHECKIN_MIN_GAP_MIN` | `30` | Minutes between check-in questions |
| `ARJUN_CHECKIN_DEMO` | `0` | `1` only for a live demo: lets `scripts/checkin_demo.py` ask the next check-in now |
| `YOUTUBE_API_KEY` | empty | YouTube Data API v3 key. Empty = the page opens the YouTube results page instead of playing the first match |
| `YOUTUBE_MAX_SEARCHES_PER_DAY` | `80` | Cap on **uncached** searches (80 × 100 = 8,000 of 10,000 daily units); results cached 24 h |
| `VOICE_CLONE_KEY` | empty | Fernet key that encrypts stored speaker embeddings; empty = cloning off. **Never change it later** (saved voices stop working) and never share it. Make one: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ARJUN_SOUND_EVENTS` | `0` | Experimental sound events; off by default |
| `MONGO_URL` | – | Reserved, not read by any service |

## reasoning

### The LLM (open conversation only)
Priority when several are set: **`GNANI_REASONING_IMPL=evon` + `EVON_BASE_URL`** → **`LLM_BASE_URL`** →
**`SARVAM_API_KEY`** → leftover `EVON_*`. `LLM_*` and `EVON_*` are never mixed (a missing `LLM_MODEL` must not
silently become the Evon model name and be sent to a hosted provider). Nothing configured = rules only.

| Variable | Default | Meaning |
|---|---|---|
| `SARVAM_API_KEY` | empty | **Alone enough** to turn on Sarvam-105B (hosted, non-Gnani) for open conversation, unreadable turns and the family summaries |
| `SARVAM_MODEL` | `sarvam-105b` | e.g. `sarvam-105b-conversations` |
| `SARVAM_BASE_URL` | `https://api.sarvam.ai/v1` | OpenAI-compatible |
| `LLM_REASONING` | off | `1` lets Sarvam "think" (latency). Default sends `reasoning_effort: null`; `<think>` text is stripped |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | empty | Any other OpenAI-compatible provider (`LLM_MODEL` required with `LLM_BASE_URL`) |
| `LLM_PROVIDER_NAME` | `hosted-llm` | Free-text name for logs and `/health`; **use it in the public write-up** |
| `LLM_SEND_TEMPLATE_KWARGS` | `1` (`0` for Sarvam) | vLLM-only `chat_template_kwargs`; set `0` for hosted providers |
| `LLM_TIMEOUT_S` | `6` | One budget for **all** LLM calls in a turn, then the fixed fallback line |
| `LLM_MAX_TOKENS` | code `250` (`.env.example` shows `80`) | Reply cap. 80 cut Marathi replies mid-sentence in some cases; the companion call uses `min(this, 120)`. Measured Marathi replies use 20–42 tokens |
| `LLM_MAX_CONCURRENT` | `4` | LLM calls in flight; over it the rules answer |
| `LLM_PER_MINUTE` | `60` | LLM call rate; over it the rules answer; back-off after a provider 429 |
| `LLM_HISTORY_EXCHANGES` | `8` | **Old knob**, no longer the size of Arjun's memory |
| `EVON_BASE_URL`, `EVON_MODEL`, `EVON_API_KEY`, `EVON_SEND_TEMPLATE_KWARGS`, `GNANI_REASONING_IMPL` | – | Evon is **not used** (decision T9, 2026-10-24); names kept as aliases. Never run it on the dev laptop |

Fixed constants (not env): extraction/understanding temperature **0**; companion temperature **0.4** (≤ 0.4 so replies
stay on what she said; the companion eval was run at 0.5 and a re-run is pending); top-p 0.95; companion reply cut at
300 characters on a sentence boundary.

### Acting and timing
| Variable | Default | Meaning |
|---|---|---|
| `ARJUN_ASK_BEFORE_ACTING` | `0` | `1` restores the spoken yes/no flow (the older test suites run in that mode) |
| `UNDO_WINDOW_S` | `150` | Spoken undo window (core-api allows 180 s; keep the margin) |
| `TURN_RATE_PER_S` / `TURN_RATE_BURST` | `2` / `6` | Per-user `/turn` limit. Safety text is never limited |
| `CONVERSATION_IDLE_S` | `180` | Silence that ends a conversation; its summary then goes to the family |
| `ARJUN_INTERNAL_KEY` | unset | If set, `WS /turn/stream` requires it in the `x-arjun-internal` header |

### Memory and context
| Variable | Default | Meaning |
|---|---|---|
| `ARJUN_SESSION_EXCHANGES` | `20` | Exchanges kept word for word; older are compressed into a running summary |
| `ARJUN_SESSION_IDLE_MIN` | `30` | Minutes of silence after which a conversation is compressed (never deleted). After 24 h only long-term facts remain |
| `ARJUN_FACTS_IN_CONTEXT` | `10` | How many life facts go into each LLM call, best match first |
| `ARJUN_CONTEXT_STATE` | `1` | `0` restores the old prompt assembly |
| `ARJUN_PROMPT_TOKEN_CAP` | `2600` | Variable part of the prompt (history + state + context + facts) |
| `ARJUN_RELEVANCE_GUARD` | `1` | `0` turns off the "reply must be about what she said" guard |
| `USER_CONTEXT_TTL_S` | `300` | Cache of the user's context block |

### Live facts
| Variable | Default | Meaning |
|---|---|---|
| `TAVILY_API_KEY` | empty | Live web search (weather aside). Empty = Arjun says it has no information. **News** is answered only from results whose domain the family added as an `rss`/`link` app link |

## voice-agent

### Gnani + LiveKit
| Variable | Default | Meaning |
|---|---|---|
| `GNANI_API_KEY` | – (**required**) | Prisma STT and Timbre TTS |
| `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | – (**required**) | LiveKit Cloud (`wss://<project>.livekit.cloud`) |
| `ARJUN_AGENT_NAME` | `arjun` | Explicit-dispatch name; `make_token.py` and `/livekit/token` dispatch this name |
| `ARJUN_USER_ID` | `1` | Fallback user for Console rooms; real sessions use the dispatch metadata |
| `ARJUN_VOICE_PROVIDER` | `gnani` | **Testing switch**: `sarvam` swaps in Saaras STT + Bulbul TTS (`ARJUN_SARVAM_SPEAKER`). Never record or publish a demo with it |

### Speech to text (Prisma)
| Variable | Default | Meaning |
|---|---|---|
| `GNANI_STT_IMPL` | `plugin` | `plugin` = pinned `livekit-plugins-gnani` (Marathi hint, no model selection); `v3` = direct Prisma v3 adapter (`prisma_v3.py`, `indic-auto`, keyterms, speaker names) |
| `GNANI_STT_LANGUAGE` | `mr-IN` | Hint for the plugin path (not language identification). Not read by v3 |
| `GNANI_USE_STREAMING` | `1` | `0` = REST fallback (Marathi streaming support unconfirmed) |
| `GNANI_STT_FORMAT` | `transcribe` | `verbatim` or `transcribe` (the pinned plugin exposes only these two) |
| `GNANI_STT_SAMPLE_RATE` | `16000` | |
| `GNANI_ITN_NATIVE_NUMERALS` | `true` | Write digits in Devanagari; reasoning reads both forms |
| `GNANI_STT_TRANSPORT` | `ws` | v3 only: `ws` streaming or `rest` (one POST per utterance, ≤ 28 s, websocket fallback after two failures) |
| `GNANI_STT_TOPIC` | built-in | v3: what the audio is about (ASCII ≤ 1600 chars); `off` = none |
| `GNANI_STT_PREV_TEXT` | `0` | v3 REST: send the last 1–2 transcripts as context (Gnani warns it can lower accuracy) |

### Text to speech (Timbre)
| Variable | Default | Meaning |
|---|---|---|
| `GNANI_TTS_MODEL` | `timbre-v3.0` | Accepts only `timbre-v2.5` / `timbre-v3.0`. v3.0 understands voice tags |
| `GNANI_TTS_VOICE` | `Avinash` | A v3.0 voice, **unverified on our key**. The first synthesis of each worker is a probe |
| `GNANI_TTS_FALLBACK_MODEL` / `GNANI_TTS_FALLBACK_VOICE` | `timbre-v2.5` / `Omkar` | Used if the probe fails (verified live 2026-10-21) |
| `GNANI_TTS_METHOD` | `sse` | `sse` = pooled HTTP, sentence by sentence; `websocket` = old path (new socket per reply, ~0.9–1.2 s connect) |
| `GNANI_TTS_LANGUAGE` | empty | **Leave empty**: each reply is spoken in its own language |
| `GNANI_TTS_MULTILINGUAL_VOICE` | `0` | Opt in only after confirming the multilingual catalog is enabled for the account |
| `ARJUN_TTS_PREBUFFER_MS` | `150` | Decoded audio to wait for before playback; `0` disables |
| `ARJUN_CLONED_VOICE` | `1` | `0` = never speak in a cloned voice |
| `ARJUN_CLONED_VOICE_METHOD` | `rest` | `sse` is experimental (loud noise on the laptop 2026-11-08) |
| `ARJUN_CLONED_VOICE_LANGUAGES` | empty (all) | e.g. `hi,en`: keep `mr` out so Marathi stays in Arjun's own voice (the clone copies the sample's accent and the API has no language field) |

### Turn taking
| Variable | Default | Meaning |
|---|---|---|
| `ARJUN_MIN_ENDPOINTING_S` / `ARJUN_CARE_MAX_ENDPOINTING_S` | `0.8` / `2.5` | Care-mode silence before end of turn (aliases `ARJUN_ENDPOINT_MIN_DELAY` / `_MAX_DELAY`) |
| `ARJUN_COMPANION_MIN_ENDPOINTING_S` / `ARJUN_MAX_ENDPOINTING_S` | `1.6` / `4.0` | Chat/story mode (aliases `ARJUN_ENDPOINT_COMPANION_MIN_DELAY` / `_MAX_DELAY`) |
| `ARJUN_HELD_ANSWER_S` | `4.0` | A held "…आणि" sentence is answered after this long with no more words |
| `ARJUN_TURN_DETECTION` | `vad` | `vad`, `auto` (LiveKit cloud detector; 4 of 84 predictions timed out 2026-10-31), `stt` |
| `ARJUN_IDLE_CLOSE_S` | `0` | `0` = never close by itself (hands-free); `60` = old idle close (saves credits; always-on cost is unmeasured) |
| `REASONING_TIMEOUT_S` | `7.5` | Wait for reasoning before speaking the fixed fallback line |
| `ARJUN_STREAM` | off | `1` uses `WS /turn/stream` (falls back to HTTP by itself); `ARJUN_STREAM_CONNECT_S` 1.5, `ARJUN_STREAM_ACK_S` 2.0 |
| `ARJUN_DEBUG_VOICE` | `1` | Short `voice:` lines (lengths, language, timings; never the words) in `logs/voice-agent.app.log` |
| `ARJUN_SOUND_EVENTS` / `ARJUN_SOUND_MODEL_PATH` | `0` / empty | Experimental; needs a local YAMNet ONNX file |

## scheduler

| Variable | Default | Meaning |
|---|---|---|
| `SCHEDULER_INTERVAL_SECONDS` | `30` | Tick interval |
| `BRIEFING_TIME` | `20:30` | Daily Telegram voice briefing time (household-local) |
| `BRIEFING_VOICE_URL` | `http://127.0.0.1:8002/synthesize` | Loopback endpoint hosted by voice-agent (the Gnani key stays there) |
| `OPENER_USER_IDS` | empty | Comma list; empty = every user with `daily_checkins` on. Openers are **logged only**, not spoken |

## web

| Variable | Default | Meaning |
|---|---|---|
| `ARJUN_ACCESS_CODE` | empty | Locks the tunnel (6+ letters/digits/`-`/`_`). Empty or shorter = every remote request refused. `dev-up.ps1 -Phone` refuses to start without it |
| `CORE_API_URL`, `CORE_API_KEY` | – | Used by the Vite proxy (server side only) |

URL parameters (not env): `?user=1` (elder id), `?view=family`, `?handsfree=0` (tap-to-talk test mode),
`?theme=evening`, `?ui=1` (UI gallery), `?ui=chat`, `?debug` (YouTube debug).

## Family alerts, Telegram and emergency calls

| Variable | Default | Meaning |
|---|---|---|
| `TELEGRAM_ENABLED` | `0` | `1` sends family alerts over Telegram |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | empty | From @BotFather / the family group. Never committed or logged (the request URL contains the token) |
| `CALLS_ENABLED` | `0` | `1` + Twilio keys lets emergency escalation actually place calls |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM` | empty | Read only by core-api. Trial accounts can call only verified numbers |
| `ARJUN_EMERGENCY_WAIT_S` | `10` | How long Arjun waits for "तुम्ही ठीक आहात का?" before calling the help number |

## ENV=prod startup checks

With `ENV=prod`, **core-api, reasoning and voice-agent refuse to start** (printing the *names*, never values, of
what is wrong); the scheduler checks `CORE_API_URL`, `CORE_API_KEY`, `REASONING_URL`. core-api requires:
`CORE_API_KEY` (≥ 32 chars), `DATABASE_URL`, `CORS_ALLOW_ORIGINS` (exact origins, no `*`), `BASE_URL`,
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`; and forbids `ARJUN_TESTING=1` and
`ARJUN_ALLOW_OPEN_SIGNUP=1`; with `ARJUN_AUTH=1`, `ARJUN_SIGNUP_CODE` must be set. Without `ENV=prod`, behaviour is
unchanged.

## Docker Compose notes

`docker-compose.yml` runs **postgres (pgvector/pg16), core-api, reasoning, scheduler and web**. It does **not**
run voice-agent: start the worker separately (`scripts\dev-up.ps1 -Only voice-agent`, or the Railway config in
`deploy/railway/voice-agent.railway.json`, start command `python agent.py start`). Compose defaults `CORE_API_KEY`
to `dev-change-me`: **change it**. The compose `web` service sets `CORE_API_URL`/`REASONING_URL`/`CORE_API_KEY`
but not `ARJUN_ACCESS_CODE` (the access code applies to the Vite dev server only).
