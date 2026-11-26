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

def _release_url(mp4) -> str:
    """Host the MP4 as a GitHub Release asset (free, public) and return its URL."""
    repo, gh = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not (repo and gh):
        raise RuntimeError("GITHUB_REPOSITORY/GITHUB_TOKEN missing")
    import datetime as dt

    tag = "video-" + dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    h = {"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"}
    rel = httpx.post(f"https://api.github.com/repos/{repo}/releases", headers=h,
                     json={"tag_name": tag, "name": tag}, timeout=60)
    rel.raise_for_status()
    up = rel.json()["upload_url"].split("{")[0]
    with open(mp4, "rb") as f:
        a = httpx.post(up, params={"name": "short.mp4"}, content=f.read(), timeout=300,
                       headers={**h, "Content-Type": "video/mp4"})
    a.raise_for_status()
    return a.json()["browser_download_url"]


def post_threads(mp4, title: str, caption: str, publish: bool) -> str | None:
    import time

    token = os.getenv("THREADS_TOKEN")
    if not token or not publish:  # Threads has no drafts: only post when publishing
        return None
    api = "https://graph.threads.net/v1.0"
    uid = httpx.get(f"{api}/me", params={"fields": "id", "access_token": token}, timeout=30)
    uid.raise_for_status()
    uid = uid.json()["id"]
    url = _release_url(mp4)
    c = httpx.post(f"{api}/{uid}/threads", timeout=60, data={
        "media_type": "VIDEO", "video_url": url,
        "text": (title + "\n\n" + caption)[:490], "access_token": token})
    c.raise_for_status()
    cid = c.json()["id"]
    for _ in range(30):  # wait for Threads to finish processing the video
        st = httpx.get(f"{api}/{cid}", params={"fields": "status,error_message",
                                              "access_token": token}, timeout=30).json()
        if st.get("status") == "FINISHED":
            break
        if st.get("status") == "ERROR":
            raise RuntimeError(st.get("error_message", "threads processing error"))
        time.sleep(10)
    p = httpx.post(f"{api}/{uid}/threads_publish", timeout=60,
                   data={"creation_id": cid, "access_token": token})
    p.raise_for_status()
    return p.json().get("id")


def post_all(mp4, title: str, caption: str, publish: bool) -> dict:
    out = {}
    for name, fn in (("facebook_id", post_facebook), ("bluesky_uri", post_bluesky), ("threads_id", post_threads)):
        try:
            out[name] = fn(mp4, title, caption, publish)
        except Exception as e:  # noqa: BLE001 - one platform must not break the others
            out[name] = f"error: {e!r}"
    return out
