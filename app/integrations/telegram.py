import httpx

from app.config import settings


def notify_draft(draft_id: int, platform: str, body: str) -> bool:
    """Send a draft preview with Approve/Reject buttons. No-op without credentials."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": f"[{platform.upper()}] draft #{draft_id}\n\n{body[:3500]}",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "Approve", "callback_data": f"approve:{draft_id}"},
                {"text": "Reject", "callback_data": f"reject:{draft_id}"},
            ]]
        },
    }
    r = httpx.post(url, json=payload, timeout=15)
    return r.is_success
