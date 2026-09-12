#!/usr/bin/env python3
"""Generate a temporary card portrait for effect testing."""

from __future__ import annotations

import argparse
import io
import os
import re
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit(
        "Pillow is required. Install it with: python -m pip install Pillow"
    ) from exc


WIDTH = 250
HEIGHT = 190
TEXT_WIDTH = WIDTH - 32
TEXT_HEIGHT = HEIGHT - 32
KEY_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")
NUMBERED_TEST_KEY_PATTERN = re.compile(r"^Test([0-9]+)$")
CARD_TYPE_ALIASES = {"攻击": "Attack", "Attack": "Attack", "技能": "Skill", "Skill": "Skill", "能力": "Power", "Power": "Power", "状态": "Status", "Status": "Status", "诅咒": "Curse", "Curse": "Curse"}
CARD_TYPE_COLORS = {"Attack": (244, 204, 204, 255), "Skill": (217, 234, 211, 255), "Power": (207, 226, 243, 255), "Status": (217, 217, 217, 255), "Curse": (217, 217, 217, 255)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 250x190 temporary card portrait."
    )
    parser.add_argument("--key", required=True, help="PascalCase card key.")
    parser.add_argument("--name", default="", help="Optional displayed card name.")
    parser.add_argument("--type", dest="card_type", default="Status", choices=tuple(CARD_TYPE_ALIASES), help="Card type; defaults to Status.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory. Defaults to Mod/RDMod/images/cards.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing portrait.",
    )
    return parser.parse_args()


def resolve_label(key: str, name: str) -> str:
    if name.strip():
        return name.strip()
    numbered_match = NUMBERED_TEST_KEY_PATTERN.fullmatch(key)
    return numbered_match.group(1) if numbered_match else key


def normalize_card_type(card_type: str) -> str:
    try:
        return CARD_TYPE_ALIASES[card_type.strip()]
    except (AttributeError, KeyError) as exc:
        raise ValueError(f"Unsupported card type {card_type!r}") from exc


def find_font_path() -> str:
    windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    candidates = [
        windows_fonts / "msyhbd.ttc",
        windows_fonts / "msyh.ttc",
        windows_fonts / "arialbd.ttf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(
        "No supported font was found. Install Microsoft YaHei, Arial, "
        "Noto Sans CJK, or DejaVu Sans."
    )


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    if draw.textbbox((0, 0), text, font=font, stroke_width=2)[2] <= max_width:
        return text

    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        width = draw.textbbox(
            (0, 0), candidate, font=font, stroke_width=2
        )[2]
        if current and width > max_width:
            lines.append(current.rstrip())
            current = character.lstrip()
        else:
            current = candidate
    if current:
        lines.append(current.rstrip())
    return "\n".join(lines)


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
) -> tuple[str, ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    font_sizes = range(42, 5, -1) if re.search(r"[\u4e00-\u9fff]", text) else range(56, 7, -2)
    for font_size in font_sizes:
        font = ImageFont.truetype(font_path, font_size)
        wrapped = wrap_text(draw, text, font, TEXT_WIDTH)
        bounds = draw.multiline_textbbox(
            (0, 0),
            wrapped,
            font=font,
            spacing=4,
            align="center",
            stroke_width=2,
        )
        if bounds[2] - bounds[0] <= TEXT_WIDTH and bounds[3] - bounds[1] <= TEXT_HEIGHT:
            return wrapped, font, bounds
    raise ValueError("Card name is too long to fit in the placeholder image.")


def render_placeholder(label: str, card_type: str = "Status") -> bytes:
    image = Image.new("RGBA", (WIDTH, HEIGHT), CARD_TYPE_COLORS[normalize_card_type(card_type)])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (2, 2, WIDTH - 3, HEIGHT - 3),
        radius=10,
        outline=(126, 211, 255, 255),
        width=4,
    )

    wrapped, font, bounds = fit_text(draw, label, find_font_path())
    text_width = bounds[2] - bounds[0]
    text_height = bounds[3] - bounds[1]
    position = (
        (WIDTH - text_width) / 2 - bounds[0],
        (HEIGHT - text_height) / 2 - bounds[1],
    )
    draw.multiline_text(
        position,
        wrapped,
        font=font,
        fill=(255, 255, 255, 255),
        spacing=4,
        align="center",
        stroke_width=2,
        stroke_fill=(0, 0, 0, 180),
    )

    output = io.BytesIO()
    image.convert("RGB").save(output, format="PNG")
    return output.getvalue()


def write_image(output_path: Path, payload: bytes, force: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not force:
        try:
            with output_path.open("xb") as output_file:
                output_file.write(payload)
        except FileExistsError as exc:
            raise FileExistsError(
                f"Card art already exists: {output_path}. Use --force to overwrite it."
            ) from exc
        return

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.stem}.",
            suffix=".tmp.png",
            dir=output_path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as output_file:
            output_file.write(payload)
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    if not KEY_PATTERN.fullmatch(args.key):
        raise SystemExit(
            "Card key must be PascalCase and contain only ASCII letters and digits: "
            f"{args.key}"
        )

    workspace_root = Path(__file__).resolve().parent.parent
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else workspace_root / "Mod" / "RDMod" / "images" / "cards"
    )
    output_path = output_dir / f"{args.key}.png"
    payload = render_placeholder(resolve_label(args.key, args.name), args.card_type)

    try:
        write_image(output_path, payload, args.force)
    except FileExistsError as exc:
        raise SystemExit(str(exc)) from exc

    print(output_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
