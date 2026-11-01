"""Build the rich menu JPEGs from the owner art (dev-only, needs Pillow).

Usage: python richmenu/build_images.py <owner-art.png>

page1.jpg is the owner art upscaled to the LINE canvas. page2.jpg reuses its
background and footer and draws new tiles. Labels must avoid stacked Thai marks
(e.g. "ตั้ง"): this Pillow build has no raqm shaping and drops the upper mark.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CANVAS = (2500, 1686)
SCALE = 2500 / 1527
MAX_BYTES = 1_000_000

FONT = ROOT / "frontend/node_modules/@fontsource/prompt/files/prompt-thai-700-normal.woff2"
EMOJI_FONT = Path("C:/Windows/Fonts/seguiemj.ttf")
LABEL_COLOR = (163, 23, 79)
TILE_FILL = (254, 246, 248)
WIDE_FILL = (254, 214, 138)
RADIUS = 70

# Tile rectangles (x0, y0, x1, y1) in canvas space; see the plan's geometry table.
TILES = {
    "BIG": (34, 43, 1362, 1058),
    "WIDE": (34, 1079, 1364, 1501),
    "R1A": (1387, 41, 1925, 526),
    "R1B": (1952, 41, 2474, 526),
    "R2A": (1387, 552, 1925, 1048),
    "R2B": (1952, 552, 2474, 1048),
    "R3A": (1387, 1072, 1925, 1501),
    "R3B": (1952, 1072, 2474, 1501),
}
GRID = {
    "R1A": ("🎯", "สร้างเป้า"),
    "R1B": ("💰", "ออม"),
    "R2A": ("🗑", "ลบล่าสุด"),
    "R2B": ("📤", "ส่งออกข้อมูล"),
    "R3A": ("💡", "เสนอแนะ"),
    "R3B": ("📖", "วิธีใช้"),
}
# Pig face in the owner art's big tile (source pixels): centre and radius of a round badge.
PIG_CENTER = (445, 480)
PIG_RADIUS = 170
BADGE_SIZE = 520


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def _fitted_font(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int) -> ImageFont.FreeTypeFont:
    font = _font(size)
    while draw.textlength(text, font=font) > max_width and size > 40:
        size -= 4
        font = _font(size)
    return font


def _pig_badge(art: Image.Image) -> Image.Image:
    cx, cy = PIG_CENTER
    face = art.crop((cx - PIG_RADIUS, cy - PIG_RADIUS, cx + PIG_RADIUS, cy + PIG_RADIUS))
    face = face.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS).convert("RGBA")
    # Draw the mask at 4x and downscale for a smooth edge.
    mask = Image.new("L", (BADGE_SIZE * 4, BADGE_SIZE * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, BADGE_SIZE * 4 - 1, BADGE_SIZE * 4 - 1), fill=255)
    face.putalpha(mask.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS))
    ring = Image.new("RGBA", (BADGE_SIZE + 40, BADGE_SIZE + 40), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, BADGE_SIZE + 39, BADGE_SIZE + 39), fill=(251, 121, 164))
    ring.paste(face, (20, 20), face)
    return ring


def _chevron_left(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int) -> None:
    # Prompt's Thai subset has no "‹", so draw it.
    x, y = center
    half = size // 2
    draw.line([(x + half // 2, y - half), (x - half // 2, y), (x + half // 2, y + half)],
              fill=LABEL_COLOR, width=size // 5, joint="curve")


def _centered_text(draw: ImageDraw.ImageDraw, center: tuple[int, int], text: str, font) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x = center[0] - (right - left) / 2 - left
    y = center[1] - (bottom - top) / 2 - top
    draw.text((x, y), text, font=font, fill=LABEL_COLOR)


def _emoji(canvas: Image.Image, center: tuple[int, int], char: str) -> None:
    # Segoe UI Emoji renders colour glyphs at its bitmap size; draw large, then fit.
    font = ImageFont.truetype(str(EMOJI_FONT), 109)
    glyph = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(glyph).text((80, 80), char, font=font, embedded_color=True, anchor="mm")
    glyph = glyph.crop(glyph.getbbox()).resize((190, 190), Image.LANCZOS)
    canvas.paste(glyph, (center[0] - 95, center[1] - 95), glyph)


def build_page1(art: Image.Image) -> Image.Image:
    return art.resize(CANVAS, Image.LANCZOS)


def build_page2(art: Image.Image, page1: Image.Image) -> Image.Image:
    canvas = page1.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    for name, rect in TILES.items():
        draw.rounded_rectangle(rect, RADIUS, fill=WIDE_FILL if name == "WIDE" else TILE_FILL)

    x0, y0, x1, y1 = TILES["BIG"]
    badge = _pig_badge(art)
    canvas.paste(badge, (x1 - badge.width - 70, y1 - badge.height - 50), badge)
    draw.text((x0 + 110, y0 + 90), "เป้าหมาย", font=_font(170), fill=LABEL_COLOR)
    draw.text((x0 + 110, y0 + 280), "การออม", font=_font(170), fill=LABEL_COLOR)

    x0, y0, x1, y1 = TILES["WIDE"]
    label_font = _font(150)
    text_width = draw.textlength("กลับหน้าแรก", font=label_font)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    _chevron_left(draw, (round(cx - text_width / 2 - 40), cy), 110)
    _centered_text(draw, (cx + 40, cy), "กลับหน้าแรก", label_font)

    for name, (char, label) in GRID.items():
        x0, y0, x1, y1 = TILES[name]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        _emoji(canvas, (cx, cy - 70), char)
        _centered_text(draw, (cx, cy + 115), label, _fitted_font(draw, label, 100, x1 - x0 - 90))
    return canvas.convert("RGB")


def save_jpeg(image: Image.Image, path: Path) -> int:
    for quality in range(92, 59, -4):
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=quality, optimize=True)
        if buffer.tell() <= MAX_BYTES:
            path.write_bytes(buffer.getvalue())
            return quality
    raise SystemExit(f"{path.name}: cannot fit {MAX_BYTES} bytes at quality >= 60")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    art = Image.open(argv[0]).convert("RGB")
    page1 = build_page1(art)
    for name, image in (("page1", page1), ("page2", build_page2(art, page1))):
        path = HERE / f"{name}.jpg"
        quality = save_jpeg(image, path)
        print(f"{path.name}: {image.size[0]}x{image.size[1]}, {path.stat().st_size} bytes, quality {quality}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
