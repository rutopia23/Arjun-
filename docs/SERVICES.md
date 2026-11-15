# Service and module guide

A file-by-file map of the code: what each module is for and when you would edit it. Read
[ARCHITECTURE.md](ARCHITECTURE.md) first for the big picture. Sizes are approximate lines at 2026-11-15.

Contents: [core-api](#core-api) · [reasoning](#reasoning) · [voice-agent](#voice-agent) · [scheduler](#scheduler) ·
[web](#web) · [shared, eval, scripts](#shared-eval-scripts-deploy)

---

## core-api

`services/core-api/core_api/` · FastAPI app `core_api.main:app` · start: `uvicorn core_api.main:app --port 8000`
(run from `services/core-api`). Tests: `services/core-api/tests/`.

**Startup (`main.py: lifespan`)**: `check_api_key_configured()` → `check_prod_env()` → BASE_URL probe thread →
`reconcile_schema` → `Base.metadata.create_all` → `ensure_columns`. Middleware: `origin_brake` (CSRF),
`RateLimitMiddleware`, optional CORS.

| Module | Role |
|---|---|
| `main.py` (905) | App wiring; users, contacts, reminders, appointments, stories, the propose/confirm/undo/reject ledger (`_validate_payload`), help/distress/lonely/health-complaint, notifications, `fire-due`, sound events, `/health`, `/diag/base-url`. **Add a new action type here** |
| `models.py` (564) | All SQLAlchemy tables ([DATA_MODEL.md](DATA_MODEL.md)); `User.address_as` default |
| `schemas.py` (385) | Pydantic request/response models (`ReminderIn`, `DayOut`, `PendingOut`...) |
| `db.py` | Engine, `get_db`, `ADDED_COLUMNS`, `ensure_columns`, `reconcile_schema` |
| `deps.py` | `require_key`, `check_api_key_configured`, `testing()`, `get_now` (test hook), `auth_enabled` |
| `auth.py` (612) | Accounts, Argon2id passwords, sessions, memberships, invites, device pairing, login/pairing/sign-up rate limits, `authorize_core_request`, `authorize_websocket` |
| `origin_guard.py` | CSRF brake for cookie requests |
| `ratelimit.py` | Token bucket + HTTP middleware (`/health`, WebSockets exempt) |
| `medicines.py` | Family-only medicine CRUD, dose generation (`ensure_doses`, `due_at_for`), taken/snooze, `/internal/medicines/tick` |
| `deliveries.py` | The T8 delivery queue state machine (`enqueue`, claim/spoken/release/ack, sweep). Constants `LATE_AFTER` 120 s, `BACKLOG_CAP` 3, `STALE_CLAIM` 90 s, `MAX_TRIES` 3 |
| `checkins.py`, `checkin_plan.py` | Family-enabled meal/walk/BP/interest check-ins and today's plan, built only from SQL (frozen feature) |
| `day.py` | `/users/{id}/day`: one SQL-backed view of a day |
| `recurrence.py` | Weekly appointment occurrences (`next_occurrence`, `occurrence_on`) |
| `wellbeing.py` | Per-conversation severity/mood/summary rows (no transcripts) |
| `feed.py` | `Notification`/`Wellbeing` → `FeedEvent` via SQLAlchemy events; WebSocket + polling feed; kind → severity/title map |
| `telegram.py` | Telegram alerts (`claim`, `recent_outcome` de-duplication), join-call buttons, voice notes |
| `briefings.py` | Daily consent-aware Marathi voice briefing (`BRIEFING_TIME`, one attempt/user/day) |
| `emergency.py` | Emergency settings, location capture (15-minute window), escalation calls via Twilio (`CALLS_ENABLED`), honest call log |
| `facts.py` | Long-term facts with refusal rules (numbers, addresses, money, medicines, diagnoses), consent for body complaints |
| `rag.py` | Light retrieval over her own stories |
| `applinks.py` | Family-approved apps/links with host allowlist and the "approve other host" tick |
| `media.py` | YouTube search (key kept here, 24 h cache, daily cap), RSS headlines from the family's feeds |
| `video_calls.py`, `family_call.py`, `joins.py` | Elder-initiated calls, signed join links, family join/answer/end |
| `livekit_token.py` | `/livekit/token`: fresh room, explicit `arjun` dispatch, metadata `{user_id, language}`; in-memory room map |
| `voices.py` | Consent-first voice cloning (the **only** place core-api reads `GNANI_API_KEY`); Fernet-encrypted embeddings; audit trail |
| `health.py` | Family health profile; the day's medicine check |
| `readings.py` | BP / watch samples (frozen; raw numbers only) |
| `activity.py` | Last-seen timestamp |
| `voice_metrics.py` | Numeric-only aggregation of `turns.jsonl` |
| `baseurl.py` | Is `BASE_URL` a real, reachable, non-quick-tunnel URL? |
| `prodcheck.py`, `clock.py` | `ENV=prod` refusals; household-local clock |

## reasoning

`services/reasoning/reasoning_svc/` · app `reasoning_svc.main:app` · start: `uvicorn reasoning_svc.main:app --port 8001`.

| Module | Role |
|---|---|
| `main.py` | FastAPI routes, `TurnIn/TurnOut`, per-user rate limit, engine/tracker singletons, `/turn/stream`, media gate, delivery pulls, flush-idle, briefing/opener |
| **`turn.py` (3,454)** | **`TurnEngine`: the orchestration.** `_handle` is the fixed pipeline; `_understand` (the one LLM call), `_intent` (LLM vs rules), `_dispatch` (one branch per intent), `_chat_reply`, `_web_turn`, `_open_media`, `_symptom`, `_med_list`, `_safety`, guards (`_claim_guard`, `_guard_cardiac_reply`, `_relevance_guard`, `_guard_reply_language`), delivery pulls, `opener`, `briefing`. **Almost every behaviour change lands here** |
| `parser.py` | Rule-based fallback: intent + slots (Marathi/Hindi/English times: साडे, सव्वा, पावणे, दीड, अडीच, day-parts) → `Parsed`/`Draft`; `YES`/`NO`/`STOP`/`SNOOZE_WORDS` |
| `distress.py` | **Safety lexicons and rules**: `is_emergency`, `is_distress`, `is_lonely`, `symptom_category`, `has_health_word`, `gives_medical_advice`, `mentions_cardiac`. Recall-biased; **unverified by a native speaker** |
| `safety_langs.py` | Same for bn, gu, kn, ml, pa, ta, te |
| `replies.py` (946) | **Fixed reply templates** mr/hi/en (`R[lang]`), `SELF_CARE`, `MED_LIST`, AI disclosure, emergency/distress lines |
| `replies_langs.py` | Fixed templates for the seven other languages (unverified; missing keys fall back to English) |
| `evon.py` (1,251) | `EvonClient`: the OpenAI-compatible LLM client (name is historical). Understanding call (strict JSON), companion reply, summary, simplify, filler strip, voice-tag handling, `Limiter`/`LlmBusy`, think-text stripping |
| `config.py` | `llm_settings()`, temperatures, windows, memory sizes, `VOICE_TAGS` |
| `memory.py` | `SessionMemory`, `FactBook`, `parse_remember` / `parse_forget`, `shape_questions` |
| `convstate.py` | `StateTracker`, `fit_prompt`: fixed-order, token-capped prompt assembly |
| `wellbeing.py` | `Tracker`: turns one conversation into a family summary (LLM paraphrase or rules), flush on idle |
| `core_client.py` | Thin HTTP client for core-api (`CoreError`); all state lives there |
| `appcmd.py`, `apps.py`, `app_replies.py`, `callcmd.py`, `media_understanding.py` | Voice commands for YouTube/news/WhatsApp/links/phone apps and call requests; fixed app replies |
| `qa.py`, `tools/web_search.py`, `tools/weather.py` | Answer router helpers, Tavily search, Open-Meteo weather; computed-in-code date facts |
| `checkins.py` | Reading a spoken check-in answer, spotting a volunteered topic |
| `relevance.py` | Is the reply about what she said? (word overlap, then a tiny LLM yes/no) |
| `langid.py`, `langswitch.py`, `textutil.py` | Language detection (script first, then Marathi/Hindi markers), "speak Hindi" switching, normalisation, `collapse_repeats` |
| `stream.py` | `/turn/stream` frames and ordering |
| `readings.py` | Spoken BP parsing (frozen) |
| `ratelimit.py`, `clock.py`, `prodcheck.py` | Per-user bucket (own copy by design), household clock, `ENV=prod` refusals |

## voice-agent

`services/voice-agent/` · start: `python agent.py dev` (local) or `python agent.py start` (cloud). Registers as
`agent_name="arjun"`. LiveKit Agents **1.8.6 pinned**, `livekit-plugins-gnani==1.8.6`.

| Module | Role |
|---|---|
| `agent.py` | `entrypoint` (per room: TTS probe, STT choice, `AgentSession`, event wiring), `Arjun.on_user_turn_completed` (filters then `Responder`), TTS classes (`SseTimbre`, `ClonedTimbre`, `make_tts`, `working_tts`), env loading (`load_agent_env`), startup prewarm |
| `responder.py` | **The ONE place a turn becomes speech** (spoken or tapped) |
| `bridge.py` | HTTP to reasoning: `reply_or_fallback`, `prepare_reasoning`, delivery pulls, fixed fallback lines |
| `streamclient.py` | WebSocket client of `/turn/stream` with reconnect/back-off |
| `prisma_v3.py` | Direct Prisma v3 adapter (`indic-auto`, keyterms, speaker names, ws/REST) |
| `clip.py` | Push-to-record: whole clip → Prisma v3 REST → normal turn |
| `voice.py`, `voiceprovider.py` | TTS text shaping, language/voice selection, voice tags; testing switch to Sarvam |
| `ttsgate.py`, `ttspipeline.py` | One Timbre request at a time; bounded first-sentence prefetch + prebuffer |
| `clonedvoice.py` | Consent-first cloned voice for companion chat only |
| `endpointing.py` | Mode-aware endpointing and `ConjunctionHold` |
| `media.py`, `mediamode.py`, `safety_words.py` | Media mode: forward only wake word / bare control / safety phrase; **local** safety check |
| `familyroom.py` | Family presence in the room → Arjun stays quiet |
| `sessionstate.py`, `idle.py`, `screenstate.py`, `usermeta.py` | Session state from LiveKit events, optional idle close, screen attributes for the page, dispatch metadata |
| `delivery.py` | Speak queued reminders/medicines in an open session |
| `emergencycall.py` | Trigger core-api escalation (family → help number) |
| `briefing_audio.py` | `/synthesize` helper (OGG/Opus) hosted in the worker |
| `soundevents.py` | Opt-in in-memory sound events; audio never written |
| `turnlog.py`, `applog.py` | One JSON timing line per turn (`eval/results/turns.jsonl`); file log `logs/voice-agent.app.log` |
| `audiowarm.py`, `langid.py`, `prodcheck.py` | soxr warm-up (fixes the Windows `LSX_FFT_BR` crash, **not confirmed live**), language id, `ENV=prod` refusals |

## scheduler

`services/scheduler/scheduler.py` (single file). Loop every `SCHEDULER_INTERVAL_SECONDS`: `fire-due`, medicine tick,
check-in tick, delivery sweep, conversation flush, briefing sweep, openers. A failing step logs a warning and
**does not stop the tick**. State: `_opened_today` in memory (a restart can allow a second opener; core-api's
decline gate still blocks after "नको"). Docker image only needs `httpx tzdata`.

## web

`web/` · Vite 5 + React 18 + strict TypeScript + Tailwind; tests with Vitest (`npm test`).

| Path | Role |
|---|---|
| `src/main.tsx` | Routing by pathname/query: `/elder-screen`, `/chat`, `/family-dashboard`, `?view=join`, `?ui=…`; elder vs family; user id from `?user=` / localStorage |
| `src/elder/ElderApp.tsx` | The elder app: connects by itself, hands-free listening, screens (home, listening, confirm, saved, safety, media, video call), undo, emergency location |
| `src/elder/*` | `MediaScreen`, `VideoCallScreen`, `ytPlayer`, `media`, `strings`/`i18n` (UI text in 10 languages), `useAppActions`, `RecorderBar` |
| `src/screens/*` | Elder screen components and `ChatScreen` |
| `src/voice/*` | `useArjunVoice` (LiveKit room + token), `usePushToRecord`, `clip`, voice `state`/`action` |
| `src/family/Dashboard.tsx` | The dashboard and its cards: `AccountGate`, `EmergencyCard`, `HealthProfileCard`, `KnownFactsCard`, `MedicineCheckCard`, `NamesCard`, `VoicesCard`, `AppLinksCard`, `BaseUrlWarning`, `JoinCall`, feed/polling/alarm helpers |
| `src/api.ts` | Typed client for `/core/*` and reasoning calls |
| `src/styles/tokens.css`, `app.css`, `ui.css` | Design tokens (source of truth) and styles |
| `src/components/*`, `src/preview/*` | shared UI primitives; UI gallery and debug pages |
| `server/access.ts` | Dev-server access lock and key injection (cookie roles, route allowlists, WebSocket check) |
| `api/*.ts`, `vercel.json` | Vercel functions replicating the proxy and gate in the cloud (unverified) |
| `scripts` in `package.json` | `dev` (vite --host), `build` (runs `check_no_browser_speech.py`, `tsc`, `vite build`), `test`, `typecheck` |

Elder UI rules ("Ghar" design system): Khadi ground, indigo primary, haldi accent (dark text only), kumkum = help
only, leaf = success; Tiro Devanagari headings + Mukta body; tap targets ≥ 14 mm (80–92 px), elder text ≥ 24 px,
contrast ≥ 4.5:1, icon + word always, one decision per screen, no swipes or timeouts, everything also spoken,
motion off under `prefers-reduced-motion`. **The elder page must speak through LiveKit + Gnani**: browser speech is
forbidden (the build fails via `scripts/check_no_browser_speech.py`).

## shared, eval, scripts, deploy

| Path | Role |
|---|---|
| `shared/schemas/intent.json`, `tool_calls.json` | JSON schema the LLM's understanding output is validated against |
| `shared/langid.py` | Shared language-id helper (copies live in reasoning and voice-agent) |
| `eval/` | Datasets (`cases.jsonl`, `emergency_cases.jsonl`, `dialogues.jsonl`, `companion_eval.jsonl`, `lang_eval.jsonl`, ...), `run_eval.py`, `REPORT.md`, `results/` (**only measured numbers**, `RESULTS.md`) |
| `scripts/dev-up.ps1` | Starts the local stack (see [OPERATIONS.md](OPERATIONS.md)) |
| `scripts/elder-kiosk.ps1` | Opens the elder screen full-screen in a Chrome profile started with autoplay allowed, so Arjun can speak with no tap. Use only on the elder's own device; `-Url`, `-NoKiosk` |
| `scripts/seed_heerabai.py`, `seed_apps.py`, `clean_demo_db.py` | Synthetic demo user "Aaji"; family links; reset (dry run by default, `--apply` after a backup) |
| `scripts/check_env.py`, `check_gnani.py`, `check_no_browser_speech.py`, `make_token.py`, `tunnel_url.py` | Env check, Gnani key check, build guard, LiveKit test token, tunnel URL → `.env` |
| `scripts/eval_*.py`, `voice_report.py`, `voice_latency_report.py`, `eval_realvoice.py` | Evaluations and timing reports |
| `scripts/telegram_test.py`, `checkin_demo.py`, `simulate_watch.py`, `converse_test.py` | Manual probes |
| `deploy/railway/*.json` | Railway service configs (unverified) |
| `design/`, `Arjun UI design.html` | UI reference only |
| `docker-compose.yml` | postgres + core-api + reasoning + scheduler + web (no voice-agent) |
