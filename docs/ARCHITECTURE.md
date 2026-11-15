# Architecture

How Arjun is put together, how one spoken sentence travels through it, and why it is built this way.
Last reviewed against the code on 2026-11-15. Names of files and functions are real; where something is
unverified or only tested in isolation, it says so.

Contents: [1. The idea](#1-the-idea) · [2. Services](#2-services) · [3. The voice path](#3-the-voice-path) ·
[4. The turn pipeline](#4-the-turn-pipeline-reasoning) · [5. Acting and undoing](#5-acting-and-undoing) ·
[6. Delivery queue](#6-the-delivery-queue-reminders-and-medicines-reaching-her-ears) ·
[7. Emergency flow](#7-emergency-flow) · [8. Family side](#8-the-family-side) ·
[9. Where state lives](#9-where-state-lives) · [10. Failure behaviour](#10-failure-behaviour) ·
[11. Security model](#11-security-model) · [12. Design decisions](#12-design-decisions-and-why)

---

## 1. The idea

Arjun is a voice companion for elderly Indians who speak Marathi, Hindi, English or a mix. It is two
products in one:

| Half | Does | Must be |
|---|---|---|
| **Reliable assistant** | reminders, appointments, "what is today?", medicines, help requests, family calls | exact, boring, predictable, never wrong |
| **Warm listener** | chat, stories, interests, Memory Book, festivals, recipes, general questions | warm, short, honest that it is an AI |

The two halves have opposite risk profiles, so they are built differently:

* **Everything that touches her health, time or safety is rules + SQL + fixed templates.** A language model is
  never allowed to write a reminder, a medicine line or a safety reply.
* **A hosted LLM is used for meaning and conversation only.** It *suggests*; core-api (deterministic code)
  *validates and acts*.

> "Arjun is a bridge to people, not a replacement for them." No streaks, no "I missed you", nothing that
> discourages human contact.

## 2. Services

```
                    +--------------------------------------------------------------+
                    |                     Browser (web/ , :5173)                   |
                    |   Elder app (/elder-screen, /chat)    Family dashboard       |
                    +------+----------------------------+--------------------+-----+
        LiveKit audio/data  |                            | /core/* (proxy)    |
                    +--------v---------+                  |  adds X-API-Key    |
                    |  LiveKit Cloud   |                  |                    |
                    +--------+---------+                  |                    |
                  dispatch "arjun" |                      |                    |
                    +--------v---------+  HTTP / WS   +---v--------------------v---+
                    |   voice-agent    +------------> |        core-api  :8000     |
                    |  (worker :8002)  |  /turn,      |  FastAPI + SQLAlchemy       |
                    |  Prisma STT in   |  /turn/stream|  SQLite (dev) / Postgres    |
                    |  Timbre TTS out  |              +---^-----------^------------+
                    +--------+---------+                  |           |
                             | POST /turn                 |           | internal ticks
                    +--------v---------+  X-API-Key       |       +---+-----------+
                    |    reasoning     +------------------+       |   scheduler   |
                    |      :8001       |                          | polls every   |
                    | safety > LLM >   |<-------------------------+ 30 s          |
                    | rules > dispatch |   /conversations/flush-idle, /opener     |
                    +--------+---------+                          +---------------+
                             | OpenAI-compatible chat (non-Gnani)         Telegram / Twilio
                    +--------v---------+                           (called by core-api only)
                    |  Sarvam-105B     |
                    +------------------+
```

| Service | Folder | Port | Language | Owns |
|---|---|---|---|---|
| core-api | `services/core-api` | 8000 | Python, FastAPI, SQLAlchemy | **All persistent state.** Validation, consent rules, undo, delivery queue, Telegram, Twilio, LiveKit tokens, accounts |
| reasoning | `services/reasoning` | 8001 | Python, FastAPI | **The brain.** Safety rules, understanding, dispatch, companion chat, memory, summaries. Holds only in-memory session state |
| voice-agent | `services/voice-agent` | 8002 (small HTTP helper) | Python, LiveKit Agents 1.8.6 | **Ears and mouth.** Prisma STT, Timbre TTS, endpointing, media mode, delivering queued items, emergency calls trigger |
| scheduler | `services/scheduler` | none | Python, httpx | A 30 s clock. Triggers "due" work in core-api and reasoning |
| web | `web/` | 5173 | React 18, TypeScript, Vite, Tailwind | Elder app and family dashboard. Dev proxy injects the API key |

Rules of the house:

* **core-api is the only process that writes the database.** Reasoning and scheduler call it over HTTP.
* **Services share HTTP contracts, not code** (e.g. `ratelimit.py` exists in both core-api and reasoning on
  purpose). `shared/` holds only JSON schemas and one language-id helper.
* **Secrets are scoped.** `GNANI_API_KEY` and `LIVEKIT_*` are read by voice-agent (and `LIVEKIT_*` for token
  signing in core-api); `LLM_API_KEY`/`SARVAM_API_KEY` only by reasoning; Twilio and Telegram only by core-api.
  The browser never sees any key. See [CONFIGURATION.md](CONFIGURATION.md).

## 3. The voice path

```
 elder taps once
   -> web: POST /core/livekit/token {user_id, language}           (core-api, livekit_token.py)
        returns {url, token, room, identity}; room name is FRESH each time and the token carries an
        explicit dispatch for agent_name="arjun" + metadata {user_id, language}
   -> browser joins the LiveKit room, publishes the microphone
   -> LiveKit dispatches the "arjun" worker to the new room             (agent.py: entrypoint)
   -> worker connects, reads user_id from the dispatch metadata, picks TTS (Timbre v3.0 probe -> fallback v2.5)
   -> audio frames -> Silero VAD + endpointing -> Gnani Prisma STT      (plugin or prisma_v3.py)
   -> transcript -> Arjun.on_user_turn_completed()                      (agent.py)
        filters: video-call active, family in room, media mode, conjunction hold ("... आणि")
   -> Responder.respond(text)                                           (responder.py, the ONE place a turn becomes speech)
        -> reasoning  POST /turn   (or WebSocket /turn/stream, ARJUN_STREAM=1)   (bridge.py / streamclient.py)
        <- {reply, speech, intent, mode, language, action, screen, speech_style, ...}
   -> Timbre TTS (SSE, sentence by sentence, with first-sentence prefetch)  -> audio track -> speaker
   -> participant attributes (arjun.action, screen state) tell the page what to show/open
```

Important details:

* **Explicit dispatch.** The worker registers as `agent_name="arjun"` and joins *only* rooms that dispatch it.
  Dispatch happens when the room is **created**, so each session needs a fresh room name. The LiveKit Console
  with "No agent selected" never dispatches it. `scripts/make_token.py` builds a token with the dispatch.
* **No LLM inside the voice session.** `Arjun(Agent)` is constructed with placeholder instructions and every
  turn raises `StopResponse()` so LiveKit's built-in LLM reply never runs. Replies come from reasoning.
* **A reasoning failure never means silence.** `bridge.reply_or_fallback` speaks a fixed line if reasoning
  times out (`REASONING_TIMEOUT_S`, default 7.5 s) or errors.
* **Mode-aware endpointing** (`endpointing.py`): care mode waits 0.8 s min / 2.5 s max of silence, chat mode
  1.6 / 4.0 s. A sentence ending in आणि / पण / म्हणजे / की is *held* for more speech
  (`ConjunctionHold`); if nothing follows, it is answered after `ARJUN_HELD_ANSWER_S` (4 s). All values are
  placeholders to tune on elderly speech.
* **Language is per turn.** Each reply is spoken in the language of that turn (Hindi now, Marathi next).
  `langid.py` (script first, then word markers for the Marathi/Hindi pair) corrects Prisma's frequent
  mr/hi confusion. A spoken "हिंदीत बोला" switches the reply language until changed.
* **Media mode** (`media.py`, `mediamode.py`, `soundevents.py` is separate): while a YouTube video plays, the mic
  hears the video, so most transcripts are discarded. Only a wake word ("अर्जुन ..."), a bare control
  ("थांबव", "पुढचं", "आवाज कमी") or a safety phrase is forwarded. The safety check is local
  (`safety_words.py`), so it never waits for another service.
* **Family in the room / video call.** If a family member has joined the LiveKit room, Arjun stays quiet
  (`familyroom.py`); during a call only safety phrases and a bare stop are processed.
* **TTS probing.** At worker start a one-word synthesis probes Timbre v3.0 / `Avinash`; if it fails, the
  session uses `timbre-v2.5` / `Omkar` (verified live 2026-10-21). The probe is bounded so a hung Timbre
  cannot keep the session from listening. Timbre v3.0 voice tags (`<laugh>` etc.) are stripped for other
  models and never shown on screen.
* **Cloned voice** (`clonedvoice.py`): with family consent a relative's voice can be used for companion chat
  only, never for safety, medicines or reminders.
* **Testing switch** `ARJUN_VOICE_PROVIDER=sarvam` swaps in Sarvam STT/TTS. Never record or publish a demo
  with it: the contest requires Gnani voice.

Push-to-record path: the elder page can also record a whole clip and POST it (`clip.py`, Prisma v3 REST) which
then runs through the same `Responder`.

## 4. The turn pipeline (reasoning)

`POST /turn {user_id, text, language_code?, reply_language?}` → `TurnEngine.handle()` → `_handle()` in
`reasoning_svc/turn.py`. The order is **fixed**:

| # | Step | Needs core-api? | Needs LLM? |
|---|---|---|---|
| 0 | Clean the transcript (collapse "हो हो हो कर कर" recognizer loops); system markers (`[video_call_missed]` ...) handled | no | no |
| 1 | Empty/noise → silent (twice in a row → "come closer" line) | no | no |
| 2 | **Physical emergency check** (`distress.is_emergency`) → fixed template, stop | no | no |
| 3 | **Distress check** (`is_distress`) → fixed gentle template, stop | no | no |
| 4 | Second look: a body/health word no rule recognised (`_second_look`, may use a tiny LLM call) | no | optional |
| 5 | Load the user (core-api). If it fails: fixed error line, never silence | yes | no |
| 6 | Language resolution (this turn's language wins), spoken switch ("हिंदीत बोला") | no | no |
| 7 | Speech style commands ("हळू बोला", "नेहमीसारखं बोल"), "repeat that" (may simplify) | no | optional |
| 8 | "लक्षात ठेव" / "विसरून जा" memory commands (rules only) | yes | no |
| 9 | Weather follow-up state ("which city?") | yes | no |
| 10 | **ONE LLM understanding call** (`_understand`): intent, slots, reply, confidence, route (know / search / tool / refuse_safe) | yes | **yes** |
| 11 | AI disclosure ("are you human?", "your name?") → fixed honest line | no | no |
| 12 | Open yes/no, media choice cards, BP reading, open check-in answer | yes | no |
| 13 | Intent merge: LLM intent, else **rule parser** (`parser.py`) as fallback | no | no |
| 14 | Distress/symptom/loneliness re-checks on the parsed intent; medicine list question | yes | no |
| 15 | Live facts (weather, news, scores) only on the LLM's say-so, after all safety paths | yes | search |
| 16 | **Dispatch** (`_dispatch`): CREATE_REMINDER, SHOW_DAY, MEDICINE_*, SHARE_STORY, OPEN_MEDIA, CHAT ... | yes | companion reply only |
| 17 | Guards: claim guard (a reply must not claim an action that did not happen), cardiac guard, relevance guard | – | small yes/no |
| 18 | Result: `TurnResult` (reply, speech, intent, mode, screen, action, speech_style, trace) | – | – |

Key properties:

* **Safety first, rules only.** Steps 2–3 never wait for core-api or the LLM and are never rate-limited
  (`/turn` exempts emergency/distress text from the per-user bucket).
* **The model chooses the meaning; the code decides the action.** The LLM returns intent+slots as strict JSON
  validated against `shared/schemas/intent.json`. A chat reply can never create a reminder or touch a medicine.
* **Rules are the fallback**, used when the LLM is not configured, times out (`LLM_TIMEOUT_S`, 6 s budget for
  *all* LLM calls in a turn), returns bad JSON, or reports confidence < 0.4 for an action intent.
* **Care-mode and safety replies are fixed templates** (`replies.py` for mr/hi/en, `replies_langs.py` for the
  other seven languages). No LLM paraphrases or translates them.
* **Answer router** (2026-11-09): for questions the LLM labels `know` (answered from model knowledge, only at
  ≥ 0.9 confidence and never for anything time-sensitive), `search` (Tavily; news only from family-approved
  domains), `tool` (weather via Open-Meteo, time/date), or `refuse_safe` (fixed "ask your doctor" line).
* **Per-turn trace** (`TurnResult.trace`) records route (`llm`/`rules`), reason for rules fallback, timings.

### Streaming
`WebSocket /turn/stream` (`stream.py`) is the streaming twin of `/turn`: only complete, guarded sentences are
emitted (not raw tokens) so voice-agent can start Timbre on the first sentence while the rest is generated.
`/turn` is unchanged and is the client's fallback. `POST /turn/prepare` is a millisecond rules-only pre-step.

### Memory (`memory.py`, `convstate.py`)
* **Session memory**: the last `ARJUN_SESSION_EXCHANGES` (20) exchanges word for word, older ones compressed
  into a running summary; after `ARJUN_SESSION_IDLE_MIN` (30) minutes a conversation ends and is compressed. In
  process memory only: a restart forgets it.
* **Long-term facts** (`user_facts` in core-api): short facts about her life ("नातू आर्यन", "likes bhajans").
  Written after a conversation ends (source `auto`) or on "हे लक्षात ठेव" (`explicit`). Facts refuse numbers,
  addresses, money, medicines and diagnoses. The family can delete any fact.
* **Prompt assembly** (`convstate.py`): history + state + context + facts in a fixed order under a token cap
  (`ARJUN_PROMPT_TOKEN_CAP`, 2600). `ARJUN_CONTEXT_STATE=0` restores the old assembly.
* **Stories** (`story_memories`) are private by default; recalled only from stored text, never invented.

## 5. Acting and undoing

Decision of 2026-10-31: **no yes/no questions.** Flow for "उद्या सकाळी दहा वाजता डॉक्टर":

```
reasoning  -> core-api  POST /users/{id}/actions/propose   {action_type: CREATE_REMINDER, payload}
core-api   validates (_validate_payload), stores a PendingAction, returns it
reasoning  -> core-api  POST /users/{id}/actions/{id}/confirm      (immediately, in no-question mode)
core-api   executes (creates the reminder), keeps an undo window of UNDO_TTL_S = 180 s
Arjun says ONE line:  "ठेवली: उद्या सकाळी 10:00, डॉक्टर. बदलायचं असेल तर 'नको' म्हणा."
"नको"/"चुकलं" within UNDO_WINDOW_S (150 s) -> POST .../actions/{id}/undo
```

* Supported action types: `CREATE_REMINDER`, `COMPLETE_REMINDER`, `REQUEST_CAREGIVER`, `SHARE_STORY`,
  `SAVE_STORY`, `MEDICINE_TAKEN`, `MEDICINE_SNOOZE`. There is **no** medicine create/edit action: medicines are
  family-only (dashboard).
* **Missing details are still asked** (which day? AM or PM? which meal?). Arjun never guesses.
* A help request cannot be unsent; undo sends the family a *second* note instead.
* `ARJUN_ASK_BEFORE_ACTING=1` restores the older spoken "...ठेवू का?" yes/no flow (the older test suites run
  in that mode). A pending yes/no is protected: anything that is not yes/no/cancel gets the same question again,
  and a pending action expires after `PENDING_TTL_S` (300 s).

## 6. The delivery queue (reminders and medicines reaching her ears)

```
scheduler tick (30 s)
  POST /internal/reminders/fire-due     due reminders -> status "fired", Notification, enqueue Delivery
  POST /internal/medicines/tick         creates today's MedicineDose rows, reminds, marks "unconfirmed" after N
  POST /internal/checkins/tick          (frozen feature) asks meal/walk check-ins if the family enabled them
  POST /internal/deliveries/sweep       retires finished items, applies late/backlog rules, tells family
  POST reasoning /conversations/flush-idle   idle conversations -> one summary line for the family
  POST /internal/briefings/send-due     daily Telegram voice briefing at BRIEFING_TIME
  POST reasoning /opener/{id}           one interest opener a day (LOGGED ONLY, not spoken)
```

A voice session then **pulls** items (`/delivery/next` via reasoning → core-api `deliveries/.../claim`):

```
queued -> speaking (claimed atomically) -> spoken (only after playback really finished) -> acknowledged
queued -> shown_only     not spoken on purpose (medicine waited past its window; over BACKLOG_CAP = 3)
speaking -> queued       released (interrupted, TTS failed, session vanished)
speaking -> undelivered  the 3rd release (MAX_TRIES = 3); stays on screen, family told once
queued -> superseded     reminder done / dose handled / replaced
```

Honesty rule (boundary 14): **"fired" only means "the due time passed."** Only `spoken_at` means she heard it.
Items older than 120 s are "late"; a claim not finished within 90 s is stale. Proactive speech needs a
dedicated, always-open elder device because browsers block audio until a tap.

**Medicines** (`medicines.py`): family-created; a dose's due time is a fixed clock time or a family-set
wake/breakfast/lunch/dinner time plus an offset. Name + dose are read exactly as entered from a fixed template.
"Taken" is self-reported and labelled so. After `max_reminders` (default 3) with no confirmation the dose is
`unconfirmed` and **only the family** is told. No adherence scores, streaks or guilt.

## 7. Emergency flow

1. Reasoning's rules detect a physical emergency (chest pain, can't breathe, a fall now, fainting, bleeding)
   → fixed reply ("call 112 / call out to someone near") and `POST /users/{id}/distress` with
   `kind: "emergency"` in core-api (`main.py: record_distress`). **The family is always alerted**, even with distress consent off (decision
   2026-10-24): a prominent dashboard banner naming the configured contacts, plus Telegram when enabled.
2. Voice-agent (`emergencycall.py`) then calls `POST /internal/users/{id}/emergency/escalate`:
   * stage `family`: phone up to 2 family contacts with numbers, ask "तुम्ही ठीक आहात का?", wait
     `ARJUN_EMERGENCY_WAIT_S` (10 s);
   * stage `help`: if no answer, phone the **family-saved** help number (nurse desk / warden / hospital) and
     read the saved address.
3. **Arjun never dials 112 itself** or any number the family did not save.
4. Calls run only with `CALLS_ENABLED=1` plus Twilio keys (core-api only). Every attempt is stored in
   `emergency_calls` with its honest status: `placed`, `failed`, `skipped_disabled`, `skipped_no_number`.
   Escalation is de-duplicated for 10 minutes.
5. Location: the elder device sends its position **only while an emergency is open**; core-api discards it
   otherwise (15-minute window) and the family receives a Google Maps link on the dashboard and Telegram. No
   continuous tracking.
6. Emotional distress is different: stop the story, respond gently, offer a family call, mention Elderline
   14567 (8 AM–8 PM), alert the family **only** with consent. Both word lists are **unverified** until a
   native speaker reviews them.

Status: emergency auto-calls are untested with a real Twilio call.

## 8. The family side

* **Dashboard** (`web/src/family/Dashboard.tsx`): reminders, appointments, medicines, contacts, day card,
  Memory Book (shared stories only), apps & links, emergency settings, health profile (never sent to the LLM),
  known facts (consent-gated), cloned voices, deliveries, performance card (numeric only), and the live feed.
* **Live feed** (`feed.py`): every `Notification` and `Wellbeing` row automatically becomes a `FeedEvent`.
  Pushed over `WebSocket /ws/users/{id}/feed`, with `GET /users/{id}/feed?after=` polling as fallback.
* **Wellbeing** (`wellbeing.py`): per conversation a seriousness level (normal/watch/urgent/emergency), a mood
  word and a short paraphrased summary. **Never a transcript.** Mood, summaries, distress and loneliness are
  shown **only** with `consent_distress_alert` ("share how she is doing"); without it the family sees what she
  did and the level for help requests/emergencies only. The LLM may *raise* a level, never lower the rules floor.
* **Telegram** (`telegram.py`): free family alerts (and a "join call" button built from `BASE_URL`), voice
  briefings (`briefings.py`), video-call links. Never sends transcripts.
* **Family video call** (`family_call.py`, `joins.py`, `video_calls.py`): a signed 30-minute join link turns
  into a LiveKit token for the elder's current room.
* **Accounts** (`auth.py`, `ARJUN_AUTH=1`): email + Argon2id password, 12 h sliding session (30 d max) in the
  `arjun_session` cookie, memberships (owner/family) per elder, invite links, and **paired elder devices**
  (`arjun_device` cookie from a one-time pairing code). The first account ever created owns the elders that
  already exist. Limitation: per-elder dashboard routes still pass through the key-injecting dev proxy, so the
  elder picker is the boundary in the browser, not the API; production needs a real proxy (T14).

## 9. Where state lives

| State | Where | Survives restart? |
|---|---|---|
| Users, reminders, appointments, medicines, doses, contacts, stories, facts, notifications, wellbeing, feed, deliveries, check-ins, accounts, voices, emergency data | core-api database (SQLite file `arjun.db` locally, Postgres in Docker/cloud) | yes |
| Pending/undoable actions | `pending_actions` table | yes |
| Session history + running summary, open drafts, media choice cards, weather follow-up, repeat counters, language switch | reasoning process memory | **no** |
| Conversation tracker for the family summary | reasoning memory, flushed by the scheduler after `CONVERSATION_IDLE_S` (180 s) | **no** |
| Room → user map for the family join link | core-api memory (`livekit_token._rooms`) | **no** (elder's next tap restores it) |
| "Opener sent today" | scheduler memory | **no** (core-api's decline gate still blocks openers after "नको") |
| Turn timings | `eval/results/turns.jsonl` (voice-agent writes, core-api reads numeric fields) | yes |
| Raw audio | **never stored** | – |

There are **no migrations**. `Base.metadata.create_all` creates missing tables; `db.ensure_columns` adds
columns listed in `ADDED_COLUMNS` to old databases at startup; `reconcile_schema` sets aside/adds, never drops.

## 10. Failure behaviour

| What fails | What happens |
|---|---|
| LLM down / slow / over limit | rules answer at once (a voice turn never queues); casual chat falls back to four fixed lines |
| core-api down | safety still works; other turns get the fixed error line; voice still speaks |
| reasoning down | voice-agent speaks `bridge.reply_or_fallback` line; safety words still checked locally in media mode |
| Timbre v3.0 probe fails | session uses `timbre-v2.5` / `Omkar` |
| Cloned voice fails | Arjun speaks in its own voice |
| LiveKit network drops | worker may be killed by an FFI panic (`timed out waiting for ReadyForRoomEventRequest`) and is **not** auto-restarted locally; restart with `scripts\dev-up.ps1 -Only voice-agent` |
| Telegram off/unreachable | alerts stay on the dashboard; the join button is omitted and a warning is logged |
| Twilio off | emergency calls recorded as `skipped_disabled`, never claimed |

## 11. Security model

* **Service key.** All core-api routes except health, LiveKit token (own auth), family join (signed token),
  WebSocket feed (self-authenticated) and `/auth/*` require `X-API-Key` = `CORE_API_KEY` (constant-time compare).
  core-api **refuses to start** without it (tests use `ARJUN_TESTING=1`).
* **Browser never holds the key.** The Vite dev proxy (`/core/*`) injects it. Through a tunnel it injects it only
  for requests carrying a valid role-limited access cookie (`web/server/access.ts`, `ARJUN_ACCESS_CODE`);
  elder cookie → elder routes only, family cookie → dashboard routes only; the signed Telegram join link is the
  only public path. A key in a WebSocket URL is refused. Vercel (`web/api/*`) plays this role in the cloud.
* **Accounts** (optional): password sessions or device cookies authorise `/parents*` and per-elder routes.
* **CSRF brake** (`origin_guard.py`): a cookie-carrying unsafe request whose `Origin` is not `BASE_URL`/localhost → 403.
* **Rate limits**: core-api token bucket per client (`CORE_RATE_*`, 429 + Retry-After; `/health` and
  WebSockets exempt); reasoning per-user `/turn` bucket (safety exempt); LLM concurrency 4 and 60/min.
* **ENV=prod startup checks** (`prodcheck.py` in core-api, reasoning, voice-agent; scheduler checks its three
  URLs/keys): refuse to start, naming (never printing) missing/unsafe settings, e.g. a `CORE_API_KEY` shorter
  than 32 characters, `*` in `CORS_ALLOW_ORIGINS`, `ARJUN_TESTING=1`, open signup.
* **Privacy**: stories private by default, no raw audio, no transcripts in family views, synthetic demo data
  only. What she says in chat turns **is sent to the hosted LLM provider** (named in `LLM_PROVIDER_NAME`).

## 12. Design decisions and why

| Decision | Why |
|---|---|
| Rules for safety, fixed templates for care | Predictable and testable; works with core-api and the LLM down |
| One LLM understanding call per non-safety turn, rules as fallback | Better coverage of messy code-mixed speech than a parser; the app still works with no LLM at all |
| LLM never touches the DB | A hallucinated sentence cannot create or alter a reminder or medicine |
| Act-then-undo instead of yes/no | Elderly users answer "हो"/"नाही" unreliably; undo is easier than confirming |
| Fresh LiveKit room per session | Agent dispatch happens at room creation |
| Services share HTTP, not code | Independent deploys; each can be replaced or scaled |
| No migrations (frozen) | Scope control before the contest deadline; `ensure_columns` covers additive changes |
| Evon not used (T9, 2026-10-24) | Not on the API platform; needs an 80 GB GPU. `EVON_*` names still alias `LLM_*` |
| Sarvam-105B with thinking off | Latency; any `<think>` text is stripped |
| Hosted LLM disclosed as non-Gnani | Contest rules: Gnani must be genuinely used (STT + TTS) and the demo voice must be Gnani's |

Deeper engineering notes (latency numbers, concurrency, rate limiting, Prisma audit) are in
[ENGINEERING.md](ENGINEERING.md).
