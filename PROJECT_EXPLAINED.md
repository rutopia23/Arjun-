# Arjun: the project on one page

**What it is.** A voice companion for elderly Indians who speak Marathi, Hindi, English or a mix. She talks; Arjun
listens, answers by voice, keeps her day on track, and keeps her family informed. It is an AI, says so when asked,
and is meant to connect her to people, not replace them.

**Two halves.** A *reliable assistant* (reminders, appointments, "what is today?", medicines, help requests, family
video calls, bhajans and news) and a *warm listener* (chat, stories, interests, a Memory Book of stories she chooses
to share).

**How a sentence travels.**
`Elder's browser (one big button) → LiveKit room → voice-agent → Gnani Prisma (speech-to-text) → reasoning → core-api (database) → reply → Gnani Timbre (text-to-speech) → speaker`.

| Part | Does |
|---|---|
| **web** (React, TypeScript) | The elder screen and the family dashboard |
| **voice-agent** (LiveKit worker "arjun") | Ears and mouth: Prisma in, Timbre out, turn-taking, media mode |
| **reasoning** (FastAPI) | The brain: safety rules first, then understanding, then the action |
| **core-api** (FastAPI, SQLite/Postgres) | The only place data is stored; validates and executes every action |
| **scheduler** | A 30-second clock that triggers due reminders, medicines, summaries and briefings |

**The key design rule.** Rules and fixed templates handle everything that touches health, time or safety. A hosted
language model (Sarvam-105B, not Gnani, disclosed) is used only to understand messy speech and to chat. It *suggests*;
core-api *validates and acts*. The model never touches the database. If the model or the network is down, the rules
still answer.

**What happens when she asks for something.** "Tomorrow at 10, doctor" is saved at once and read back in one line;
"नको" undoes it. If a detail is missing (which day, AM or PM) Arjun asks and never guesses. A reminder counts as
*spoken* only after the audio really played.

**Safety, on every turn, rules only.** A physical emergency gets a fixed reply and always alerts the family
(dashboard, Telegram, and optional phone calls to numbers the family saved; Arjun never dials 112). Distress gets a
gentle reply, a family-call offer and Elderline 14567, and alerts the family only with consent. Medicines are created
only by the family, read exactly as entered, and Arjun gives no medical advice.

**For the family.** Reminders, medicines, apps and links, emergency settings, a live feed with a level (normal, watch,
urgent, emergency), a mood word and a short paraphrase, **never a transcript**, shown only with her consent.

**Privacy.** No raw audio is stored, stories are private by default, a relative's cloned voice needs recorded consent
and is used only for friendly chat, and all demo data is synthetic.

**Gnani AI used.** Prisma (ears), Timbre (voice), and voice cloning, all through LiveKit.

**Status, honestly.** About 2,500 automated tests plus lint, type-check and build pass. Not yet confirmed in a live
voice session: a full spoken turn on the current code, emergency phone calls, and cloned-voice playback. The Marathi
safety word lists await a native-speaker review. We report system results only, not speech accuracy.

**Run it.** Fill `.env` (Gnani, LiveKit, optional Sarvam keys), then `scripts\dev-up.ps1`; open
`http://localhost:5173/?user=1`. Details: [README](README.md) · all docs: [docs/README.md](docs/README.md) ·
pitch: [PITCH.md](PITCH.md).
