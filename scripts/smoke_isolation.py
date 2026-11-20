"""Live multi-user smoke test (docs/DEPLOY_CLOUD.md). Run against the deployed web URL with TWO throwaway accounts.
Usage: python scripts/smoke_isolation.py https://arjun-care-app.vercel.app <signup-code>
Creates synthetic accounts/elders only. Prints PASS/FAIL per check; exits 1 on any FAIL. UNVERIFIED until run once."""
import sys
import uuid

import httpx

base, code = sys.argv[1].rstrip("/"), sys.argv[2]
fails = 0


def check(name: str, ok: bool) -> None:
    global fails
    fails += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + name)


def account(tag: str) -> tuple[httpx.Client, int]:
    c = httpx.Client(base_url=base + "/core", timeout=20, follow_redirects=True)
    email = f"smoke-{tag}-{uuid.uuid4().hex[:6]}@example.com"
    body = {"email": email, "password": "Smoke-" + uuid.uuid4().hex, "signup_code": code, "name": tag}
    r = c.post("/auth/signup", json=body)
    check(f"{tag}: sign-up", r.status_code in (200, 201))
    r = c.post("/parents", json={"name": f"Synthetic {tag}", "interests": []})
    check(f"{tag}: create elder", r.status_code in (200, 201))
    return c, r.json().get("id", 0)


a, ua = account("A")
b, ub = account("B")
check("A sees its own elder", a.get(f"/users/{ua}").status_code == 200)
check("A cannot read B's elder", a.get(f"/users/{ub}").status_code in (401, 403, 404))
check("B cannot read A's elder", b.get(f"/users/{ua}").status_code in (401, 403, 404))
check("A cannot mint B's voice token", a.post("/livekit/token", json={"user_id": ub}).status_code in (401, 403, 404))
anon = httpx.Client(base_url=base + "/core", timeout=20)
check("no login -> 401/403", anon.get(f"/users/{ua}").status_code in (401, 403))
sys.exit(1 if fails else 0)
