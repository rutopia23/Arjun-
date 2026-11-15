"""C: the ONE certifi TLS context is used by the TTS session too (never the Windows cert store on the event loop).
D: a failed timbre-v3.0 probe is retried once after 5 s, then the session falls back to the verified voice."""

import asyncio

import pytest

ENV = ("GNANI_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


@pytest.fixture
def voice_agent(monkeypatch):
    for name in ENV:
        monkeypatch.setenv(name, "test")
    import agent

    return agent


class ProbeTTS:
    """Fails its first `failures` one-word probes, then succeeds. Counts every synthesize() call."""

    def __init__(self, failures):
        self.failures, self.calls = failures, 0

    def synthesize(self, _text):
        self.calls += 1
        fail = self.calls <= self.failures

        class Stream:
            async def collect(_self):
                if fail:
                    raise TimeoutError("probe timed out")
                return ["audio"]

        return Stream()


def test_the_tts_session_uses_the_one_certifi_tls_context(monkeypatch, voice_agent):
    import prisma_v3

    class FakeTTS:
        def __init__(self, **_kw):
            self._session = None

    monkeypatch.setitem(voice_agent.TTS, "method", "sse")
    monkeypatch.setattr(voice_agent, "SseTimbre", FakeTTS)

    async def main():
        voice_agent.make_tts("model", "voice", "hi-IN")
        try:
            session = voice_agent._TTS_SESSIONS[asyncio.get_running_loop()]
            assert session.connector._ssl is prisma_v3.tls_context()
        finally:
            await voice_agent.close_tts_session()

    asyncio.run(main())


def test_the_retry_waits_five_seconds(voice_agent):
    assert voice_agent.TTS_PROBE_RETRY_S == 5.0


def test_a_timed_out_probe_is_retried_once_and_then_works(monkeypatch, voice_agent):
    monkeypatch.setattr(voice_agent, "TTS_PROBE_RETRY_S", 0)  # no real 5 s wait in the test
    tts = ProbeTTS(failures=1)
    assert asyncio.run(voice_agent._probe_tts_with_retry(tts, "timbre-v3.0")) is True
    assert tts.calls == 2


def test_a_probe_that_fails_twice_falls_back_after_exactly_one_retry(monkeypatch, voice_agent):
    monkeypatch.setattr(voice_agent, "TTS_PROBE_RETRY_S", 0)
    primary, fallback = ProbeTTS(failures=99), ProbeTTS(failures=0)

    def make_tts(model, _voice, _language=None):
        return primary if model == voice_agent.TTS_MODEL else fallback

    monkeypatch.setattr(voice_agent, "make_tts", make_tts)

    async def main():
        return await voice_agent.working_tts()

    tts, model = asyncio.run(main())
    assert tts is fallback and model == voice_agent.TTS["fallback_model"]
    assert primary.calls == 2  # the first probe and exactly ONE retry, never a whole session on v2.5 after one blip
    assert fallback.calls == 1


def test_a_non_timeout_probe_failure_does_not_retry(monkeypatch, voice_agent):
    class FailedTTS:
        calls = 0

        def synthesize(self, _text):
            self.calls += 1

            class Stream:
                async def collect(self):
                    raise ValueError("unsupported model")

            return Stream()

    tts = FailedTTS()
    assert asyncio.run(voice_agent._probe_tts_with_retry(tts, "timbre-v3.0")) is False
    assert tts.calls == 1


def test_a_hung_timbre_probe_cannot_hold_the_session_past_the_start_budget(monkeypatch, voice_agent):
    """Regression 2026-11-15: probe + 5 s retry + probe + fallback probe could take ~29 s, longer than the page's 20 s,
    so the elder page showed "Arjun is not ready yet" although the worker was registered and had the job."""
    monkeypatch.setattr(voice_agent, "TTS_START_BUDGET_S", 0.2)
    fallback = ProbeTTS(failures=0)

    class HungTTS:
        def synthesize(self, _text):
            class Stream:
                async def collect(_self):
                    await asyncio.sleep(30)  # Timbre accepts the request and never returns audio

            return Stream()

    def make_tts(model, _voice, _language=None):
        return fallback if model == voice_agent.TTS["fallback_model"] and model != voice_agent.TTS_MODEL else HungTTS()

    monkeypatch.setattr(voice_agent, "make_tts", make_tts)
    monkeypatch.setitem(voice_agent.TTS, "fallback_model", "timbre-v2.5")
    monkeypatch.setattr(voice_agent, "TTS_MODEL", "timbre-v3.0")
    voice_agent._PROBED.clear()

    started = asyncio.run(asyncio.wait_for(_timed(voice_agent), timeout=5))
    tts, model, seconds = started
    assert tts is fallback and model == "timbre-v2.5"
    assert seconds < 2  # the budget, not the 8 + 5 + 8 s probe chain
    assert not voice_agent._PROBED  # nothing cached from the abandoned probe: the next session tries Timbre v3 again


async def _timed(voice_agent):
    import time

    t0 = time.monotonic()
    tts, model = await voice_agent.working_tts()
    return tts, model, time.monotonic() - t0
