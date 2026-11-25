"""Cross-post the rendered Short. Each platform is optional and never fails the job."""
import os

import httpx

GRAPH = "https://graph-video.facebook.com/v21.0"


def post_facebook(mp4, title: str, caption: str, publish: bool) -> str | None:
    page, token = os.getenv("FB_PAGE_ID"), os.getenv("FB_PAGE_TOKEN")
    if not (page and token):
        return None
    with open(mp4, "rb") as f:
        r = httpx.post(
            f"{GRAPH}/{page}/videos",
            data={
                "access_token": token,
                "title": title,
                "description": caption,
                "published": "true" if publish else "false",
            },
            files={"source": f},
            timeout=300,
        )
    r.raise_for_status()
    return r.json().get("id")


def post_bluesky(mp4, title: str, caption: str, publish: bool) -> str | None:
    handle, pw = os.getenv("BSKY_HANDLE"), os.getenv("BSKY_APP_PASSWORD")
    if not (handle and pw) or not publish:  # Bluesky has no drafts: only post when publishing
        return None
    from atproto import Client

    c = Client()
    c.login(handle, pw)
    text = (title + "\n\n" + caption)[:290]
    with open(mp4, "rb") as f:
        r = c.send_video(text=text, video=f.read(), video_alt=title)
    return r.uri


def post_all(mp4, title: str, caption: str, publish: bool) -> dict:
    out = {}
    for name, fn in (("facebook_id", post_facebook), ("bluesky_uri", post_bluesky)):
        try:
            out[name] = fn(mp4, title, caption, publish)
        except Exception as e:  # noqa: BLE001 - one platform must not break the others
            out[name] = f"error: {e!r}"
    return out
