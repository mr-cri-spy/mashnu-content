from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.agents.content.graph import build_graph
from app.agents.content.prompts.platforms import PLATFORM_RULES
from app.config import settings
from app.db.models import Draft, SessionLocal
from app.integrations import notion, telegram

router = APIRouter(prefix="/content")


def auth(x_api_key: str = Header(default="")):
    if x_api_key != settings.api_key:
        raise HTTPException(401, "bad api key")


class GenerateIn(BaseModel):
    note: str = Field(min_length=20)
    platforms: list[str] = ["youtube", "short"]
    source_ref: str = ""


def _generate(note: str, platforms: list[str], source_ref: str) -> list[dict]:
    result = build_graph().invoke({"note": note, "platforms": platforms})
    out = []
    with SessionLocal() as db:
        for p, body in result["drafts"].items():
            d = Draft(source_ref=source_ref, platform=p, body=body,
                      critique_score=result["scores"].get(p, 0))
            db.add(d)
            db.flush()
            telegram.notify_draft(d.id, p, body)
            out.append({"id": d.id, "platform": p, "score": d.critique_score, "body": body})
        db.commit()
    return out


@router.post("/generate", dependencies=[Depends(auth)])
def generate(body: GenerateIn):
    bad = [p for p in body.platforms if p not in PLATFORM_RULES]
    if bad:
        raise HTTPException(422, f"unknown platforms: {bad}")
    return _generate(body.note, body.platforms, body.source_ref)


@router.post("/sync-notion", dependencies=[Depends(auth)])
def sync_notion(limit: int = 3):
    """Called by n8n/cron. Skips notes already turned into drafts."""
    created = []
    with SessionLocal() as db:
        seen = {r[0] for r in db.query(Draft.source_ref).distinct()}
    for n in notion.fetch_new_notes(limit):
        if n["id"] in seen:
            continue
        created += _generate(n["text"], ["youtube", "short"], n["id"])
    return {"created": len(created), "drafts": created}


@router.get("/drafts", dependencies=[Depends(auth)])
def list_drafts(status: str = "pending"):
    with SessionLocal() as db:
        rows = db.query(Draft).filter(Draft.status == status).order_by(Draft.id.desc()).all()
        return [{"id": d.id, "platform": d.platform, "score": d.critique_score, "body": d.body} for d in rows]


@router.post("/drafts/{draft_id}/{action}", dependencies=[Depends(auth)])
def decide(draft_id: int, action: str):
    if action not in ("approve", "reject"):
        raise HTTPException(422, "action must be approve or reject")
    with SessionLocal() as db:
        d = db.get(Draft, draft_id)
        if not d:
            raise HTTPException(404, "draft not found")
        d.status = "approved" if action == "approve" else "rejected"
        db.commit()
        return {"id": d.id, "status": d.status}
