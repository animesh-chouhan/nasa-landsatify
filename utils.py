from __future__ import annotations

import random
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH = 2560
HEIGHT = 1920
FPS = 30
BACKGROUND = (8, 12, 18)
LETTER_HEIGHT_RATIO = 0.3  # Keep this as is, as it affects letter size
LETTER_GAP_RATIO = 0.01  # Reduced to half to decrease gap between letters
WORD_GAP_RATIO = 0.05
LINE_GAP_RATIO = 0.045
SIDE_MARGIN_RATIO = 0.06
BACKGROUND_POINTS_RATIO = 0.00045
BACKGROUNDS_DIR = Path("assets/backgrounds")
TEXT_GLYPH_HEIGHT_RATIO = 0.62
FONT_PATH = "/usr/share/fonts/truetype/freefont/FreeSansBoldOblique.ttf"
CAPTION_FONT_PATH = FONT_PATH
CAPTION_FONT_SIZE_RATIO = 0.045
CAPTION_BOTTOM_MARGIN_RATIO = 0.045
CAPTION_MAX_WIDTH_RATIO = 0.88
CAPTION_LINE_GAP_RATIO = 0.012
CAPTION_COLOR = (237, 217, 60)
CAPTION_SHADOW = (0, 0, 0)
LETTER_CAPTION_GAP_RATIO = 0.008
CAPTION_STROKE_WIDTH = 3  # Re-adding this constant
MAX_WORDS_FOR_NO_WRAP = 2  # Phrases with this many words or fewer will not wrap.
APOSTROPHE_GLYPH_PADDING_X = 0  # Smaller padding for apostrophe glyph
GLYPH_PADDING_X = 9  # Half of the 18px added to glyph width
SHADOW_OFFSET_X = 8
SHADOW_OFFSET_Y = 10
SHADOW_ALPHA = 120  # For paste_item shadow

LETTER_HEIGHT = round(HEIGHT * LETTER_HEIGHT_RATIO)
LETTER_GAP = round(WIDTH * LETTER_GAP_RATIO)
WORD_GAP = round(WIDTH * WORD_GAP_RATIO)
LINE_GAP = round(HEIGHT * LINE_GAP_RATIO)
SIDE_MARGIN = round(WIDTH * SIDE_MARGIN_RATIO)
BACKGROUND_POINTS = round(WIDTH * HEIGHT * BACKGROUND_POINTS_RATIO)
TEXT_GLYPH_HEIGHT = round(LETTER_HEIGHT * TEXT_GLYPH_HEIGHT_RATIO)
CAPTION_FONT_SIZE = round(HEIGHT * CAPTION_FONT_SIZE_RATIO)
CAPTION_BOTTOM_MARGIN = round(HEIGHT * CAPTION_BOTTOM_MARGIN_RATIO)
CAPTION_MAX_WIDTH = round(WIDTH * CAPTION_MAX_WIDTH_RATIO)
CAPTION_LINE_GAP = round(HEIGHT * CAPTION_LINE_GAP_RATIO)
LETTER_CAPTION_GAP = round(HEIGHT * LETTER_CAPTION_GAP_RATIO)


def normalize_lyric_text(text: str) -> str:
    text = re.sub(r"['\u2019]", "", text.lower())
    return " ".join(re.findall(r"[a-z]+", text))


def display_lyric_text(text: str) -> str:
    return " ".join(text.strip().split())


