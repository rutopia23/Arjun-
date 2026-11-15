# ENGINEERING.md - how a spoken turn flows, and why it stays on topic

Written 2026-11-10 with the streaming + conversation-context work. STATUS.md says what is verified; CLAUDE.md holds the hard boundaries
(none of them changed here: the safety rules still run first, the LLM never touches the database, medicine text is never LLM-written).

## 1. Transport: HTTP `/turn` and WebSocket `/turn/stream`

```
voice-agent (Prisma final transcript)
   |  ARJUN_STREAM=1 ?  yes -> streamclient.StreamClient  --ws-->  reasoning /turn/stream
   |                    no  -> bridge.reply_or_fallback   --http-> reasoning /turn      (unchanged, always works)
   v
reasoning TurnEngine.handle()   safety rules -> ONE understanding call -> rules / tools -> companion reply -> guards
```

* **Frames** (`reasoning_svc/stream.py` docstring): `ack` (rules only, carries the web-lookup filler) -> `sentence`* -> `final` (all `/turn`
  fields) -> `action`. `cancel {turn_id}` drops a turn that has not been spoken. Errors are frames (`error` with a status), never a dead socket.
* **Ordering**: one asyncio lock per user, FIFO, so two turns of one person never overlap; different people do not wait for each other.
* **Safety**: the engine's own first step. A sentence that is an emergency / distress is never rate limited and never gets a filler.
* **Auth**: optional shared key `ARJUN_INTERNAL_KEY` (header `x-arjun-internal`, constant-time compare, never logged). Unset = open, like `/turn`
  (an internal port).
* **Client fallback rules** (`streamclient.ask_with_fallback`):
  * never reached the engine (socket down, refused, no `ack` in 2 s, 422/429) -> **HTTP `/turn`**;
  * the socket died **after** the `ack` -> the **fixed fallback line**, *not* an HTTP replay (the engine may already have set a reminder);
  * reconnect back-off 1 s -> 30 s; while backing off the client does not even try, HTTP answers.
* **Honest limit**: sentences are cut from the *finished, guarded* reply. The language, medical-advice and relevance guards need the whole text, so
  no unguarded LLM token is ever spoken. The LLM call itself is not sped up; per-sentence pipelined TTS is not wired.

## 2. Conversation state (`convstate.py`)

Rules only, in memory only, per user. Holds `current_topic` (+ previous), people / places / times mentioned, a *flag* that a medicine was
mentioned (never its name: boundary 6), and the last 6 exchanges. The pending question stays in `SessionMemory` (single owner) and reaches
the prompt as the `OPEN QUESTION` line. At prompt time `references()` resolves what her NEW sentence points back to: a pronoun ("त्याला") ->
the last person named; "हो / तेच / आणखी" -> a short answer to the last question. "Forget this" scrubs the state too.

`fit_prompt` builds the variable part of the prompt in a fixed order under `ARJUN_PROMPT_TOKEN_CAP` (estimated tokens). Dropped first-to-last:
facts (last first) -> older exchanges (down to the last 2) -> state lines. Never dropped: the open question, the last 2 exchanges.
`ARJUN_CONTEXT_STATE=0` restores the previous assembly (all history, facts appended whole).

## 3. Staying on topic

1. **Prompt** (`evon._conversation_rules`): answer only what she just said or asked, reuse her words and named people, no new topic, no tip
   lists, ambiguous -> one short question quoting her words, subject change -> follow her, at most 2 short spoken sentences. The understanding
   JSON also returns `topic` and `relevance_self_check`. Temperature 0.4.
2. **Relevance guard** (`turn._relevance_guard`, `relevance.py`), on every LLM chat reply, before it is spoken:
   generic filler -> off; word overlap with her sentence / topic / people / open question >= 0.2 -> on; otherwise a tiny LLM yes/no
   (`relevance_check`; "cannot tell" never blocks) -> off: ONE retry (`companion_reply(focus=her sentence)`) -> still off: a one-question line
   that quotes her own words. Logged: `relevance_score`, `retried`, `clarified` (no words). `ARJUN_RELEVANCE_GUARD=0` disables it.
3. Rules / tool / safety / medicine replies are fixed templates and bypass the guard.

## 4. Measuring it

`python scripts/eval_context.py run <label>` (45 dialogues in `eval/context/golden.jsonl`, live LLM) then `compare <before> <after>`.
`ARJUN_CODE=<other checkout>` runs the same cases on an older commit. The judge is the same hosted model as the companion, so the numbers are
a before/after on one ruler, not an independent grade. Latency there is *text ready* (engine only); STT endpointing and TTS are not in it.
The older reasoning suites run with the guard off (conftest) because they count LLM calls exactly.
