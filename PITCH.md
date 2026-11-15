# Arjun: a voice companion for elders who live away from their families

**Great Indian AI Internship Challenge (Gnani AI)** · Repository: https://github.com/atharva-glitch10/Arjun-

## The problem
Millions of elderly Indians live alone or in old-age homes while their children work in other cities. They miss
medicines, have no one to talk to during the day, and when something goes wrong nobody knows in time. Typing,
small screens and English-only apps do not work for them. Their families want to stay close but are busy.

## The solution
Arjun is a voice companion that speaks **Marathi, Hindi, English and code-mixed speech** (ten languages in total).
The elder just talks: one big button, no menus. Arjun is an AI, says so whenever asked, and is built as
**a bridge to people, not a replacement for them**.

- **A reliable assistant:** reminders and appointments set by voice (read back in one line, "नको" undoes), "आज काय
  आहे?", medicines read exactly as the family entered them, help requests, family video calls, bhajans and news.
- **A warm listener:** conversation, stories, interests, and a Memory Book of stories she chooses to share.
- **For the family:** a dashboard and Telegram briefing showing how she is doing (a level, a mood and a short
  paraphrase, **never a transcript**, shared only with her consent) and honest delivery status.

## Why it is safe
Safety checks run first on every turn, rules only, and work even if the cloud or the AI model is down: a physical
emergency gets a fixed reply and always alerts the family; distress gets a gentle reply and offers a family call
(Elderline 14567). **The language model never touches the database**: it only suggests, and plain code validates and
acts. Medicines are created only by the family, never by voice. No medical advice, no streaks, no guilt, no raw audio
stored, synthetic demo data only.

## How it uses Gnani AI
| Gnani | Role |
|---|---|
| **Prisma** | Arjun's ears: streaming Marathi and code-mixed speech-to-text |
| **Timbre** | Arjun's voice (v3.0, with v2.5 fallback), through LiveKit |
| **Voice cloning** | A relative's voice for friendly chat, with recorded consent (never for safety or medicine) |

Disclosed: open conversation uses a hosted non-Gnani LLM (Sarvam-105B). Evon is not used.
Stack: LiveKit, FastAPI, React + TypeScript, SQLite/Postgres.

## Honest status
Automated tests pass (core-api 367, reasoning 1479, voice-agent 445, scheduler 7, web 266). **Not yet confirmed in a
live voice session:** a complete spoken turn on the current code, emergency auto-calls, and cloned-voice playback.
The Marathi safety word lists await a native-speaker review. We report system results only, not speech-recognition
accuracy.

## Read more
[README](README.md) (run it) · [Architecture](docs/ARCHITECTURE.md) · [Safety and privacy](docs/SAFETY_AND_PRIVACY.md) ·
[All docs](docs/README.md)
