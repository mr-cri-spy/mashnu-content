"""Daily job: topic -> LLM beats (JSON) -> render mp4 -> upload (private by default).
Run: python -m app.video.daily "topic or founder note"   (cron/Render cron job)"""
import json
import re
import sys
from datetime import date
from pathlib import Path

from app.agents.content.graph import VOICE
from app.agents.content.llm import LLM, get_llm
from app.video.render import render_short

PROMPT = (
    VOICE + "\n\nWrite a 30-45s vertical Short. Reply with ONLY JSON: "
    '{"title": str (<60 chars), "caption": str, "tags": [str], '
    '"beats": [{"screen": str (<=8 words), "spoken": str}]} with 5-7 beats, ~100 spoken words total. '
    "Beat 1 is a hook with a concrete specific. Never invent clients, metrics or results."
)


def plan(topic: str, llm: LLM | None = None) -> dict:
    raw = (llm or get_llm()).complete(PROMPT, topic)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("LLM did not return JSON")
    data = json.loads(m.group(0))
    assert data["beats"], "no beats"
    return data


def run(topic: str, out_dir: str = "out", upload: bool = True, publish: bool = False) -> dict:
    data = plan(topic)
    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    mp4 = render_short([(b["screen"], b["spoken"]) for b in data["beats"]], out / f"{date.today()}.mp4")
    result = {"file": str(mp4), "title": data["title"]}
    if upload:
        from app.video.upload import upload_short

        result["youtube_id"] = upload_short(mp4, data["title"], data["caption"], data["tags"], publish)
    return result


TOPICS = [
    "I built an AI content engine in one afternoon: FastAPI, LangGraph, free Gemini API, human approval before posting",
    "Zapier vs owning your core: why per-task pricing hurts when every step calls an LLM",
    "Why a WhatsApp AI lead responder helps clinics and real-estate brokers reply in seconds",
    "A free-tier AI stack for startups: Gemini free API, FastAPI, Postgres, Docker",
    "Why I never auto-post AI content: the human approval step in the Mashnu content engine",
    "My AI critiques its own drafts and rewrites the weak ones: how the critique loop works",
    "Voice agents vs chatbots for small businesses: when each one wins",
]

if __name__ == "__main__":
    import os

    topic = " ".join(sys.argv[1:]) or TOPICS[date.today().toordinal() % len(TOPICS)]
    print(run(topic, publish=os.getenv("AUTO_PUBLISH", "false").lower() == "true"))
