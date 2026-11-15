"""ENV=prod startup refusals: exit with the NAMES of missing settings (never values). Off unless ENV=prod."""
import os
import sys


def check_prod_env() -> None:
    if os.environ.get("ENV", "").strip().lower() != "prod":
        return
    bad = [f"{n} is not set" for n in ("CORE_API_URL", "CORE_API_KEY") if not os.environ.get(n, "").strip()]
    if len(os.environ.get("CORE_API_KEY", "")) < 32 and os.environ.get("CORE_API_KEY"):
        bad.append("CORE_API_KEY is shorter than 32 characters")
    if bad:
        sys.exit("reasoning: refusing to start with ENV=prod: " + "; ".join(bad))
