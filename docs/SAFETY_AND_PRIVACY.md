# Safety, privacy and honesty

What Arjun may and may not do, how each rule is enforced in code, and what is still unverified. The binding source
is [CLAUDE.md](../CLAUDE.md) ("Hard boundaries"); this page explains how they are implemented and tested. If this
page and CLAUDE.md ever differ, CLAUDE.md wins: fix this page.

> **Unverified:** the emergency and distress word lists (Marathi, Hindi, English and the seven other languages)
> have **not** been reviewed by a native speaker, and the external distress test set (T12) must pass before any
> public demo. Treat every "safe" claim below as "behaves this way in tests".

Contents: [The boundaries](#the-boundaries-and-where-they-live) · [Safety turn order](#safety-turn-order) ·
[Emergency vs distress](#emergency-vs-distress) · [Consent matrix](#consent-matrix) ·
[Medicine rules](#medicine-rules) · [What goes to third parties](#what-leaves-the-machine) ·
[Privacy and data](#privacy-and-data-handling) · [Honesty rules](#honesty-rules) ·
[Verification status](#verification-status) · [Changing a safety rule](#changing-a-safety-rule)

## The boundaries and where they live

| # | Boundary | Enforced by |
|---|---|---|
| 1 | **The LLM never touches the database.** It suggests; core-api validates and acts | reasoning has no DB access, only `CoreClient`; `propose` → `_validate_payload` in `core-api/main.py`; JSON schema `shared/schemas/intent.json`; `_claim_guard` blocks a reply that claims an action that did not happen |
| 2 | Reminders, appointments, medicines, contacts come from **SQL only**; RAG is for past stories only | `_dispatch` reads via core-api; `rag.py` searches only `story_memories` |
| 3 | **Never guess**: ambiguous AM/PM, missing date, "after the meal" without a meal → ask | `parser.py` returns a `Draft` with missing slots; `_create_reminder` asks; `ReminderIn` + `_check_reminder` reject bad input |
| 4 | **Arjun is an AI**; never claims to be human, to have feelings or family | `has_any(..., _AI_QUESTIONS / _NAME_QUESTIONS)` → fixed `ai_disclosure` template; companion prompt and sanitiser |
| 5 | **No medical advice**, diagnosis or medicine decisions. Exception (2026-11-10): one fixed self-care line for a mild, non-emergency complaint + "see a doctor if it does not get better" | `replies.SELF_CARE`; `gives_medical_advice` check on LLM replies; `refuse_safe` router route; never a medicine name, dose or diagnosis |
| 6 | **Medicines**: only the family creates/edits them (dashboard), never by voice or the LLM; read exactly as entered via a fixed template; skip/double/late/purpose/side-effect/missed-dose questions → "ask the doctor" and the family is told | no medicine-edit action exists in the ledger; `MED_LIST` template; `_medicine_action`; `medicines.py` |
| 7 | Health readings (frozen): never call a reading good/bad/high/low/normal; repeat numbers back | `readings.py` (both services); `bp_readings` columns are raw numbers only |
| 8 | **Safety checks run first on every turn**, rules only, and work with core-api and the LLM down | `_handle` steps 2–3; `main.py` exempts safety text from rate limits; `voice-agent/safety_words.py` and `/media/gate` keep a local copy for media mode |
| 9 | **No engagement tricks**: no streaks, no "I missed you", nothing discouraging human contact | reply templates and companion prompt; no such fields in the schema |
| 10 | General knowledge / recipes / festivals from model knowledge are allowed; **never** medical advice, and **never news from model memory** | answer router (`know` only at ≥ 0.9 confidence and never time-sensitive; news only from live Tavily results whose domain the family approved; otherwise "I have no information") |
| 11 | **Stories are private by default**; shared only when she asks; "he visar" deletes; never invent memories | `story_memories.share_status`; Memory Book returns shared only; recall only from stored text |
| 12 | **Secrets**: one root `.env`; keys read only by the service that needs them; never in React, Git or logs | [CONFIGURATION.md](CONFIGURATION.md); `scripts/check_no_browser_speech.py`; `test_gnani_key_only_in_create_embedding` |
| 13 | **Never invent numbers**: only measured values in `eval/results/RESULTS.md` | process rule |
| 14 | **Never claim delivery that did not happen** ("fired" ≠ "heard"; call log is honest) | `deliveries.spoken_at`, `emergency_calls.status` |

## Safety turn order

On **every** turn, before anything else (`reasoning_svc/turn.py: _handle`):

1. Emergency check → fixed template.
2. Distress check → fixed template.
3. If neither matched but a body/health word is present: a second look (`_second_look`) can still raise either.

Properties (tested): no network call is needed for 1–2; the replies are templates in `replies.py`; text matching
these checks is **never rate-limited** in `/turn`; and in media mode the voice-agent runs its own local check
(`safety_words.py`) before sending anything, so safety never waits for another service. The LLM can *raise* a
seriousness level but never lower the rules' floor, and cannot cancel a safety template.

## Emergency vs distress

| | Physical emergency | Emotional distress |
|---|---|---|
| Examples | chest pain, can't breathe, a fall now, fainting, bleeding | "I feel so alone, I want to end it", deep sadness |
| Reply | Fixed: call 112 / call out to someone near; never diagnose; never keep chatting | Fixed: stop the story, respond gently, offer a family call, mention **Elderline 14567 (8 AM–8 PM)** |
| Family alert | **Always**, even with consent off (decision 2026-10-24): dashboard banner naming the configured contacts (+ Telegram when enabled) | **Only with** `consent_distress_alert` |
| Calls | Auto-calls (decision 2026-11-08): family contacts (max 2) → "तुम्ही ठीक आहात का?" → wait `ARJUN_EMERGENCY_WAIT_S` (10 s) → the **family-saved** help number, reading the saved address. **Never dials 112.** Only with `CALLS_ENABLED=1` + Twilio; each call logged as placed / failed / skipped | none |
| Location | Device sends live location **only while an emergency is open**; discarded otherwise; shown as a map link | none |
| Stored | a notification and, if configured, call rows; **no transcript** | `distress_events` row (`caregiver_alerted`); **no transcript** |

Pending actions are rejected when distress is detected, and a pending yes/no is dropped. The dashboard alert says
honestly what was and was not sent (boundary 14).

## Consent matrix

One consent flag: `users.consent_distress_alert`, labelled in the dashboard **"share how she is doing"**.

| What the family sees | Consent off | Consent on |
|---|---|---|
| Reminders, appointments, medicines, what she did | ✔ | ✔ |
| Help request (she asked for help) | ✔ level + note | ✔ |
| Physical emergency | ✔ always | ✔ |
| Mood word, short conversation summary | ✘ | ✔ |
| Distress and loneliness notes | ✘ | ✔ |
| The list of life facts Arjun stores | ✘ | ✔ |
| A body-complaint fact is **stored** | ✘ | ✔ |
| Transcripts of what she said | **never** | **never** |

Life facts are stored for Arjun's own use regardless of sharing consent (they make it a better listener), but the
family sees the list only with consent, and **deleting a fact never requires consent**. Cloned voices need a
separate, recorded consent statement from the voice's owner.

## Medicine rules

* Only the family writes medicines (dashboard → `POST/PATCH/DELETE /users/{id}/medicines`).
* Name, dose, timing, doctor and instructions are returned **exactly as entered**, via a fixed template, never
  LLM-paraphrased or translated.
* "आता कोणती गोळी?" / "माझी औषधं कोणती?" are answered from SQL (`MED_LIST`).
* A skip / double / late / "why" / side-effect / missed-dose question gets the safe line first ("दोन डोस एकत्र घेऊ
  नका"), then "ask the doctor", and the family is told. Arjun never says "take the missed dose" or "take two".
* "Taken" is **self-reported** and labelled so. Not confirmed after `max_reminders` → `unconfirmed` → **family only**
  is told. No adherence scores, streaks or guilt.
* `health_profiles` (allergies, doctor, notes) are never sent to the LLM and never used to give advice.

## What leaves the machine

| Destination | What is sent | When | Controlled by |
|---|---|---|---|
| **Gnani** (Prisma, Timbre) | her speech audio (STT), reply text (TTS) | every voice turn | `GNANI_API_KEY` |
| **LiveKit Cloud** | the audio stream and room metadata (`user_id`, `language`) | every session | `LIVEKIT_*` |
| **Hosted LLM** (Sarvam by default; named in `LLM_PROVIDER_NAME`) | **what she says in chat/understanding turns**, recent history, a short context block (name, family names, today's items, facts) | non-safety turns when configured | `SARVAM_API_KEY` / `LLM_*`. Safety turns, medicine answers, health profile and confirmations are **not** sent |
| **Sarvam** (summaries) | a conversation to summarise | only with consent on and a key set; otherwise rule-built summaries | consent flag |
| **Tavily** | a search query | live-fact questions | `TAVILY_API_KEY` |
| **Open-Meteo** | a city name | weather | none (no key) |
| **YouTube API** | a search phrase (from core-api, key server-side) | media requests | `YOUTUBE_API_KEY` |
| **Telegram** | alert text, voice briefing, join link; **no transcripts** | when enabled | `TELEGRAM_*` |
| **Twilio** | phone numbers the family saved, a spoken script | emergency only, `CALLS_ENABLED=1` | `TWILIO_*` |

Because chat turns reach a non-Gnani provider, **demo data must be synthetic**, and the public write-up must name
the provider (contest rule; open question 5 on Discord). Gnani's EULA clause 16 may forbid publishing benchmark
numbers: report **system** results ("8/10 reminders set correctly"), not Prisma WER, until Gnani confirms.

## Privacy and data handling

* **No raw audio is stored** anywhere (`*.wav/mp3/ogg/opus/m4a/flac` are git-ignored). `sound_events` keep a label and
  confidence only. The cloned-voice reference clip goes to Gnani once and only an encrypted embedding is kept.
* **No transcripts in the database or the family views.** The turn log (`eval/results/turns.jsonl`) holds timings;
  `ARJUN_DEBUG_VOICE` lines hold lengths, never words. Logs never contain keys.
* **Synthetic data only**: no real phone numbers, Aadhaar, PAN or recorded calls. `scripts/seed_heerabai.py` creates
  user "Aaji".
* **Stories** are private by default; shared only when she says so; "he visar" deletes.
* **Location** is stored only during an open emergency and kept 15 minutes for linking.
* **Emergency call log** keeps only the last four digits of a number.
* **Accounts** use Argon2id, 12 h sliding sessions, rate-limited login/pairing/sign-up, a CSRF origin check, and
  role-limited cookies on the tunnel. Per-elder dashboard routes still pass the key-injecting proxy: production
  needs a real proxy (T14).
* **Deleting**: stories, facts, contacts, medicines, links, voices and devices can be deleted by the family; a
  deleted cloned voice keeps an audit row (when it was used) but not the embedding.
* **Sessions in memory** (history, summary, drafts) are lost on a reasoning restart.

## Honesty rules

* Arjun says it is an AI whenever asked, and never claims feelings, a family or a body.
* The write-up must say: speech in = Gnani Prisma, speech out = Gnani Timbre, the conversation LLM = the hosted
  non-Gnani provider named in `LLM_PROVIDER_NAME` (Sarvam-105B), Evon = not used.
* **A demo whose voice is not Gnani's is a misleading demo** and forbidden: do not use `ARJUN_VOICE_PROVIDER=sarvam`
  or browser speech (`scripts/check_no_browser_speech.py` guards the build).
* No bought engagement, no engagement swaps, no plagiarism (contest rules).
* "Fired" means "the due time passed"; "spoken" means playback finished; a call is "placed", "failed" or
  "skipped" exactly as it happened.
* Report only measured numbers (`eval/results/RESULTS.md`). The eval sets were written alongside the parsers, so
  100% there says nothing about real speech.

## Verification status

| Area | State (2026-11-15) |
|---|---|
| Unit/integration tests | core-api 367, reasoning 1479, voice-agent 445, scheduler 7, Vitest 266, `tsc`, Ruff, web build, `eval/run_eval.py` all passed (STATUS.md) |
| Emergency lexicon | recall 87/87 on the rules-only set, 0/12 harmless flagged; **set written alongside the lexicon**, so it says nothing about real speech |
| Native-speaker review | **none yet** for any lexicon or the seven extra languages |
| External distress test (T12) | **must pass before a public demo**; not done |
| Live voice session on current code | **not run**; STT live and full STT→TTS turn unverified |
| Emergency auto-calls with real Twilio | not tested |
| Phone microphone / apps by voice | tested by automation only |
| Cloud deployment | not deployed |

See [DETAILS.md](DETAILS.md) for the complete, dated limitations list.

## Changing a safety rule

1. Read the relevant boundary in CLAUDE.md. Do not "improve it away".
2. Edit the lexicon in `distress.py` / `safety_langs.py` (the ONE source) or the template in `replies.py`. Then run
   `python scripts/gen_safety_words.py` to regenerate `voice-agent/safety_words.py` (the import-free local copy used
   in media mode). **Never hand-edit that file**; `--check` exits 1 when it is out of date.
3. Add cases to `eval/emergency_cases.jsonl` (and a harmless counter-case), run `python eval/run_eval.py` and the
   reasoning and voice-agent tests.
4. Keep care-mode and safety replies as fixed templates; never route them through a free-form LLM.
5. Update STATUS.md and mark anything unverified as unverified.
