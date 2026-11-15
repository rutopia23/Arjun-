import pytest
from core_api import prodcheck

GOOD = {
    "ENV": "prod", "CORE_API_KEY": "k" * 40, "DATABASE_URL": "sqlite:////data/arjun.db",
    "CORS_ALLOW_ORIGINS": "https://arjun.vercel.app", "BASE_URL": "https://arjun.vercel.app",
    "LIVEKIT_URL": "wss://x.livekit.cloud", "LIVEKIT_API_KEY": "a", "LIVEKIT_API_SECRET": "b",
}


def test_good_config_has_no_problems():
    assert prodcheck.problems(GOOD) == []


def test_missing_names_are_reported_without_values():
    bad = {k: v for k, v in GOOD.items() if k != "LIVEKIT_URL"}
    assert prodcheck.problems(bad) == ["LIVEKIT_URL is not set"]


@pytest.mark.parametrize("extra,word", [
    ({"CORE_API_KEY": "short"}, "shorter"),
    ({"CORS_ALLOW_ORIGINS": "*"}, "not *"),
    ({"ARJUN_ALLOW_OPEN_SIGNUP": "1"}, "OPEN_SIGNUP"),
    ({"ARJUN_AUTH": "1"}, "SIGNUP_CODE"),
])
def test_unsafe_settings_refused(extra, word):
    assert any(word in p for p in prodcheck.problems({**GOOD, **extra}))


def test_off_outside_prod(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    prodcheck.check_prod_env()  # no exit


def test_prod_exits_listing_names(monkeypatch):
    for k in GOOD:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ENV", "prod")
    with pytest.raises(SystemExit) as e:
        prodcheck.check_prod_env()
    assert "CORE_API_KEY is not set" in str(e.value)
