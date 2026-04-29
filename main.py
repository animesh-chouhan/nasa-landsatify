#!/usr/bin/env python3
"""Create a timestamped Landsat lyric video from local assets and an LRC file."""

from __future__ import annotations

import random
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

LRC_FILE = Path("03 We Found Love.lrc")
LETTER_DIR = Path("assets/landsat-letters")
BUILD_DIR = Path("build/lyric-video")
FRAME_DIR = BUILD_DIR / "frames"
CONCAT_FILE = BUILD_DIR / "frames.txt"
AUDIO_FILE = Path("rihanna-we-found-love.mp3")
SILENT_OUTPUT_FILE = Path("landsat-lyrics.mp4")
OUTPUT_FILE = Path("landsat-lyrics-with-audio.mp4")

WIDTH = 1920
HEIGHT = 1080
FPS = 30
BACKGROUND = (8, 12, 18)
LETTER_HEIGHT = 245
LETTER_GAP = 14
WORD_GAP = 58
LINE_GAP = 34


@dataclass(frozen=True)
class LyricLine:
    time: float
    text: str


def parse_time(value: str) -> float:
    minutes, seconds = value.split(":")
    return int(minutes) * 60 + float(seconds)


def parse_length(value: str) -> float:
    minutes, seconds = value.split(":")
    return int(minutes) * 60 + int(seconds)


def parse_lrc(path: Path) -> tuple[list[LyricLine], float]:
    lines: list[LyricLine] = []
    total_length = 0.0
    timestamp_re = re.compile(r"\[(\d{2}:\d{2}(?:\.\d{1,2})?)\](.*)")

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        if raw_line.startswith("[length:"):
            total_length = parse_length(
                raw_line.removeprefix("[length:").removesuffix("]")
            )
            continue

        match = timestamp_re.match(raw_line)
        if match:
            lines.append(LyricLine(parse_time(match.group(1)), match.group(2).strip()))

    return lines, total_length


def load_letter_images() -> dict[str, list[Image.Image]]:
    images: dict[str, list[Image.Image]] = {}

    for letter_dir in sorted(LETTER_DIR.iterdir()):
        if not letter_dir.is_dir():
            continue

        letter = letter_dir.name.lower()
        variants = []
        for image_path in sorted(
            letter_dir.glob("*.jpg"), key=lambda path: int(path.stem)
        ):
            image = Image.open(image_path).convert("RGB")
            ratio = LETTER_HEIGHT / image.height
            width = round(image.width * ratio)
            variants.append(
                image.resize((width, LETTER_HEIGHT), Image.Resampling.LANCZOS)
            )

        if variants:
            images[letter] = variants

    return images


def choose_letter_image(
    letter_images: dict[str, list[Image.Image]],
    letter: str,
    line_index: int,
    char_index: int,
) -> Image.Image:
    variants = letter_images[letter]
    return variants[(line_index + char_index) % len(variants)]


def split_into_rows(
    text: str,
    letter_images: dict[str, list[Image.Image]],
    line_index: int,
) -> list[list[Image.Image | None]]:
    words = re.findall(r"[a-z]+", text.lower())
    rows: list[list[Image.Image | None]] = [[]]
    current_width = 0
    char_index = 0

    for word in words:
        word_images = [
            choose_letter_image(letter_images, letter, line_index, char_index + index)
            for index, letter in enumerate(word)
            if letter in letter_images
        ]
        if not word_images:
            continue

        word_width = sum(image.width for image in word_images)
        word_width += LETTER_GAP * (len(word_images) - 1)
        extra_gap = WORD_GAP if rows[-1] else 0

        if rows[-1] and current_width + extra_gap + word_width > WIDTH - 180:
            rows.append([])
            current_width = 0
            extra_gap = 0

        if extra_gap:
            rows[-1].append(None)
            current_width += extra_gap

        rows[-1].extend(word_images)
        current_width += word_width
        char_index += len(word)

    return [row for row in rows if row]


