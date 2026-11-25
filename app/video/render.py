"""Script -> animated vertical 1080x1920 mp4. Free stack: Pillow + numpy frames piped to ffmpeg,
edge-tts voiceover with word timings for karaoke captions.

Look: drifting glow background (accent colour changes each beat), pop-in headline words,
ghost beat number, growing underline, top progress bar, word-by-word highlighted captions."""
import asyncio
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VOICE = "en-IN-PrabhatNeural"
PALETTE = [(80, 200, 160), (255, 170, 60), (120, 140, 255), (255, 100, 140), (70, 200, 255)]
WHITE = (245, 247, 255)
OUT_FADE = 0.25

_fonts: dict[int, ImageFont.FreeTypeFont] = {}
_sprites: dict[tuple, Image.Image] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT, size)
    return _fonts[size]


# ---------- audio ----------

async def _tts(text: str, out: Path) -> list[tuple[str, float, float]]:
    """Save mp3, return [(word, start_s, end_s)] (empty if no word timings). Falls back to simpler
    edge-tts options if the service rejects the fancy ones."""
    import edge_tts

    attempts = [
        {"rate": "+6%", "boundary": "WordBoundary"},
        {"boundary": "WordBoundary"},
        {},
    ]
    last: Exception | None = None
    for kw in attempts:
        words: list[tuple[str, float, float]] = []
        try:
            comm = edge_tts.Communicate(text, VOICE, **kw)
            got_audio = False
            with open(out, "wb") as f:
                async for ch in comm.stream():
                    if ch["type"] == "audio":
                        f.write(ch["data"])
                        got_audio = True
                    elif ch["type"] == "WordBoundary":
                        s = ch["offset"] / 1e7
                        words.append((ch["text"], s, s + ch["duration"] / 1e7))
            if got_audio:
                return words
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[tts] attempt {kw} failed: {e!r}")
        await asyncio.sleep(1)
    raise RuntimeError(f"edge-tts failed: {last!r}")


def _duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _even_words(spoken: str, dur: float) -> list[tuple[str, float, float]]:
    toks = spoken.split()
    wts = [len(t) + 2 for t in toks]
    total, t, out = sum(wts), 0.1, []
    span = max(0.5, dur - 0.4)
    for tok, w in zip(toks, wts):
        e = t + span * w / total
        out.append((tok, t, e))
        t = e
    return out


# ---------- drawing helpers ----------

