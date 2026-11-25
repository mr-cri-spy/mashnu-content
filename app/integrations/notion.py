import httpx

from app.config import settings

BASE = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def fetch_new_notes(limit: int = 5) -> list[dict]:
    """Return [{id, text}] for pages in the founder-notes database, newest first."""
    if not (settings.notion_token and settings.notion_database_id):
        return []
    r = httpx.post(
        f"{BASE}/databases/{settings.notion_database_id}/query",
        headers=_headers(),
        json={"page_size": limit, "sorts": [{"timestamp": "created_time", "direction": "descending"}]},
        timeout=20,
    )
    r.raise_for_status()
    notes = []
    for page in r.json()["results"]:
        blocks = httpx.get(f"{BASE}/blocks/{page['id']}/children", headers=_headers(), timeout=20)
        blocks.raise_for_status()
        text = "\n".join(
            "".join(t["plain_text"] for t in b[b["type"]].get("rich_text", []))
            for b in blocks.json()["results"]
            if b["type"] in ("paragraph", "bulleted_list_item", "heading_1", "heading_2", "heading_3")
        ).strip()
        if text:
            notes.append({"id": page["id"], "text": text})
    return notes
