PLATFORM_RULES = {
    "x": "X thread: 5-7 posts, each under 270 chars, numbered 1/ 2/ ... Post 1 is the hook. Last post is a takeaway, not a CTA.",
    "linkedin": "LinkedIn post: 900-1300 chars, hook line, short paragraphs, one clear lesson, one question at the end.",
    "medium": "Medium article outline plus intro: title, 5-7 section headings with one-line summaries, and a full 150-word intro.",
    "short": (
        "Vertical 30-45s video for YouTube Shorts AND Instagram Reels (~100 spoken words). Output exactly:\n"
        "HOOK (first 2s, spoken + on-screen text)\nSCRIPT (spoken lines, one per row, with [VISUAL: ...] cues)\n"
        "ON-SCREEN TEXT (3-5 captions)\nCTA (one line, a follow or comment prompt)\n"
        "CAPTION (under 150 chars) + 5 hashtags\nTITLE (Shorts title under 60 chars)"
    ),
    "youtube": (
        "YouTube video 6-10 min, screen-share/explainer style. Output exactly:\n"
        "3 TITLE OPTIONS (under 60 chars, specific, no clickbait lies)\nTHUMBNAIL TEXT (max 4 words) + visual idea\n"
        "HOOK (first 20s, states the payoff)\nOUTLINE with timestamps and full spoken script per section, "
        "each with [SCREEN: what is shown]\nPROOF MOMENT (a real demo or number shown on screen)\n"
        "END SCREEN CTA\nDESCRIPTION (first 2 lines matter) + 8 tags"
    ),
}
VIDEO_PLATFORMS = ("short", "youtube")
