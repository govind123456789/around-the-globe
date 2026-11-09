"""Social share cards (1200x630 PNG) in the site's emerald-and-brass style."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import SITE

W, H = 1200, 630
INK, INK2, ON_INK, ON_INK_2, BRASS = (14, 43, 35), (19, 58, 47), (243, 239, 226), (169, 188, 177), (220, 193, 137)
FONTS = SITE / "assets" / "og-fonts"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, max_lines: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,.") + "…"
    return lines


def _background() -> Image.Image:
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(INK, INK2)))
    # graticule motif, cropped by the right edge
    cx, cy, r = 1030, 300, 300
    faint = tuple(int(a + (b - a) * .2) for a, b in zip(INK2, BRASS))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=tuple(int(a + (b - a) * .45) for a, b in zip(INK2, BRASS)), width=2)
    for k in (.33, .66):
        d.ellipse([cx - r * k, cy - r, cx + r * k, cy + r], outline=faint, width=1)
        d.ellipse([cx - r, cy - r * k, cx + r, cy + r * k], outline=faint, width=1)
    d.line([(cx, cy - r), (cx, cy + r)], fill=faint, width=1)
    d.line([(cx - r, cy), (cx + r, cy)], fill=faint, width=1)
    return img


def card(out: Path, site_name: str, eyebrow: str, title: str, lines: list[str]) -> None:
    img = _background()
    d = ImageDraw.Draw(img)
    x, width = 72, 800
    d.text((x, 62), site_name, font=_font("Fraunces-500.ttf", 34), fill=ON_INK)
    d.text((x, 150), eyebrow.upper(), font=_font("Inter-600.ttf", 22), fill=BRASS)
    size = 76 if len(title) < 26 else 62 if len(title) < 48 else 50
    tf = _font("Fraunces-500.ttf", size)
    y = 190
    for line in _wrap(d, title, tf, width, 3):
        d.text((x, y), line, font=tf, fill=ON_INK)
        y += int(size * 1.14)
    y += 18
    lf = _font("Inter-500.ttf", 30)
    for line in lines[:4]:
        if y > H - 92:
            break
        d.text((x, y), line, font=lf, fill=ON_INK_2)
        y += 44
    d.rectangle([x, H - 58, x + 90, H - 54], fill=BRASS)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.quantize(colors=96, dither=Image.Dither.NONE).save(out, optimize=True)