def row_width(row: list[Image.Image | None]) -> int:
    width = 0
    previous_was_letter = False

    for item in row:
        if item is None:
            width += WORD_GAP
            previous_was_letter = False
            continue

        if previous_was_letter:
            width += LETTER_GAP
        width += item.width
        previous_was_letter = True

    return width


def make_background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    for _ in range(900):
        x = random.randrange(WIDTH)
        y = random.randrange(HEIGHT)
        shade = random.randrange(18, 58)
        draw.point((x, y), fill=(shade, shade + 4, shade + 8))

    return image.filter(ImageFilter.GaussianBlur(0.25))


def render_frame(
    text: str,
    letter_images: dict[str, list[Image.Image]],
    line_index: int,
    output_path: Path,
) -> None:
    canvas = make_background()
    rows = split_into_rows(text, letter_images, line_index)

    if not rows:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_path)
        return

    total_height = len(rows) * LETTER_HEIGHT + (len(rows) - 1) * LINE_GAP
    y = (HEIGHT - total_height) // 2

    for row in rows:
        x = (WIDTH - row_width(row)) // 2
        previous_was_letter = False

        for item in row:
            if item is None:
                x += WORD_GAP
                previous_was_letter = False
                continue

            if previous_was_letter:
                x += LETTER_GAP

            shadow = Image.new("RGBA", item.size, (0, 0, 0, 120))
            canvas.paste(shadow, (x + 8, y + 10), shadow)
            canvas.paste(item, (x, y))
            x += item.width
            previous_was_letter = True

        y += LETTER_HEIGHT + LINE_GAP

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def write_concat_file(frame_paths: list[Path], durations: list[float]) -> None:
    lines: list[str] = []

    for frame_path, duration in zip(frame_paths, durations):
        lines.append(f"file '{frame_path.resolve()}'")
        lines.append(f"duration {duration:.3f}")

    lines.append(f"file '{frame_paths[-1].resolve()}'")
    CONCAT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_silent_video() -> None:
    random.seed(7)
    lyrics, total_length = parse_lrc(LRC_FILE)
    letter_images = load_letter_images()

    if not lyrics:
        raise RuntimeError(f"No timestamped lyrics found in {LRC_FILE}")
    if not letter_images:
        raise RuntimeError(f"No letter images found in {LETTER_DIR}")

    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    FRAME_DIR.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    durations: list[float] = []

    if lyrics[0].time > 0:
        intro_path = FRAME_DIR / "0000.png"
        render_frame("we found love", letter_images, -1, intro_path)
        frame_paths.append(intro_path)
        durations.append(lyrics[0].time)

    for index, line in enumerate(lyrics):
        next_time = lyrics[index + 1].time if index + 1 < len(lyrics) else total_length
        duration = max(0.1, next_time - line.time)
        frame_path = FRAME_DIR / f"{len(frame_paths):04d}.png"
        render_frame(line.text, letter_images, index, frame_path)
        frame_paths.append(frame_path)
        durations.append(duration)

    write_concat_file(frame_paths, durations)

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(CONCAT_FILE),
        "-vf",
        f"fps={FPS},format=yuv420p",
        "-movflags",
        "+faststart",
        str(SILENT_OUTPUT_FILE),
    ]
    subprocess.run(command, check=True)


def add_audio() -> None:
    if not AUDIO_FILE.exists():
        raise RuntimeError(f"Audio file not found: {AUDIO_FILE}")
    if not SILENT_OUTPUT_FILE.exists():
        raise RuntimeError(f"Silent video file not found: {SILENT_OUTPUT_FILE}")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(SILENT_OUTPUT_FILE),
        "-i",
        str(AUDIO_FILE),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(OUTPUT_FILE),
    ]
    subprocess.run(command, check=True)


def make_video() -> None:
    render_silent_video()
    add_audio()


if __name__ == "__main__":
    make_video()
