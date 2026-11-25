"""YouTube Data API upload. Needs a one-time OAuth refresh token (see README). Stays PRIVATE unless publish=True."""
from pathlib import Path

from app.config import settings


def upload_short(path: Path, title: str, description: str, tags: list[str], publish: bool = False) -> str:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    if not (settings.yt_client_id and settings.yt_client_secret and settings.yt_refresh_token):
        raise RuntimeError("YouTube OAuth not configured (YT_CLIENT_ID/SECRET/REFRESH_TOKEN)")
    creds = Credentials(
        None, refresh_token=settings.yt_refresh_token, client_id=settings.yt_client_id,
        client_secret=settings.yt_client_secret, token_uri="https://oauth2.googleapis.com/token",
    )
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title[:100], "description": description + "\n\n#Shorts",
                    "tags": tags, "categoryId": "28"},
        "status": {"privacyStatus": "public" if publish else "private",
                   "selfDeclaredMadeForKids": False},
    }
    r = yt.videos().insert(part="snippet,status", body=body,
                           media_body=MediaFileUpload(str(path), mimetype="video/mp4", resumable=True)).execute()
    return r["id"]
