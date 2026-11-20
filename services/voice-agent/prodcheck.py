"""ENV=prod startup refusals for the voice worker: NAMES only, never values. Off unless ENV=prod."""
import os
import sys

REQUIRED = ("CORE_API_URL", "CORE_API_KEY", "REASONING_URL", "ARJUN_INTERNAL_KEY")


def check_prod_env() -> None:
    if os.environ.get("ENV", "").strip().lower() != "prod":
        return
    bad = [f"{n} is not set" for n in REQUIRED if not os.environ.get(n, "").strip()]
    if bad:
        sys.exit("voice-agent: refusing to start with ENV=prod: " + "; ".join(bad))
