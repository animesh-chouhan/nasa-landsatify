#!/usr/bin/env python3
"""Create a timestamped Landsat lyric video from local assets and an LRC file."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from utils import (
    add_audio_to_video,
    display_lyric_text,
    load_letter_images,
    normalize_lyric_text,
    load_background_images,
    render_frame,
    render_video_from_frames,
    write_concat_file,
)

LRC_FILE = Path("we-found-love-edited.lrc")
LETTER_DIR = Path("assets/landsat-letters")
from utils import BACKGROUNDS_DIR

BUILD_DIR = Path("build/lyric-video")
FRAME_DIR = BUILD_DIR / "frames"
CONCAT_FILE = BUILD_DIR / "frames.txt"
OUTPUT_DIR = Path("build/output")
AUDIO_FILE = Path("rihanna-we-found-love.mp3")
SILENT_OUTPUT_FILE = OUTPUT_DIR / "landsat-lyrics.mp4"
OUTPUT_FILE = OUTPUT_DIR / "landsat-lyrics-with-audio.mp4"

START_TIME = "00:00"
END_TIME = "01:00"

MAX_WORDS_PER_FRAME = 4
MIN_SPLIT_DURATION = 1.2

LRC_TAG_RE = re.compile(r"\[([^\]]+)\]")
LRC_TIMESTAMP_RE = re.compile(r"^\d{1,3}:\d{2}(?:\.\d{1,3})?$")


@dataclass(frozen=True)
class LyricLine:
    time: float
    text: str


@dataclass(frozen=True)
class LyricSegment:
    text: str
    duration: float


def parse_time(value: str) -> float:
    minutes, seconds = value.strip().split(":")
    return int(minutes) * 60 + float(seconds)


def parse_length(value: str) -> float:
    minutes, seconds = value.strip().split(":")
    return int(minutes) * 60 + int(seconds)


def parse_optional_time(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return parse_time(value)


def parse_lrc(path: Path) -> tuple[list[LyricLine], float]:
    lines: list[LyricLine] = []
    metadata: dict[str, str] = {}
    total_length = 0.0

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        tags = LRC_TAG_RE.findall(raw_line)
        timestamps = [
            parse_time(tag) for tag in tags if LRC_TIMESTAMP_RE.match(tag.strip())
        ]

        if not timestamps:
            if len(tags) == 1 and ":" in tags[0]:
                key, value = tags[0].split(":", 1)
                metadata[key.strip().lower()] = value.strip()
            continue

        text = LRC_TAG_RE.sub("", raw_line).strip()
        lines.extend(LyricLine(timestamp, text) for timestamp in timestamps)

    if "length" in metadata:
        total_length = parse_length(metadata["length"])

    lines.sort(key=lambda line: line.time)

    return lines, total_length


def split_long_lyric(text: str, duration: float) -> list[LyricSegment]:
    display_words = display_lyric_text(text).split()
    normalized_words = [normalize_lyric_text(word) for word in display_words]
    words_for_scoring = [word for word in normalized_words if word]

    if (
        len(words_for_scoring) <= MAX_WORDS_PER_FRAME
        or duration < MIN_SPLIT_DURATION * 2
    ):
        return [LyricSegment(display_lyric_text(text), duration)]

    best_split = 1
    best_score = float("inf")

    for split_at in range(1, len(display_words)):
        left = normalized_words[:split_at]
        right = normalized_words[split_at:]
        if len(left) == 1 or len(right) == 1:
            continue

        left_chars = sum(len(word) for word in left)
        right_chars = sum(len(word) for word in right)
        score = abs(left_chars - right_chars) + abs(len(left) - len(right)) * 2

        if score < best_score:
            best_score = score
            best_split = split_at

    chunks = [
        " ".join(display_words[:best_split]),
        " ".join(display_words[best_split:]),
    ]
    normalized_chunks = [normalize_lyric_text(chunk) for chunk in chunks]
    weights = [max(1, len(chunk.replace(" ", ""))) for chunk in normalized_chunks]
    total_weight = sum(weights)

    return [
        LyricSegment(chunk, duration * weight / total_weight)
        for chunk, weight in zip(chunks, weights)
    ]


def render_silent_video() -> None:
    lyrics, total_length = parse_lrc(LRC_FILE)
    letter_images = load_letter_images(LETTER_DIR)
    background_images = load_background_images(BACKGROUNDS_DIR)
    start_time = parse_optional_time(START_TIME) or 0.0
    end_time = parse_optional_time(END_TIME) or total_length

    if not lyrics:
        raise RuntimeError(f"No timestamped lyrics found in {LRC_FILE}")
    if not letter_images:
        raise RuntimeError(f"No letter images found in {LETTER_DIR}")
    if end_time <= start_time:
        raise RuntimeError("END_TIME must be later than START_TIME")

    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    FRAME_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    frame_paths: list[Path] = []
    durations: list[float] = []
    if start_time == 0 and lyrics[0].time > 0:
        intro_path = FRAME_DIR / "0000.png"
        render_frame(
            "We Found Love",
            letter_images,
            background_images,
            intro_path,
            background_index=0,
            override_caption="Rihanna - We Found Love ft. Calvin Harris",  # Override caption for intro
        )
        frame_paths.append(intro_path)
        durations.append(lyrics[0].time)

    for (
        _index,
        line,
    ) in enumerate(  # Renamed to _index as it's no longer used for background selection
        lyrics
    ):  # Renamed to _index as it's no longer used for background
        next_time = (
            lyrics[_index + 1].time if _index + 1 < len(lyrics) else total_length
        )
        segment_start = max(line.time, start_time)
        segment_end = min(next_time, end_time)

        if segment_end <= segment_start:
            continue
        duration = max(0.1, segment_end - segment_start)

        for segment in split_long_lyric(line.text, duration):
            frame_index = len(frame_paths)
            frame_path = FRAME_DIR / f"{frame_index:04d}.png"
            render_frame(
                segment.text,
                letter_images,
                background_images,
                frame_path,
                background_index=frame_index,  # Cycle background per actual frame
            )
            frame_paths.append(frame_path)
            durations.append(segment.duration)

    write_concat_file(CONCAT_FILE, frame_paths, durations)
    render_video_from_frames(CONCAT_FILE, SILENT_OUTPUT_FILE)


def add_audio() -> None:
    add_audio_to_video(
        SILENT_OUTPUT_FILE,
        AUDIO_FILE,
        OUTPUT_FILE,
        start_time=parse_optional_time(START_TIME) or 0.0,
    )


def make_video() -> None:
    render_silent_video()
    add_audio()


if __name__ == "__main__":
    make_video()
