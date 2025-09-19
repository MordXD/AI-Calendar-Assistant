from app.sgr import SGRController
from app.models import SuggestEventsRequest

class DummyLLM(SGRController):
    pass


def test_suggest_basic(monkeypatch):
    ctrl = SGRController()

    def fake_suggest_events(self, instruction: str, now: str, timezone: str):
        return {
            "candidates": [
                {
                    "title": "Deep Work",
                    "description": "Focus block",
                    "start": "2025-09-19T10:00:00+03:00",
                    "end": "2025-09-19T12:00:00+03:00",
                    "timezone": timezone,
                }
            ]
        }

    monkeypatch.setattr(type(ctrl.llm), "suggest_events", fake_suggest_events)
    resp = ctrl.suggest(SuggestEventsRequest(instruction="Add deep work"))
    assert resp.candidates