def _load_font_robustly(
    font_paths: list[str | Path], size: int
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Helper to load a font from a list of paths, falling back to default."""
    font_paths = [
        str(p) for p in font_paths if p  # Ensure paths are strings and not empty
    ]
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_glyph_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_paths = [FONT_PATH, "FreeSansBoldOblique.ttf", "DejaVuSans-Bold.ttf"]
    return _load_font_robustly(font_paths, TEXT_GLYPH_HEIGHT)


def load_caption_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_paths = [
        CAPTION_FONT_PATH,
        FONT_PATH,
        "FreeSansBoldOblique.ttf",
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    return _load_font_robustly(font_paths, CAPTION_FONT_SIZE)


def load_letter_images(letter_dir: Path) -> dict[str, list[Image.Image]]:
    images: dict[str, list[Image.Image]] = {}

    for letter_path in sorted(letter_dir.iterdir()):
        if not letter_path.is_dir():
            continue

        letter = letter_path.name.lower()
        variants = []
        for image_path in sorted(
            letter_path.glob("*.jpg"), key=lambda path: int(path.stem)
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


def load_background_images(background_dir: Path) -> list[Image.Image]:
    """Loads and resizes background images from a directory."""
    images: list[Image.Image] = []
    if not background_dir.is_dir():
        return images

    for image_path in sorted(background_dir.iterdir()):
        if not image_path.is_file() or image_path.suffix.lower() not in [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        ]:
            continue
        try:
            image = Image.open(image_path).convert("RGB")
            # Resize to fit the frame dimensions
            image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            images.append(image)
        except Exception as e:
            print(f"Warning: Could not load background image {image_path}: {e}")
            continue
    return images


def choose_letter_image(
    letter_images: dict[str, list[Image.Image]],
    letter: str,
) -> Image.Image:
    return random.choice(letter_images[letter])


def make_text_glyph(char: str) -> Image.Image:
    font = load_glyph_font()
    probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), char, font=font)
    text_width = max(1, bbox[2] - bbox[0])

    current_glyph_padding_x = GLYPH_PADDING_X
    if char == "'":
        current_glyph_padding_x = APOSTROPHE_GLYPH_PADDING_X

    # Add padding to the glyph image to prevent clipping and for visual spacing
    image = Image.new(
        "RGBA",
        (text_width + (current_glyph_padding_x * 2), LETTER_HEIGHT),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(image)
    x = current_glyph_padding_x - bbox[0]
    y = (LETTER_HEIGHT - (bbox[3] - bbox[1])) // 2 - bbox[1]  # Center vertically
    draw.text((x + 3, y + 4), char, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), char, font=font, fill=(235, 242, 248, 235))
    return image


def make_token_images(
    token: str,
    letter_images: dict[str, list[Image.Image]],
) -> list[Image.Image]:
    images: list[Image.Image] = []

    for char in token:
        letter = char.lower()
        if letter in letter_images:
            images.append(choose_letter_image(letter_images, letter))
        elif not char.isspace():
            images.append(make_text_glyph(char))

    return images


def split_into_rows(
    text: str,
    letter_images: dict[str, list[Image.Image]],
) -> list[list[Image.Image | None]]:
    words = display_lyric_text(text).split()
    rows: list[list[Image.Image | None]] = [[]]
    current_width = 0
    for word in words:
        word_images = make_token_images(word, letter_images)
        if not word_images:
            continue

        word_width = sum(image.width for image in word_images)
        word_width += LETTER_GAP * (len(word_images) - 1)
        extra_gap = WORD_GAP if rows[-1] else 0

        if rows[-1] and current_width + extra_gap + word_width > WIDTH - (
            SIDE_MARGIN * 2
        ):
            rows.append([])
            current_width = 0
            extra_gap = 0

        if extra_gap:
            rows[-1].append(None)
            current_width += extra_gap

        rows[-1].extend(word_images)
        current_width += word_width

    return [row for row in rows if row]


def scale_rows_to_fit(
    rows: list[list[Image.Image | None]],
    text: str,
) -> list[list[Image.Image | None]]:
    if not rows:
        return rows

    caption_top = get_caption_top(text)

    max_width = WIDTH - (SIDE_MARGIN * 2)
    max_height = caption_top - LETTER_CAPTION_GAP - SIDE_MARGIN
    total_height = len(rows) * LETTER_HEIGHT + (len(rows) - 1) * LINE_GAP
    widest_row = max(row_width(row) for row in rows)
    scale = min(1.0, max_width / widest_row, max_height / total_height)

    if scale >= 1:
        return rows

    scaled_rows: list[list[Image.Image | None]] = []
    for row in rows:
        scaled_row: list[Image.Image | None] = []
        for item in row:
            if item is None:
                scaled_row.append(None)
                continue

            size = (
                max(1, round(item.width * scale)),
                max(1, round(item.height * scale)),
            )
            scaled_row.append(item.resize(size, Image.Resampling.LANCZOS))
        scaled_rows.append(scaled_row)

    return scaled_rows


def row_height(row: list[Image.Image | None]) -> int:
    return max((item.height for item in row if item is not None), default=0)


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


def make_background(
    background_images: list[Image.Image], background_index: int
) -> Image.Image:
    """
    Creates a background image, either by choosing one sequentially from the provided
    list or by generating a procedural one if the list is empty.
    """
    if background_images:
        image_index = background_index % len(
            background_images
        )  # Use modulo to cycle through backgrounds
        return background_images[
            image_index
        ].copy()  # Return a copy to prevent in-place modification
    else:
        # Fallback to procedural background if no images are loaded
        image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
        draw = ImageDraw.Draw(image)

        for _ in range(BACKGROUND_POINTS):
            x = random.randrange(WIDTH)
            y = random.randrange(HEIGHT)
            shade = random.randrange(18, 58)
            draw.point((x, y), fill=(shade, shade + 4, shade + 8))
        return image.filter(ImageFilter.GaussianBlur(0.25))


def render_frame(
    text: str,
    letter_images: dict[str, list[Image.Image]],
    background_images: list[Image.Image],
    output_path: Path,
    background_index: int,  # Index for cycling backgrounds
    override_caption: (
        str | None
    ) = None,  # Optional text to override the caption display
) -> None:
    canvas = make_background(background_images, background_index)

    # Main letters always use the original 'text' parameter
    main_display_text = text
    rows = scale_rows_to_fit(split_into_rows(main_display_text, letter_images), text)

    if not rows:
        # Use override_caption for caption if provided, otherwise use original text
        caption_to_draw = override_caption if override_caption is not None else text
        draw_caption(canvas, caption_to_draw)
        canvas.save(output_path)
        return

    total_height = sum(row_height(row) for row in rows) + (len(rows) - 1) * LINE_GAP
    caption_top = get_caption_top(text)
    available_height = max(1, caption_top - LETTER_CAPTION_GAP)
    y = (available_height - total_height) // 2

    for row in rows:
        x = (WIDTH - row_width(row)) // 2
        previous_was_letter = False
        height = row_height(row)

        for item in row:
            if item is None:
                x += WORD_GAP
                previous_was_letter = False
                continue

            if previous_was_letter:
                x += LETTER_GAP

            paste_item(canvas, item, x, y)
            x += item.width
            previous_was_letter = True

        y += height + LINE_GAP

    # Use override_caption for caption if provided, otherwise use original text
    caption_to_draw = override_caption if override_caption is not None else text
    draw_caption(
        canvas, caption_to_draw
    )  # Draw caption after letters to ensure it's on top
    canvas.save(output_path)


def draw_caption(canvas: Image.Image, text: str) -> None:
    caption = display_lyric_text(text)
    if not caption:
        return
    caption = "♪ " + caption + " ♪" # Add musical note characters

    font = load_caption_font()
    draw = ImageDraw.Draw(canvas)
    lines = wrap_caption(caption, draw, font)
    line_height = caption_line_height(draw, font)
    total_height = len(lines) * line_height + (len(lines) - 1) * CAPTION_LINE_GAP
    y = HEIGHT - CAPTION_BOTTOM_MARGIN - total_height

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        x = (WIDTH - width) // 2  # Center the text

        # Draw shadow with stroke
        draw.text(
            (x + 3, y + 4),  # Shadow offset
            line,
            font=font,
            fill=CAPTION_SHADOW,
            stroke_width=CAPTION_STROKE_WIDTH,
            stroke_fill=CAPTION_SHADOW,
        )
        # Draw main text with stroke
        draw.text(
            (x, y),
            line,
            font=font,
            fill=CAPTION_COLOR,
            stroke_width=CAPTION_STROKE_WIDTH,
            stroke_fill=(0, 0, 0),  # Black stroke for main text
        )
        y += line_height + CAPTION_LINE_GAP


def get_caption_top(text: str) -> int:
    caption = display_lyric_text(text)
    if not caption:
        return HEIGHT

    font = load_caption_font()
    probe = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(probe)
    lines = wrap_caption(caption, draw, font)
    line_height = caption_line_height(draw, font)
    total_height = len(lines) * line_height + (len(lines) - 1) * CAPTION_LINE_GAP
    return HEIGHT - CAPTION_BOTTOM_MARGIN - total_height


def caption_reserved_height() -> int:
    return CAPTION_FONT_SIZE + CAPTION_BOTTOM_MARGIN + LETTER_CAPTION_GAP


def wrap_caption(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> list[str]:
    words = text.split()
    if not words:  # Handle empty text
        # Return a reasonable default height if no words to measure
        return caption_line_height(draw, font)
        return []

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox(
            (0, 0), candidate, font=font, stroke_width=CAPTION_STROKE_WIDTH
        )  # Account for stroke
        if bbox[2] - bbox[0] <= CAPTION_MAX_WIDTH:
            current = candidate
            continue

        lines.append(current)
        current = word

    lines.append(current)
    return lines


def caption_line_height(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox(
        (0, 0), "Ag", font=font, stroke_width=CAPTION_STROKE_WIDTH
    )  # Account for stroke
    return bbox[3] - bbox[1]


def paste_item(canvas: Image.Image, item: Image.Image, x: int, y: int) -> None:
    if item.mode == "RGBA":
        alpha = item.getchannel("A")
        shadow = Image.new("RGB", item.size, (0, 0, 0))  # Black shadow base
        shadow_alpha = alpha.point(
            lambda value: min(value, SHADOW_ALPHA)
        )  # Apply transparency
        canvas.paste(shadow, (x + SHADOW_OFFSET_X, y + SHADOW_OFFSET_Y), shadow_alpha)
        canvas.paste(item.convert("RGB"), (x, y), alpha)
        return

    shadow = Image.new("RGBA", item.size, (0, 0, 0, SHADOW_ALPHA))  # For non-RGBA items
    canvas.paste(shadow, (x + SHADOW_OFFSET_X, y + SHADOW_OFFSET_Y), shadow)
    canvas.paste(item, (x, y))


def write_concat_file(
    concat_file: Path,
    frame_paths: list[Path],
    durations: list[float],
) -> None:
    lines: list[str] = []

    for frame_path, duration in zip(frame_paths, durations):
        lines.append(f"file '{frame_path.resolve()}'")
        lines.append(f"duration {duration:.3f}")

    if frame_paths:  # Crucial for FFmpeg to correctly process the last frame's duration
        lines.append(f"file '{frame_paths[-1].resolve()}'")
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_video_from_frames(concat_file: Path, output_file: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-vf",
        f"fps={FPS},format=yuv420p",
        "-movflags",
        "+faststart",
        str(output_file),
    ]
    subprocess.run(command, check=True)


def add_audio_to_video(
    silent_output_file: Path,
    audio_file: Path,
    output_file: Path,
    start_time: float = 0.0,
) -> None:
    if not audio_file.exists():
        raise RuntimeError(f"Audio file not found: {audio_file}")
    if not silent_output_file.exists():
        raise RuntimeError(f"Silent video file not found: {silent_output_file}")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(silent_output_file),
    ]

    if start_time > 0:
        command.extend(["-ss", f"{start_time:.3f}"])

    command.extend(
        [
            "-i",
            str(audio_file),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_file),
        ]
    )
    subprocess.run(command, check=True)
