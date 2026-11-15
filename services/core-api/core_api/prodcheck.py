"""ENV=prod startup refusals: exit with the NAMES of missing or unsafe settings (never their values).

Off unless ENV=prod, so local development and the test suites behave exactly as before.
"""
import os
import sys

MIN_KEY_LEN = 32
REQUIRED = (
    "CORE_API_KEY", "DATABASE_URL", "CORS_ALLOW_ORIGINS", "BASE_URL",
    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
)


def is_prod() -> bool:
    return os.environ.get("ENV", "").strip().lower() == "prod"


def problems(env: "os._Environ[str] | dict[str, str]" = os.environ) -> list[str]:  # type: ignore[assignment]
    out = [f"{n} is not set" for n in REQUIRED if not env.get(n, "").strip()]
    if env.get("CORE_API_KEY") and len(env["CORE_API_KEY"]) < MIN_KEY_LEN:
        out.append(f"CORE_API_KEY is shorter than {MIN_KEY_LEN} characters")
    if env.get("ARJUN_TESTING") == "1":
        out.append("ARJUN_TESTING=1 must not be set")
    if env.get("ARJUN_ALLOW_OPEN_SIGNUP", "").strip() == "1":
        out.append("ARJUN_ALLOW_OPEN_SIGNUP=1 must not be set")
    if env.get("ARJUN_AUTH", "").strip() == "1" and not env.get("ARJUN_SIGNUP_CODE", "").strip():
        out.append("ARJUN_SIGNUP_CODE is not set (ARJUN_AUTH=1)")
    if "*" in env.get("CORS_ALLOW_ORIGINS", ""):
        out.append("CORS_ALLOW_ORIGINS must list exact origins, not *")
    return out


def check_prod_env() -> None:
    if not is_prod():
        return
    bad = problems()
    if bad:
        sys.exit("core-api: refusing to start with ENV=prod: " + "; ".join(bad))
