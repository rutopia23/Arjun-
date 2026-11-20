from fastapi.testclient import TestClient
from reasoning_svc.main import app


def test_http_routes_need_the_internal_key_when_it_is_set(monkeypatch):
    monkeypatch.setenv("ARJUN_INTERNAL_KEY", "k" * 24)
    c = TestClient(app)
    assert c.get("/health").status_code == 200  # the platform healthcheck carries no key
    assert c.post("/turn", json={"user_id": 1, "text": "hi"}).status_code == 403
    assert c.post("/turn", json={"user_id": 1, "text": "hi"}, headers={"x-arjun-internal": "wrong"}).status_code == 403
    assert c.post("/turn", json={"user_id": 1, "text": "hi"}, headers={"x-arjun-internal": "k" * 24}).status_code != 403


def test_open_when_the_key_is_unset(monkeypatch):
    monkeypatch.delenv("ARJUN_INTERNAL_KEY", raising=False)
    assert TestClient(app).post("/turn", json={"user_id": 1, "text": "hi"}).status_code != 403
