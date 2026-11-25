"""Script -> vertical 1080x1920 mp4: text-card slides + voiceover (edge-tts, free) via ffmpeg."""
import asyncio
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG, FG, ACCENT = (11, 15, 25), (240, 244, 255), (80, 200, 160)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VOICE = "en-IN-PrabhatNeural"


def _card(text: str, path: Path, brand: str = "MASHNU AI") -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(FONT, 78)
    small = ImageFont.truetype(FONT, 40)
    lines = textwrap.wrap(text, width=20)
    y = (H - len(lines) * 100) // 2
    for ln in lines:
        w = d.textlength(ln, font=big)
        d.text(((W - w) / 2, y), ln, font=big, fill=FG)
        y += 100
    d.rectangle([(W // 2 - 80, y + 30), (W // 2 + 80, y + 38)], fill=ACCENT)
    d.text((60, H - 140), brand, font=small, fill=ACCENT)
    img.save(path)


async def _tts(text: str, out: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, VOICE).save(str(out))


def _duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def render_short(beats: list[tuple[str, str]], out: Path, silent: bool = False) -> Path:
    """beats = [(on_screen_text, spoken_line), ...]. silent=True skips TTS (offline tests)."""
    out = Path(out)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        for i, (screen, spoken) in enumerate(beats):
            img, clip = tmp / f"{i}.png", tmp / f"{i}.mp4"
            _card(screen, img)
            if silent:
                dur = max(2.0, len(spoken.split()) / 2.7)
                audio = ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono"]
            else:
                mp3 = tmp / f"{i}.mp3"
                asyncio.run(_tts(spoken, mp3))
                dur = _duration(mp3) + 0.3
                audio = ["-i", str(mp3)]
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), *audio,
                 "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                 "-r", "30", "-c:a", "aac", "-shortest", str(clip)], check=True)
            clips.append(clip)
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{c}'\n" for c in clips))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out
