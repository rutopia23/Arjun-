# Cloud deployment: Vercel (web) + Railway (4 services)

**Status: UNVERIFIED.** Nothing here has been deployed or built in a container yet. Run the smoke tests at the end
and fix what fails. Names only below; set the values in the dashboards. Never commit values.

## How it fits
Browser -> Vercel (static page + `api/core.ts`, `api/entry.ts`) -> core-api on Railway. The Vercel functions are the
production version of the Vite dev proxy: they run the same access gate (`web/server/access.ts`), and only after a
valid link cookie do they add `CORE_API_KEY`. The key lives in Vercel's environment, not in the bundle. The page
calls same-origin `/core/*`, so no `VITE_*` API variable is needed, and the LiveKit URL comes from
`POST /livekit/token` (core-api `LIVEKIT_URL`). LiveKit Cloud holds the rooms; the Railway worker joins them.

## 1. LiveKit Cloud
Create a project; note the `wss://` URL, API key and secret (used by core-api and voice-agent).

## 2. Railway (one project, four services, same repo)
Create each service from the GitHub repo, then set (Settings):

| Service | Root Directory | Config-as-code path | Public domain |
|---|---|---|---|
| core-api | `services/core-api` | `/deploy/railway/core-api.railway.json` | yes (Vercel calls it) |
| reasoning | `/` (repo root) | `/deploy/railway/reasoning.railway.json` | no |
| scheduler | `services/scheduler` | `/deploy/railway/scheduler.railway.json` | no |
| voice-agent | `services/voice-agent` | `/deploy/railway/voice-agent.railway.json` | no |

core-api: add a **Volume** mounted at `/data` and keep it at **one replica** (SQLite). Healthchecks: core-api and
reasoning use `/health`; scheduler and voice-agent are workers with none. Internal calls use Railway private
networking, e.g. `http://core-api.railway.internal:8000` (use the port core-api listens on).

### Variable NAMES per service
- **core-api:** `ENV=prod`, `CORE_API_KEY` (32+ random chars), `DATABASE_URL` (`sqlite:////data/arjun.db`),
  `CORS_ALLOW_ORIGINS` (the exact Vercel origin, no `*`), `BASE_URL` (the Vercel URL), `LIVEKIT_URL`,
  `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `GNANI_API_KEY`, `VOICE_CLONE_KEY`, `ARJUN_AUTH`, `ARJUN_SIGNUP_CODE`,
  `ARJUN_TZ`, `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `CALLS_ENABLED=0`.
- **reasoning:** `ENV=prod`, `CORE_API_URL`, `CORE_API_KEY`, `SARVAM_API_KEY`, `SARVAM_MODEL`, `LLM_REASONING`,
  `LLM_TIMEOUT_S`, `LLM_MAX_TOKENS`, `TAVILY_API_KEY` (optional).
- **scheduler:** `ENV=prod`, `CORE_API_URL`, `CORE_API_KEY`, `REASONING_URL`, `OPENER_USER_IDS`.
- **voice-agent:** `ENV=prod`, `GNANI_API_KEY`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
  `CORE_API_URL`, `CORE_API_KEY`, `REASONING_URL`, `GNANI_STT_TRANSPORT`, `ARJUN_USER_ID`.

With `ENV=prod`, core-api, reasoning, scheduler and voice-agent exit at start naming any missing variable (never
its value). core-api also refuses a key under 32 characters, `*` in CORS, `ARJUN_ALLOW_OPEN_SIGNUP=1`,
`ARJUN_TESTING=1`, and `ARJUN_AUTH=1` without `ARJUN_SIGNUP_CODE`.

## 3. Vercel
Import the repo, **Root Directory = `web`**, framework Vite (`web/vercel.json` sets the build and rewrites).
Environment variables (server-side, NOT `VITE_*`): `CORE_API_URL` (core-api public Railway URL), `CORE_API_KEY`
(same as Railway), `ARJUN_ACCESS_CODE` (6+ characters; without it every remote request is refused).
The build skips `npm run build`'s Python pre-step; run `python scripts/check_no_browser_speech.py` before pushing.

Phone links: `https://<vercel-url>/?user=1&k=<ARJUN_ACCESS_CODE>` (elder) and
`https://<vercel-url>/?view=family&user=1&k=<ARJUN_ACCESS_CODE>` (family).

## 4. Smoke tests (replace the hosts)
```
curl -s https://<core-api>.up.railway.app/health
curl -s -o /dev/null -w "%{http_code}\n" https://<core-api>.up.railway.app/users/1          # expect 401/403 (no key)
curl -s -o /dev/null -w "%{http_code}\n" https://<vercel>/core/users/1/day                   # expect 401 (no cookie)
curl -s -i "https://<vercel>/?user=1&k=<code>" | grep -i "set-cookie\|location"              # cookie set, k removed
curl -s -c j -o /dev/null "https://<vercel>/?user=1&k=<code>"; curl -s -b j https://<vercel>/core/users/1/day   # 200
curl -s -H "Origin: https://evil.example" -i https://<core-api>.up.railway.app/health | grep -i access-control  # none
```
Then open the elder link on a phone, tap the button, and speak once. Check the voice-agent logs for `voice:` lines.

## Known gaps (do not claim these work until seen)
- **Not built or run:** the Railway configs, `services/voice-agent/Dockerfile`, and the Vercel functions.
- **No WebSocket on Vercel:** the family live feed falls back to REST polling.
- **Vercel body limit (4.5 MB):** a long voice-clone reference clip may be refused.
- **Daily Telegram voice briefing:** the voice-agent serves it on loopback `127.0.0.1:8002`, so core-api on another
  service cannot reach it; the briefing's audio part will not work in this layout.
- **Access gate rate-limit** is per function instance, and the shell page itself is public (only the API is gated).
- **SQLite on a volume** = one core-api replica, no zero-downtime deploys. Move to Postgres later.
- **Cold-start latency and cost per call** on Railway are unmeasured. Prisma and Timbre are called from the worker.


## Multi-user mode (each family has its own login and its own elder link)

Set on core-api: `ARJUN_AUTH=1`, `ARJUN_SIGNUP_CODE=<secret to give testers>` (never `ARJUN_ALLOW_OPEN_SIGNUP` in prod),
`ARJUN_DAILY_VOICE_SESSIONS=20` (cost cap), `BASE_URL=<your Vercel URL>`, `CORS_ALLOW_ORIGINS=<your Vercel URL>`.
Set on Vercel: `ARJUN_AUTH=1`, `CORE_API_URL`. `CORE_API_KEY` is then only for the voice agent and scheduler, not the browser path.
Set on voice-agent: `ENV=prod` (rooms without a user id are refused).

Flow: family opens the site -> sign up (code) -> add elder -> "Create elder link" -> opens it on her phone -> her Arjun.

Smoke test (must pass before real users): (1) two accounts A and B; (2) A's elder phone cannot read B's elder
(`GET /core/users/<B's id>/day` -> 403/404); (3) a browser with no login gets 401 on `/core/users/1/day`; (4) a
revoked phone stops working; (5) the third voice session over the cap answers 429.
Real elders' data: get consent first; CLAUDE.md says demo data is synthetic only.
