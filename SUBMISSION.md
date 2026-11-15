# Arjun: submission text (Great Indian AI Internship Challenge, Gnani AI)

> Draft. Fill the [brackets] (names, links only), and keep the "Verification status" section below honest.

## Project title
Arjun: a voice companion for elders who live away from their families

## The problem
Millions of elderly Indians live alone or in old-age homes while their children work in other cities. They miss
medicines, have no one to talk to during the day, and when something goes wrong nobody knows in time. Their
children want to stay close but are busy, and calls often end with "aur, sab theek?".

## Who uses it
- **Elders** (Marathi first; Hindi, Tamil, English and code-mixed speech): one big button, everything by voice.
- **Their family**: a dashboard plus Telegram briefings, to know how she is and what to talk about on the next call.

## What it does
**For the elder (by voice):** daily conversation and stories; "आज काय आहे?" (today's plan from SQL); reminders set by
voice with one-line read-back and "नको" to undo; medicine reminders read exactly as the family entered them; play
bhajans/songs on YouTube; start a video call to family by voice; hearing-friendly (slower, repeat, louder); a familiar
voice: with the family member's recorded consent, Arjun can chat in their cloned voice (never for safety or medicine).

**Safety first, every turn, rules only:** physical emergency words -> fixed reply (call 112, call out to someone near)
and an emergency banner on the family dashboard; emotional distress -> gentle reply, offer a family call, Elderline
14567, family alert only with consent. Never medical advice.

**For the family:** "Before you call" talking points, mood and a short paraphrased summary (never a transcript, only
with consent), medicines and alerts, Memory Book of stories she chose to share, daily Telegram voice briefing.

## Gnani AI models and APIs used (and exactly where)
| Gnani | Used for | Code |
|---|---|---|
| **Prisma** (speech-to-text, streaming) | Arjun's ears: live Marathi / code-mixed speech; optional Prisma v3 with automatic language detection, code-mix output, key terms (medicine, contact, app names), speaker names, 8 kHz | `services/voice-agent/agent.py`, `voice.py`, `prisma_v3.py` |
| **Timbre** (text-to-speech) | Arjun's voice: v3.0 with v2.5 fallback, reply language follows the speaker | `services/voice-agent/agent.py`, `voice.py` |
| **Voice cloning** (Voice Clone Embeddings + Voice Cloned TTS `vachana-vc-v1`) | A family member's voice for friendly chat, consent-first, encrypted, deletable | `services/core-api/core_api/voices.py`, `services/voice-agent/clonedvoice.py`, `web/src/family/VoicesCard.tsx` |

**Not Gnani, disclosed:** open conversation and family summaries use a hosted LLM (Sarvam-105B, hosted by Sarvam AI). Safety, medicines, reminders and times never depend on it. **Not used:** Evon (needs a GPU; not
on the API platform), Warp (no public API).

## Privacy and consent
Synthetic demo data only. No raw audio stored; voice-clone reference clips are never stored (only an encrypted
embedding), consent is recorded and the voice can be deleted anytime; the elder screen always shows whose voice is
speaking. Family sees summaries, never her words, and mood only with "share how she is doing".

## Verification status (state this plainly; do not overclaim)
- **Automated tests pass** (2026-11-15): core-api 367, reasoning 1479, voice-agent 445, scheduler 7, web 266, TypeScript and Ruff clean.
- **Not yet confirmed on a live phone/voice session:** streaming-TTS latency changes, apps by voice, media-mode recovery,
  emergency auto-calls (need Twilio; off by default), cloned-voice playback. Show only what was recorded working.
- **Unreviewed by a native speaker:** the Marathi emergency/distress word lists and the bn/gu/kn/ml/pa/ta/te strings.
- **Reported numbers are system results only**; no Prisma WER is published (Gnani EULA clause 16).
- Arjun is an AI and says so; it gives no medical advice beyond one fixed self-care line and "ask your doctor".

## Team and contributions
- [Rutuja Patole]: [product idea and UX, family dashboard and voice-cloning flow, demo film, LinkedIn/X campaign, testing]
- [Teammate]: [voice pipeline, reasoning, core-api, safety rules, deployment]

## 60-second demo script (shot list)
1. 0-5 s: Aaji alone, phone face down. Caption: "Who listens when family can't pick up?"
2. 5-20 s: she taps बोला, talks in Marathi about her first tomato; Arjun (Timbre) answers warmly in Marathi.
3. 20-28 s: "आज काय आहे?" -> today's reminders read back; medicine screen -> घेतली.
4. 28-38 s: Hinglish/Tamil line -> reply in the same language (Prisma language detection).
5. 38-48 s: family dashboard: "Before you call" card, then add a familiar voice with consent; next chat reply in that voice.
6. 48-56 s: emergency phrase -> fixed safety reply + red banner on the family dashboard.
7. 56-60 s: end card: "Built on Gnani AI: Prisma · Timbre · Voice cloning".

## Links
- Demo video: [link]
- LinkedIn post: [link] · X post: [link]
- Repository: https://github.com/atharva-glitch10/Arjun-
