"""Telegram webhook: turns Approve/Reject button presses into draft status changes.

Register once (needs a public URL):
  curl "https://api.telegram.org/bot$TOKEN/setWebhook?url=$PUBLIC/telegram/webhook&secret_token=$TELEGRAM_WEBHOOK_SECRET"
"""
import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.db.models import Draft, SessionLocal

router = APIRouter(prefix="/telegram")


def _answer(callback_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        return
    httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": text},
        timeout=10,
    )


@router.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")):
    if not settings.telegram_webhook_secret or x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(401, "bad secret")
    update = await request.json()
    cb = update.get("callback_query")
    if not cb:
        return {"ok": True}
    # only the configured owner chat may approve
    if str(cb.get("message", {}).get("chat", {}).get("id", "")) != settings.telegram_chat_id:
        raise HTTPException(403, "wrong chat")
    action, _, raw_id = cb.get("data", "").partition(":")
    if action not in ("approve", "reject") or not raw_id.isdigit():
        return {"ok": True}
    with SessionLocal() as db:
        d = db.get(Draft, int(raw_id))
        if d and d.status == "pending":
            d.status = "approved" if action == "approve" else "rejected"
            db.commit()
            msg = f"Draft #{d.id} {d.status}"
        else:
            msg = "Draft not found or already decided"
    _answer(cb["id"], msg)
    return {"ok": True}
