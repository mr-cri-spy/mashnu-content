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


if __name__ == "__main__":
    print(run(" ".join(sys.argv[1:]) or "Why I never auto-post AI content"))
