"""Builds the die face images served under /app/static/dice from the Achilles card.

The four colored faces are the Attack Chart icons and the Charge face is the Charge token of the Ultimate box, cut
out of the full-size card scan so the die looks exactly like the cards. The Miss face is plain black.

Run once when the card art changes:  python -m presentation.build_dice
"""
from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

from finaltitan.catalog import ASSETS
from presentation.render import STATIC

SOURCE = ASSETS / "titans" / "achilles.jpg"
OUT = STATIC / "dice"
SIZE = 192
# Centers and outer radii in pixels of the 1287 px wide card scan.
CHART = {"blue": (795, 899), "green": (926, 899), "yellow": (1059, 899), "red": (1192, 899)}
CHART_RADIUS = 54
CHARGE = ((997, 426), 32)


def _disc(im: Image.Image, center: tuple[int, int], radius: int) -> Image.Image:
    cx, cy = center
    pad = radius + 2
    crop = im.crop((cx - pad, cy - pad, cx + pad, cy + pad)).resize((SIZE, SIZE), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (SIZE * 4, SIZE * 4), 0)
    r = SIZE * 4 * radius / (2 * pad)
    ImageDraw.Draw(mask).ellipse((SIZE * 2 - r, SIZE * 2 - r, SIZE * 2 + r, SIZE * 2 + r), fill=255)
    mask = mask.resize((SIZE, SIZE), Image.LANCZOS)
    crop.putalpha(ImageChops.multiply(crop.getchannel("A"), mask))
    return crop


def _miss() -> Image.Image:
    im = Image.new("RGBA", (SIZE * 4, SIZE * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((8, 8, SIZE * 4 - 8, SIZE * 4 - 8), fill=(10, 10, 14, 255), outline=(70, 70, 82, 255), width=28)
    return im.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as src:
        card = src.convert("RGB")
        faces = {name: _disc(card, c, CHART_RADIUS) for name, c in CHART.items()}
        faces["charge"] = _disc(card, *CHARGE)
    faces["miss"] = _miss()
    for name, im in faces.items():
        im.save(OUT / f"{name}.webp", "WEBP", quality=92, method=6)
    print(f"{len(faces)} die faces in {OUT}")


if __name__ == "__main__":
    main()
