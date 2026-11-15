# Data model

Every table in core-api (`services/core-api/core_api/models.py`). SQLAlchemy 2.0 declarative models; SQLite
locally (`arjun.db` in the core-api working directory), Postgres 16 with pgvector in Docker. Timestamps are
**naive household-local time** (IST, `ARJUN_TZ`) unless noted; models using `utcnow` for `created_at` store UTC.

There are **no migrations**. At startup core-api runs `reconcile_schema` (set aside / add, never drop),
`Base.metadata.create_all`, then `ensure_columns` (adds columns listed in `db.ADDED_COLUMNS` to old databases).
To add a column to an existing table, add the model field **and** an `ADDED_COLUMNS` entry (nullable or with a default).

Contents: [People and accounts](#people-and-accounts) · [Her day](#her-day) · [Medicines](#medicines) ·
[Delivery and check-ins](#delivery-and-check-ins) · [Memory](#memory-and-stories) ·
[Family view](#family-view-alerts-and-wellbeing) · [Emergency](#emergency) · [Apps and voices](#apps-media-and-voices) ·
[Health data](#health-data-frozen)

## People and accounts

| Table | Purpose | Key columns |
|---|---|---|
| `users` | **The elder** (one row per person Arjun serves) | `name`, `language` (mr/hi/en...), `preferred_languages`, `wake_time`/`breakfast_time`/`lunch_time`/`snack_time`/`dinner_time`, optional `walk_time`, `bp_check_time`, `sugar_check_time`, `sugar_after_time`, `city` (weather), `daily_checkins` (family opt-in), `honorific`, `address_as`, `age`, `conditions`, `interests`, `opener_start/end` (10:00–18:00), `consent_distress_alert`, `speech_style` (rate/volume/simple/companion_name) |
| `contacts` | Family members and doctors | `user_id`, `name`, `relation`, `phone` (synthetic numbers only) |
| `accounts` | Family login | `email` (unique), `password_hash` (Argon2id), `name` |
| `memberships` | Account ↔ elder | `account_id`, `user_id`, `role` (owner/family), unique pair |
| `sessions` | Family browser sessions | `id` (32 random bytes), `account_id`, `expires_at` (12 h sliding, 30 d max) |
| `devices` | Paired elder devices | `user_id`, `token_hash`, `label`, `last_seen`, `revoked` |
| `invites` | One-time links to join an elder | `token_hash`, `user_id`, `expires_at`, `used` |
| `pairing_codes` | One-time codes to pair an elder device | `code_hash`, `user_id`, `expires_at`, `used` |

`address_as` rule: family-set when present; otherwise first name + "बाई", or "आजी" when age is known and ≥ 60.
Arjun never invents "ताई".

## Her day

| Table | Purpose | Key columns / states |
|---|---|---|
| `reminders` | A thing to remember at a time | `task`, `due_at`, `status` `pending → fired → done` (`fired` = the due time passed, **not** that she heard it), `fired_at` |
| `appointments` | One-off or weekly | `title`, `starts_at`, `location`, optional `weekdays` (0=Mon..6=Sun), `start_time`, `end_time` |
| `pending_actions` | The propose → confirm/undo ledger | `action_type` (CREATE_REMINDER, COMPLETE_REMINDER, REQUEST_CAREGIVER, SHARE_STORY, SAVE_STORY, MEDICINE_TAKEN, MEDICINE_SNOOZE), `payload` JSON, `status` |
| `caregiver_requests` | "Ask my son to call me" | `message` (≤ 300) |
| `topic_declines` | "नको" to an opener: no more that day | `day`, `count` |
| `activity` | Last time she spoke or tapped (time only) | `last_seen_at`, `how` voice/tap |

## Medicines

| Table | Purpose | Key columns / states |
|---|---|---|
| `medicines` | **Family-created only.** Name and dose verbatim | `name`, `dose`, `anchor` (fixed/wake/breakfast/lunch/dinner), `time`, `offset_min` (30), `max_reminders` (3), `repeat_minutes` (15), `window_min` (30), `prescribed_by`, `instructions`, `active` |
| `medicine_doses` | One scheduled intake per medicine per day | `status` `due → reminded → taken / unconfirmed / not_taken`, `reminders_sent`, `snooze_count`, `snoozed_until`, `taken_at`; unique (`medicine_id`, `for_date`). **`taken` is self-reported.** |
| `health_profiles` | Family notes: allergies, blood group, doctor, prescription notes, emergency notes | shown back verbatim; **never sent to the LLM**, never used for advice |

## Delivery and check-ins

| Table | Purpose | Key columns / states |
|---|---|---|
| `deliveries` | The queue between "due" and "heard" | `kind` reminder/medicine/checkin, `ref_id`, `attempt`, `status` `queued → speaking → spoken → acknowledged` (also `shown_only`, `undelivered`, `superseded`), `claimed_by`, `spoken_at` (only after playback finished), `acked_at`, `outcome` (taken/not_taken/snoozed/done/ok), `fail_count`, `notified`; unique (`kind`, `ref_id`, `attempt`) |
| `checkins` | Family-enabled meal/walk/BP/interest questions | `kind` (sleep, breakfast, lunch, walk, interest, home, dinner, bp, appt\<ID\>, rem\<ID\>), `for_date`, `due_at`, `status` `pending/asked/done/skipped/missed/unanswered`, `followups` (max one 20-minute), `ref`, `postponed` (max 3 × 10 min), `mood` (""/good/low), `source` asked/volunteered; unique per user/day/kind |
| `daily_briefings` | One Telegram briefing attempt per user per day (content not stored) | `status` pending/sent/failed |

Check-ins are self-reported and never scored, summarised or turned into advice.

## Memory and stories

| Table | Purpose | Notes |
|---|---|---|
| `story_memories` | Her stories | `summary`, `share_status` private (default) / shared. Only shared stories appear in the Memory Book. "he visar" deletes |
| `user_facts` | Long-term memory | `fact` (≤ 160 chars, short wording), `kind` person/like/dislike/routine/place/event/concern/note, `source` auto/explicit, `confidence`, `last_used`. Refuses numbers, addresses, money, medicines, diagnoses. Body-complaint facts are stored only with consent. Deleting a fact never needs consent |

## Family view: alerts and wellbeing

| Table | Purpose | Notes |
|---|---|---|
| `notifications` | Things the family should see | `kind` (reminder, emergency, help, medicine...), `body` ≤ 300 |
| `distress_events` | That distress happened, and whether the caregiver was alerted | **No transcript** |
| `wellbeing` | Per conversation or serious moment | `kind` moment/conversation, `severity` normal/watch/urgent/emergency, `mood` (happy, calm, neutral, lonely, sad, worried, unwell, distressed, not_assessed), `summary` ≤ 400 (a paraphrase), `source` rules/llm. **No transcript**; shown only with consent (emergency/help level excepted) |
| `feed_events` | The live feed | Written automatically for every new notification/wellbeing row; shared ids for WebSocket and polling |
| `sound_events` | Optional sound labels (cough, scream, crying, bang) | label + confidence only; audio never stored; off by default |

## Emergency

| Table | Purpose |
|---|---|
| `emergency_settings` | Family-set: `help_label`, `help_phone`, `address` (read out on the help call), `call_family` |
| `emergency_locations` | `lat`, `lon`, `accuracy_m`; kept only while a physical emergency was recorded in the last 15 min |
| `emergency_calls` | Every escalation attempt: `stage` family/help, `target`, `phone_tail` (last 4 digits), `status` placed/failed/skipped_disabled/skipped_no_number, `detail` |

## Apps, media and voices

| Table | Purpose | Notes |
|---|---|---|
| `app_links` | What the family lets Arjun open | `kind` youtube_query / youtube_video / youtube_playlist / youtube_channel_live / rss / whatsapp / link, `label`, `value` (WhatsApp stores a **contact id**, numbers stay in `contacts`), `spoken_names`, `sort`, `other_host` (family approved a host outside the allowlist) |
| `youtube_search_cache` | 24 h cache of `search.list` results (100 of 10,000 daily quota units each) | |
| `video_calls` | Elder-initiated calls | `contact_id`, `mode`, `status` ringing/…, timestamps |
| `cloned_voices` | A relative's voice, **consent first** | `name`, `relation`, `consent_by`, `consent_text`, `embedding_enc` (Fernet-encrypted with `VOICE_CLONE_KEY`), `active`, `use_count`. The reference clip is never stored |
| `cloned_voice_audit` | add / activate / deactivate / delete / used | kept after the voice is deleted (no foreign key) |

## Health data (frozen)

| Table | Purpose |
|---|---|
| `bp_readings` | Raw systolic/diastolic/pulse. **Never** labelled good/bad/high/low/normal (boundary 7) |
| `watch_samples` | Raw synthetic samples (heart_rate, steps, sleep_minutes). No target or alert derived |

BP/sugar is frozen until after Nov 10: the code exists, is not part of the MVP.

## Relationships at a glance

```
accounts --< memberships >-- users --< contacts
                              users --< reminders, appointments, medicines --< medicine_doses
                              users --< deliveries (ref_id -> reminder | medicine_dose | checkin)
                              users --< story_memories, user_facts, checkins, notifications, wellbeing, feed_events
                              users --< app_links, cloned_voices, video_calls(contact)
                              users -- emergency_settings (1:1), health_profiles (1:1), activity (1:1)
```
