"""Conversation-context eval (2026-11-10): 45 short multi-turn dialogues (eval/context/golden.jsonl) through the REAL turn engine with the
live hosted LLM (.env LLM_*). Only the LAST reply of each dialogue is judged (the earlier replies are generated live, so the context is
real). Scores: answered-the-question (LLM judge 1-5), stayed on topic, used the earlier turn correctly, invented facts (must be 0) and
generic fallbacks (must be 0, counted over EVERY turn by rule). Also text-ready latency per turn (engine only: no STT endpointing, no TTS).
The judge is the same hosted model as the companion (not independent): read the numbers as a before/after on the same ruler.
No key is printed.

    python scripts/eval_context.py run   <label> [--limit N] [--cases path]     writes eval/results/context_<label>.json
    python scripts/eval_context.py compare <before-label> <after-label>        prints the table + 8 sample dialogues of the second

`ARJUN_CODE=<checkout>` runs the same cases against another checkout (a git worktree of the commit "before").
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = Path(os.environ.get("ARJUN_CODE", ROOT))
RESULTS = ROOT / "eval" / "results"
sys.stdout.reconfigure(encoding="utf-8")

# independent of the code under test: filler lines that answer nothing
GENERIC = re.compile(
    r"^\s*(?:ठीक आहे|बरं|बरं का|हो का|अच्छा|सांगा ना|सांगा|मी ऐकतोय|मी ऐकत आहे|ऐकतोय|ठीक है|बताइए|मैं सुन रहा हूँ|मैं सुन रहा हूं|"
    r"okay|ok|i'?m listening|go on|tell me more|i see|alright|sure|चला सांगा|बोला|हं|हम्म)[\s.!?।…]*$", re.IGNORECASE,
)
JUDGE_SYSTEM = (
    "You grade ONE spoken reply of a voice companion (Arjun) for an elderly Indian speaker. Her words come from speech-to-text and may be "
    "noisy. You get the dialogue and the CRITERION for the LAST reply. Return ONLY a JSON object: "
    '{"answered": 1-5, "on_topic": true|false, "used_prior_turn": true|false, "invented": true|false, "why": "<=15 words"}. '
    "answered: 5 = directly and naturally answers / responds to her LAST sentence as the criterion asks; 3 = partly; 1 = ignores it, wanders, "
    "or is a generic filler. on_topic: false if the reply starts a new topic, gives a list of tips or asks an unrelated question. "
    "used_prior_turn: true if the reply correctly uses something from the EARLIER turns (a person, thing, question) where the criterion needs "
    "it, or if no earlier context was needed. invented: true if the reply states a person, event, fact or memory that is NOT in the dialogue "
    "(ordinary warm words and general knowledge are not invented)."
)


def _setup():
    from dotenv import dotenv_values

    for k, v in dotenv_values(ROOT / ".env").items():
        if v is not None:
            os.environ.setdefault(k, v)
    os.environ.update(DATABASE_URL="sqlite:///:memory:", ARJUN_TESTING="1", ARJUN_ASK_BEFORE_ACTING="0")
    for k in ("CORE_API_KEY", "TELEGRAM_ENABLED"):
        os.environ.pop(k, None)
    sys.path[:0] = [str(CODE / "services" / "core-api"), str(CODE / "services" / "reasoning")]


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else 0.0


def judge(llm, case: dict, dialogue: list[tuple[str, str]]) -> dict:
    lines = "\n".join(f"{'ARJUN' if who == 'a' else 'SHE'}: {t}" for who, t in dialogue)
    user = f"DIALOGUE:\n{lines}\n\nCRITERION for the last ARJUN reply: {case['criterion']}"
    for _ in range(2):
        try:
            raw = llm._chat([{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}], 0.0, purpose="judge", max_tokens=300)
            m = re.search(r"\{.*\}", raw, re.S)
            d = json.loads(m.group(0)) if m else None
            if isinstance(d, dict) and "answered" in d:
                return {"answered": int(d["answered"]), "on_topic": bool(d.get("on_topic")), "used_prior_turn": bool(d.get("used_prior_turn")),
                        "invented": bool(d.get("invented")), "why": str(d.get("why", ""))[:120]}
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return {"answered": 0, "on_topic": False, "used_prior_turn": False, "invented": False, "why": "judge failed"}


def run(label: str, cases_path: Path, limit: int | None) -> int:
    _setup()
    import httpx
    from core_api.db import Base, get_db, make_engine
    from core_api.main import app, get_now
    from fastapi.testclient import TestClient
    from reasoning_svc import config
    from reasoning_svc import turn as turn_mod
    from reasoning_svc.core_client import CoreClient
    from reasoning_svc.evon import EvonClient, load_intent_schema
    from reasoning_svc.turn import _VARIED, TurnEngine
    from sqlalchemy.orm import sessionmaker

    turn_mod._UNDERSTAND_TIMEOUT_S = 40.0
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _db():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_now] = lambda: datetime.now()
    cases = [json.loads(x) for x in cases_path.read_text(encoding="utf-8").splitlines() if x.strip()][:limit]
    s = config.llm_settings()
    varied = {line for pool in _VARIED.values() for line in pool}
    print(f"[{label}] LLM {s.provider}/{s.model} | code: {CODE} | temp {config.COMPANION_TEMPERATURE} | "
          f"context_state={getattr(config, 'CONTEXT_STATE', 'n/a')} guard={getattr(config, 'RELEVANCE_GUARD', 'n/a')} | {len(cases)} cases", flush=True)
    rows: list[dict] = []
    with TestClient(app) as http:
        for case in cases:
            uid = http.post("/users", json={"name": "Aaji (synthetic)", "language": case["lang"]}).json()["id"]
            llm = EvonClient(s.base_url, s.model, schema=load_intent_schema(), api_key=s.api_key, provider=s.provider,
                             send_template_kwargs=s.send_template_kwargs, max_tokens=s.max_tokens, timeout_s=s.timeout_s, reasoning_off=s.reasoning_off)
            llm.http.timeout = httpx.Timeout(45.0)
            eng = TurnEngine(CoreClient(http), llm, llm_timeout_s=60.0, ask_first=False)
            dialogue: list[tuple[str, str]] = []
            if case.get("arjun_first"):
                eng.memory.arjun_said(uid, eng.clock(), case["arjun_first"], "checkin")
                dialogue.append(("a", case["arjun_first"]))
            ms: list[float] = []
            generic = 0
            for t in case["turns"]:
                time.sleep(2.0)  # the provider is limited to ~60 calls a minute
                t0 = time.perf_counter()
                res = eng.handle(uid, t)
                ms.append((time.perf_counter() - t0) * 1000)
                dialogue += [("s", t), ("a", res.reply)]
                generic += bool(GENERIC.match(res.reply or "")) or (res.reply in varied)
            time.sleep(2.0)
            j = judge(llm, case, dialogue)
            reply = dialogue[-1][1]
            kw = case.get("keywords_any") or []
            rows.append({"id": case["id"], "cat": case["cat"], "lang": case["lang"], "dialogue": dialogue, "criterion": case["criterion"], "judge": j,
                         "keyword_hit": (any(k.lower() in reply.lower() for k in kw) if kw else None), "generic_turns": generic,
                         "turn_ms": [round(x) for x in ms], "last_ms": round(ms[-1]),
                         "relevance": dict(getattr(eng, "relevance", {}) or {})})
            mark = "OK " if j["answered"] >= 4 and j["on_topic"] and not j["invented"] and not generic else "BAD"
            print(f"{mark} {case['id']} {case['cat']:14} ans={j['answered']} topic={int(j['on_topic'])} prior={int(j['used_prior_turn'])} inv={int(j['invented'])} gen={generic} "
                  f"{rows[-1]['last_ms']:5} ms | {dialogue[-2][1][:28]} -> {reply[:60]}", flush=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"context_{label}.json").write_text(json.dumps({"label": label, "when": datetime.now().isoformat(timespec="seconds"), "llm": f"{s.provider}/{s.model}",
                                                              "temperature": config.COMPANION_TEMPERATURE, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(summary(rows))
    return 0


def summary(rows: list[dict]) -> str:
    n = len(rows)
    all_ms = [m for r in rows for m in r["turn_ms"]]
    return (
        f"cases {n} | judge avg {statistics.mean(r['judge']['answered'] for r in rows):.2f} | answered>=4 {sum(r['judge']['answered'] >= 4 for r in rows)}/{n} | "
        f"stayed on topic {sum(r['judge']['on_topic'] for r in rows)}/{n} = {sum(r['judge']['on_topic'] for r in rows) / n:.0%} | "
        f"used prior turn {sum(r['judge']['used_prior_turn'] for r in rows)}/{n} | invented {sum(r['judge']['invented'] for r in rows)} | "
        f"generic fallback turns {sum(r['generic_turns'] for r in rows)} | text-ready ms p50 {_pct(all_ms, 50):.0f} p95 {_pct(all_ms, 95):.0f} ({len(all_ms)} turns)"
    )


def compare(a: str, b: str) -> int:
    A = json.loads((RESULTS / f"context_{a}.json").read_text(encoding="utf-8"))
    B = json.loads((RESULTS / f"context_{b}.json").read_text(encoding="utf-8"))

    def stats(d):
        rows = d["rows"]
        n = len(rows)
        ms = [m for r in rows for m in r["turn_ms"]]
        return {
            "cases": n, "judge avg (1-5)": round(statistics.mean(r["judge"]["answered"] for r in rows), 2),
            "answered >= 4": f"{sum(r['judge']['answered'] >= 4 for r in rows)}/{n}",
            "stayed on topic": f"{sum(r['judge']['on_topic'] for r in rows) / n:.0%}",
            "used prior turn": f"{sum(r['judge']['used_prior_turn'] for r in rows) / n:.0%}",
            "invented facts": sum(r["judge"]["invented"] for r in rows),
            "generic fallback turns": sum(r["generic_turns"] for r in rows),
            "text-ready p50 ms": round(_pct(ms, 50)), "text-ready p95 ms": round(_pct(ms, 95)),
        }

    sa, sb = stats(A), stats(B)
    print(f"| metric | before ({a}) | after ({b}) |\n|---|---|---|")
    for k in sa:
        print(f"| {k} | {sa[k]} | {sb[k]} |")
    cats = sorted({r["cat"] for r in B["rows"]})
    print("\n| category | n | on topic before | on topic after | judge before | judge after |\n|---|---|---|---|---|---|")
    for c in cats:
        ra = [r for r in A["rows"] if r["cat"] == c]
        rb = [r for r in B["rows"] if r["cat"] == c]
        f = lambda rs, k: (f"{sum(r['judge']['on_topic'] for r in rs)}/{len(rs)}" if k == "t" else f"{statistics.mean(r['judge']['answered'] for r in rs):.1f}") if rs else "-"  # noqa: E731
        print(f"| {c} | {len(rb)} | {f(ra, 't')} | {f(rb, 't')} | {f(ra, 'j')} | {f(rb, 'j')} |")
    print("\n8 sample dialogues (after):")
    seen: set[str] = set()
    picks = []
    for r in B["rows"]:
        if r["cat"] not in seen and len(picks) < 8:
            seen.add(r["cat"])
            picks.append(r)
    for r in B["rows"]:
        if len(picks) < 8 and r not in picks:
            picks.append(r)
    for r in picks[:8]:
        print(f"\n[{r['id']} {r['cat']}] judge {r['judge']['answered']}/5 - {r['judge']['why']}")
        for who, t in r["dialogue"]:
            print(f"  {'Arjun' if who == 'a' else 'She  '}: {t}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["run"] and len(args) >= 2:
        lim = int(args[args.index("--limit") + 1]) if "--limit" in args else None
        path = Path(args[args.index("--cases") + 1]) if "--cases" in args else ROOT / "eval" / "context" / "golden.jsonl"
        raise SystemExit(run(args[1], path, lim))
    if args[:1] == ["compare"] and len(args) == 3:
        raise SystemExit(compare(args[1], args[2]))
    print(__doc__)
    raise SystemExit(2)