def _ease_out_back(p: float) -> float:
    p = min(1.0, max(0.0, p))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def _ease_out(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def _word_sprite(word: str, size: int, color: tuple) -> Image.Image:
    key = (word, size, color)
    if key not in _sprites:
        f = _font(size)
        l, t, r, b = f.getbbox(word)
        pad = 24
        img = Image.new("RGBA", (int(r - l) + pad * 2, size + pad * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((pad + 5, pad + 7), word, font=f, fill=(0, 0, 0, 150))
        d.text((pad, pad), word, font=f, fill=color + (255,))
        _sprites[key] = img
    return _sprites[key]


def _blob(radius: int, color: tuple, strength: float) -> tuple[Image.Image, Image.Image]:
    n = radius * 2
    yy, xx = np.mgrid[0:n, 0:n]
    r = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    mask = (np.clip(1 - r, 0, 1) ** 2 * 255 * strength).astype(np.uint8)
    return Image.new("RGB", (n, n), color), Image.fromarray(mask, "L")


def _gradient() -> Image.Image:
    top, bot = np.array((7, 10, 22)), np.array((22, 24, 54))
    t = np.linspace(0, 1, H)[:, None, None]
    arr = (top * (1 - t) + bot * t).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, W, axis=1), "RGB")



def _robot(t: float, talk: float, accent: tuple, wave: bool) -> Image.Image:
    """Original cartoon mascot 'Mashu' drawn at 2x then downsampled. talk in 0..1 opens the mouth."""
    S = 2
    img = Image.new("RGBA", (760, 700), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bob = 10 * math.sin(t * 3)
    ink, shell, screen = (20, 24, 48), (232, 238, 255), (16, 20, 42)
    d.ellipse([(210, 650), (550, 695)], fill=(0, 0, 0, 90))  # ground shadow
    # arms (behind body)
    sway = math.sin(t * (9 if wave else 3))
    ang = 0.55 + (0.7 if wave else 0.15) * sway
    sx, sy = 520, 500 + bob * 0.5
    hx, hy = sx + 140 * math.cos(ang), sy - 150 * math.sin(ang) + 60
    d.line([(sx, sy), (hx, hy)], fill=shell, width=34)
    d.ellipse([(hx - 28, hy - 28), (hx + 28, hy + 28)], fill=accent)
    lx, ly = 240, 500 + bob * 0.5
    ex, ey = 130, 600 + 14 * math.sin(t * 3 + 1)
    d.line([(lx, ly), (ex, ey)], fill=shell, width=34)
    d.ellipse([(ex - 28, ey - 28), (ex + 28, ey + 28)], fill=accent)
    # body
    d.rounded_rectangle([(240, 440 + bob * 0.5), (520, 650)], radius=70, fill=shell, outline=accent, width=10)
    r = 26 + 5 * math.sin(t * 5)
    d.ellipse([(380 - r, 545 - r), (380 + r, 545 + r)], fill=accent)
    # antenna
    d.line([(380, 125 + bob), (380, 65 + bob)], fill=shell, width=12)
    pr = 24 + 4 * math.sin(t * 6)
    d.ellipse([(380 - pr, 45 + bob - pr), (380 + pr, 45 + bob + pr)], fill=accent)
    # ears + head
    for ex0 in (104, 612):
        d.rounded_rectangle([(ex0, 235 + bob), (ex0 + 44, 315 + bob)], radius=18, fill=accent)
    d.rounded_rectangle([(140, 120 + bob), (620, 430 + bob)], radius=100, fill=shell, outline=accent, width=10)
    d.rounded_rectangle([(186, 165 + bob), (574, 392 + bob)], radius=64, fill=screen)
    # eyes (blink every ~3.2s, pupils wander)
    ph = (t % 3.2)
    blink = 0.12 if ph > 3.05 else 1.0
    lookx, looky = 9 * math.sin(t * 0.9), 5 * math.sin(t * 1.3)
    for cx in (302, 458):
        cy = 262 + bob
        ry = 44 * blink
        d.ellipse([(cx - 44, cy - ry), (cx + 44, cy + ry)], fill=(250, 252, 255))
        if blink > 0.5:
            d.ellipse([(cx - 20 + lookx, cy - 20 + looky), (cx + 20 + lookx, cy + 20 + looky)], fill=ink)
            d.ellipse([(cx - 8 + lookx, cy - 14 + looky), (cx + 4 + lookx, cy - 2 + looky)], fill=(255, 255, 255))
    # cheeks
    for cx in (250, 510):
        d.ellipse([(cx - 22, 322 + bob - 14), (cx + 22, 322 + bob + 14)], fill=(255, 120, 150, 200))
    # mouth
    my = 340 + bob
    if talk > 0.1:
        oh = 12 + 40 * talk
        d.ellipse([(345, my - oh / 2), (415, my + oh / 2)], fill=accent)
        d.ellipse([(362, my + oh / 2 - 14), (398, my + oh / 2 + 4)], fill=(255, 110, 130))
    else:
        d.arc([(335, my - 30), (425, my + 22)], 20, 160, fill=accent, width=9)
    return img.resize((int(img.width * 0.7), int(img.height * 0.7)), Image.LANCZOS)


def _layout_headline(text: str, size: int, max_w: int = 900) -> list[list[tuple[str, int]]]:
    f = _font(size)
    lines, cur, cur_w = [], [], 0
    space = f.getlength(" ")
    for w in text.split():
        ww = int(f.getlength(w))
        if cur and cur_w + space + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0
        cur.append((w, ww))
        cur_w += ww + (space if len(cur) > 1 else 0)
    if cur:
        lines.append(cur)
    return lines


def _chunks(words: list[tuple[str, float, float]]) -> list[list[tuple[str, float, float]]]:
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or w[0].endswith((".", "?", "!", ",", ";", ":")):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


class _Beat:
    def __init__(self, idx: int, total: int, screen: str, words, dur: float, start: float):
        self.idx, self.total, self.screen, self.dur, self.start = idx, total, screen, dur, start
        self.accent = PALETTE[idx % len(PALETTE)]
        self.words = words
        n = len(screen.split())
        self.size = 112 if n <= 3 else 96 if n <= 5 else 82
        self.lines = _layout_headline(screen, self.size)
        self.longest = max((w for ln in self.lines for w, _ in ln), key=len, default="")
        self.chunks = _chunks(words)
        self.ghost = self._ghost()

    def _ghost(self) -> Image.Image:
        f = _font(520)
        txt = f"{self.idx + 1:02d}"
        l, t, r, b = f.getbbox(txt)
        img = Image.new("RGBA", (int(r - l) + 20, 560), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((0, 0), txt, font=f, fill=self.accent + (34,))
        return img


def _draw_frame(base: Image.Image, beat: _Beat, lt: float, gt: float, total: float, blobs) -> Image.Image:
    frame = base.copy()
    a = beat.accent
    # drifting glows
    for k, (col_img, mask, bx, by, ax, ay, sp) in enumerate(blobs):
        x = int(bx + ax * math.sin(gt * sp + k))
        y = int(by + ay * math.cos(gt * sp * 0.8 + k))
        tinted = Image.new("RGB", col_img.size, a if k == 0 else tuple(int(c * 0.6) for c in a))
        frame.paste(tinted, (x - col_img.width // 2, y - col_img.height // 2), mask)

    d = ImageDraw.Draw(frame)
    fade = min(1.0, max(0.0, (beat.dur - lt) / OUT_FADE))

    # ghost beat number
    gh = beat.ghost
    gx = int(40 - 30 * (1 - _ease_out(lt / 0.6)))
    frame.paste(gh, (gx, 130), gh.split()[3].point(lambda v: int(v * fade)))

    # top progress bar + brand + counter
    d.rectangle([(0, 0), (W, 12)], fill=(30, 34, 60))
    d.rectangle([(0, 0), (int(W * min(1, gt / total)), 12)], fill=a)
    d.text((60, 52), "MASHNU AI", font=_font(38), fill=a)
    cnt = f"{beat.idx + 1}/{beat.total}"
    d.text((W - 60 - d.textlength(cnt, font=_font(38)), 52), cnt, font=_font(38), fill=(150, 160, 190))

    # headline words (pop-in, staggered)
    lh = int(beat.size * 1.28)
    block_h = lh * len(beat.lines)
    y0 = 690 - block_h // 2
    wi = 0
    space = _font(beat.size).getlength(" ")
    for li, line in enumerate(beat.lines):
        line_w = sum(w for _, w in line) + space * (len(line) - 1)
        x = (W - line_w) / 2
        cy = y0 + li * lh + beat.size / 2
        for word, ww in line:
            p = (lt - 0.08 - wi * 0.11) / 0.38
            if p > 0:
                col = a if word == beat.longest else WHITE
                sp = _word_sprite(word, beat.size, col)
                s = 0.6 + 0.4 * _ease_out_back(p)
                nw, nh = max(1, int(sp.width * s)), max(1, int(sp.height * s))
                spr = sp.resize((nw, nh), Image.BILINEAR) if abs(s - 1) > 0.01 else sp
                alpha = min(1.0, p * 2.5) * fade
                mask = spr.split()[3].point(lambda v: int(v * alpha)) if alpha < 0.99 else spr.split()[3]
                px = int(x + ww / 2 - nw / 2)
                py = int(cy - nh / 2 + (1 - min(1, p)) * 50)
                frame.paste(spr.convert("RGB"), (px, py), mask)
            x += ww + space
            wi += 1

    # underline grows after headline lands
    up = _ease_out((lt - 0.15 - wi * 0.11) / 0.5)
    if up > 0:
        half = int(110 * up)
        yb = y0 + block_h + 30
        d.rounded_rectangle([(W // 2 - half, yb), (W // 2 + half, yb + 12)], radius=6, fill=a)

    # cartoon mascot, mouth synced to the active spoken word
    talking = any(w[1] <= lt < w[2] for w in beat.words)
    talk = 0.35 + 0.65 * abs(math.sin(lt * 17)) if talking else 0.0
    rb = _robot(gt, talk, a, wave=beat.idx == 0 or beat.idx == beat.total - 1)
    pop = _ease_out_back(lt / 0.55)
    ry = int(1010 + (1 - min(1.0, pop)) * 260)
    ra = rb.split()[3].point(lambda v: int(v * fade * min(1.0, lt / 0.25)))
    frame.paste(rb.convert("RGB"), ((W - rb.width) // 2, ry), ra)

    # karaoke captions
    cur = None
    for i, ch in enumerate(beat.chunks):
        nxt = beat.chunks[i + 1][0][1] if i + 1 < len(beat.chunks) else beat.dur
        if lt >= ch[0][1] - 0.15 and lt < nxt:
            cur = ch
    if cur is None and beat.chunks and lt > 0.15:
        cur = beat.chunks[0]
    if cur:
        f = _font(64)
        toks = [w[0] for w in cur]
        full = " ".join(toks)
        rows = [cur] if f.getlength(full) <= 960 else [cur[: len(cur) // 2], cur[len(cur) // 2:]]
        row_h, ycap = 92, 1545
        box_h = row_h * len(rows) + 30
        bw = int(max(f.getlength(" ".join(w[0] for w in r)) for r in rows)) + 90
        mask = Image.new("L", (bw, box_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (bw - 1, box_h - 1)], radius=36, fill=int(170 * fade))
        frame.paste(Image.new("RGB", (bw, box_h), (6, 8, 18)), ((W - bw) // 2, ycap - 15), mask)
        for ri, r in enumerate(rows):
            rw = f.getlength(" ".join(w[0] for w in r))
            x = (W - rw) / 2
            for word, s, e in r:
                active = s - 0.02 <= lt < e + 0.04
                d.text((x, ycap + ri * row_h), word, font=f, fill=a if active else WHITE)
                x += f.getlength(word + " ")
    return frame


# ---------- main ----------

def render_short(beats: list[tuple[str, str]], out: Path, silent: bool = False,
                 outro: bool = True) -> Path:
    """beats = [(on_screen_text, spoken_line), ...]. silent=True skips TTS (offline tests)."""
    out = Path(out)
    beats = list(beats)
    if outro:
        beats.append(("Follow for daily AI builds", "Follow Mashnu AI for a new build every day."))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wavs, timed, durs = [], [], []
        for i, (screen, spoken) in enumerate(beats):
            wav = tmp / f"{i}.wav"
            words: list = []
            if silent:
                dur = max(2.4, len(spoken.split()) / 2.7 + 0.4)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                "anullsrc=r=44100:cl=mono", "-t", f"{dur:.2f}", str(wav)], check=True)
            else:
                mp3 = tmp / f"{i}.mp3"
                words = asyncio.run(_tts(spoken, mp3))
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                                "apad=pad_dur=0.35", "-ar", "44100", "-ac", "1", str(wav)], check=True)
                dur = _duration(wav)
            if not words:
                words = _even_words(spoken, dur)
            wavs.append(wav)
            timed.append(words)
            durs.append(dur)
        lst = tmp / "a.txt"
        lst.write_text("".join(f"file '{w}'\n" for w in wavs))
        audio = tmp / "all.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", str(audio)], check=True)

        total = sum(durs)
        starts = np.cumsum([0] + durs[:-1])
        objs = [_Beat(i, len(beats), beats[i][0], timed[i], durs[i], float(starts[i])) for i in range(len(beats))]
        base = _gradient()
        b1c, b1m = _blob(620, (255, 255, 255), 0.30)
        b2c, b2m = _blob(520, (255, 255, 255), 0.22)
        blobs = [(b1c, b1m, 300, 560, 220, 160, 0.55), (b2c, b2m, 820, 1450, 180, 220, 0.43)]

        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)],
            stdin=subprocess.PIPE)
        try:
            n = int(total * FPS)
            bi = 0
            for fi in range(n):
                gt = fi / FPS
                while bi + 1 < len(objs) and gt >= objs[bi + 1].start:
                    bi += 1
                b = objs[bi]
                proc.stdin.write(_draw_frame(base, b, gt - b.start, gt, total, blobs).tobytes())
        finally:
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError("ffmpeg failed")
    return out
