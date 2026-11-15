# Arjun documentation

Start here. Everything about the project, in the order you will probably need it.

| I want to... | Read |
|---|---|
| Understand what Arjun is and run it in 10 minutes | [../README.md](../README.md) |
| Understand how it is built and how one spoken sentence flows | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Find which file does what | [SERVICES.md](SERVICES.md) |
| Look up an endpoint | [API.md](API.md) (and `/docs` on :8000 and :8001) |
| Look up a table | [DATA_MODEL.md](DATA_MODEL.md) |
| Set an environment variable | [CONFIGURATION.md](CONFIGURATION.md) |
| Know what Arjun may and may not do, and what is unverified | [SAFETY_AND_PRIVACY.md](SAFETY_AND_PRIVACY.md) |
| Develop, test and extend it | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Run it, debug it, demo it | [OPERATIONS.md](OPERATIONS.md), [RUNBOOK.md](RUNBOOK.md) |
| Deploy to the cloud (unverified) | [DEPLOY_CLOUD.md](DEPLOY_CLOUD.md) |
| See latency, concurrency, the Prisma audit | [ENGINEERING.md](ENGINEERING.md) |
| See what Gnani features are and aren't wired in | [GNANI_FEATURES.md](GNANI_FEATURES.md) |
| See feature history and the honest limitations list | [DETAILS.md](DETAILS.md) |
| See the dated verification log | [../STATUS.md](../STATUS.md) |
| See the binding spec and hard boundaries | [../CLAUDE.md](../CLAUDE.md) |
| See the contest submission draft | [../SUBMISSION.md](../SUBMISSION.md) |
| See measured results | [../eval/results/RESULTS.md](../eval/results/RESULTS.md), [../eval/REPORT.md](../eval/REPORT.md) |

## Source of truth, and what to trust

1. **CLAUDE.md** is the spec and the hard boundaries. Decisions are dated there. If another document disagrees, it is wrong.
2. **Code and tests** are the truth about behaviour. The docs here were written from the code on 2026-11-15.
3. **STATUS.md** is the dated log of what was verified and how. **eval/results/RESULTS.md** holds the only numbers that may be quoted.
4. `README-OVERVIEW.md` (repo root) is an older overview from 2026-10-18 and is partly stale: prefer these pages.
5. `docs/chat_revamp.md` and `docs/MEDIA_PLAYER_CHECKLIST.md` are short working notes for the chat UI and the media
   player.

## Glossary

| Term | Meaning |
|---|---|
| **Elder / her / Aaji** | The person Arjun serves (`users` row). Demo user: "Aaji", user 1, synthetic |
| **Family / caregiver** | People who use the dashboard, set medicines, receive alerts |
| **Prisma** | Gnani's speech-to-text (ears) |
| **Timbre** | Gnani's text-to-speech (Arjun's male voice; v3.0 supports voice tags) |
| **Sarvam-105B** | The hosted, **non-Gnani** LLM used for open conversation |
| **Evon** | Gnani's LLM; **not used** (decision T9) |
| **LiveKit** | Real-time audio rooms; the worker `arjun` joins each elder session |
| **Care mode** | Fixed-template, SQL-backed replies (reminders, medicines, day, help, safety) |
| **Companion mode** | LLM chat: stories, interests, general questions |
| **Turn** | One thing she said and Arjun's reply |
| **Pending action / undo window** | Action stored by core-api and executed at once; "नको" within 150–180 s undoes it |
| **Delivery** | A due reminder/medicine/check-in queued for an open voice session to speak |
| **Fired vs spoken** | `fired` = due time passed; `spoken` = playback finished (only that means she heard it) |
| **Wellbeing** | Per-conversation level + mood + paraphrase for the family; never a transcript; consent-gated |
| **Seriousness level** | normal / watch / urgent / emergency |
| **Media mode** | While a video plays, only a wake word, bare control or safety phrase is accepted |
| **Opener** | A proactive, interest-based conversation starter (logged only; not spoken) |
| **Ghar** | The elder UI design system (tokens in `web/src/styles/tokens.css`) |
| **T-numbers (T6, T8, T9, T12, T14)** | Task ids from `CLAUDE_CODE_TASKS.md`: T6 elder app through LiveKit+Gnani, T8 delivery of reminders, T9 Evon decision, T12 external distress test, T14 production proxy |
| **UNVERIFIED** | Not reviewed by a native speaker or not run live: treat as unproven |
