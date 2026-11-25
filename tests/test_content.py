from pathlib import Path
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_content.db"
os.environ["LLM_PROVIDER"] = "fake"

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.content.graph import build_graph  # noqa: E402
from app.agents.content.llm import FakeLLM  # noqa: E402
from app.main import app  # noqa: E402

H = {"x-api-key": "change-me"}
NOTE = "Our WhatsApp agent cut lead response time from 4 hours to 40 seconds for a Mysore clinic."


def test_graph_drafts_all_platforms():
    r = build_graph(FakeLLM()).invoke({"note": NOTE, "platforms": ["x", "linkedin", "medium", "short", "youtube"]})
    assert set(r["drafts"]) == {"x", "linkedin", "medium", "short", "youtube"}
    assert all(s >= 7 for s in r["scores"].values())


def test_graph_retries_once_on_low_score():
    calls = {"n": 0}

    class Flaky(FakeLLM):
        def complete(self, system, user):
            if "SCORE" in system:
                calls["n"] += 1
                return "SCORE: 3\nFEEDBACK: vague" if calls["n"] == 1 else "SCORE: 9\nFEEDBACK: ok"
            return super().complete(system, user)

    r = build_graph(Flaky()).invoke({"note": NOTE, "platforms": ["x"]})
    assert r["retries"] == 2 and r["scores"]["x"] == 9


def test_api_flow():
    with TestClient(app) as c:
        assert c.post("/content/generate", json={"note": NOTE}).status_code == 401
        res = c.post("/content/generate", json={"note": NOTE}, headers=H)
        assert res.status_code == 200 and len(res.json()) == 2
        did = res.json()[0]["id"]
        assert c.post(f"/content/drafts/{did}/approve", headers=H).json()["status"] == "approved"
        assert c.post("/content/generate", json={"note": NOTE, "platforms": ["tiktok"]}, headers=H).status_code == 422


def test_telegram_webhook_approves_and_rejects_bad_callers():
    from app.config import settings

    settings.telegram_webhook_secret = "s3cret"
    settings.telegram_chat_id = "42"
    with TestClient(app) as c:
        did = c.post("/content/generate", json={"note": NOTE}, headers=H).json()[0]["id"]
        upd = {"callback_query": {"id": "1", "data": f"approve:{did}", "message": {"chat": {"id": 42}}}}
        assert c.post("/telegram/webhook", json=upd).status_code == 401
        hdr = {"x-telegram-bot-api-secret-token": "s3cret"}
        wrong = {"callback_query": {**upd["callback_query"], "message": {"chat": {"id": 7}}}}
        assert c.post("/telegram/webhook", json=wrong, headers=hdr).status_code == 403
        assert c.post("/telegram/webhook", json=upd, headers=hdr).status_code == 200
        approved = [d["id"] for d in c.get("/content/drafts?status=approved", headers=H).json()]
        assert did in approved


def test_render_short_silent(tmp_path):
    from app.video.render import render_short

    out = render_short([("AI writes it", "AI writes it."), ("AI rejects it", "Then it rejects it.")],
                       tmp_path / "s.mp4", silent=True)
    assert out.exists() and out.stat().st_size > 5000


def test_daily_plan_and_render(tmp_path, monkeypatch):
    import json

    from app.video import daily

    class J(FakeLLM):
        def complete(self, system, user):
            return json.dumps({"title": "t", "caption": "c", "tags": ["a"],
                               "beats": [{"screen": "Hook here", "spoken": "Hook line."},
                                         {"screen": "Point two", "spoken": "Second point."}]})

    monkeypatch.setattr(daily, "get_llm", lambda: J())
    monkeypatch.setattr(daily, "render_short",
                        lambda beats, out: (out.write_bytes(b"x" * 10), out)[1])
    res = daily.run("topic", out_dir=str(tmp_path), upload=False)
    assert res["title"] == "t" and Path(res["file"]).exists()
