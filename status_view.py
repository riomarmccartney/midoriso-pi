#!/usr/bin/env python3
"""Service-status view for the 128x128 HAT panel.

Six services, one row each, with a colour-coded dot. Colour carries the state
redundantly with position so it stays readable at this size; the header bar
shows the worst state across all services for an at-a-glance read.
"""
from PIL import Image, ImageDraw, ImageFont
from services import poll, worst, OK, MINOR, MAJOR, UNKNOWN

WIDTH = HEIGHT = 128

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

COLOUR = {
    OK:      (0, 200, 110),
    MINOR:   (240, 170, 30),
    MAJOR:   (240, 55, 65),
    UNKNOWN: (110, 110, 110),
}
LABEL = {OK: "ALL OK", MINOR: "DEGRADED", MAJOR: "OUTAGE", UNKNOWN: "NO DATA"}

BG = (0, 0, 0)
HEADER_H = 20
ROW_H = 17
DOT_R = 3


def _font(size):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(results=None):
    results = poll() if results is None else results
    overall = worst(results)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    # header: solid bar in the worst-state colour, so the summary reads instantly
    d.rectangle([0, 0, WIDTH - 1, HEADER_H - 1], fill=COLOUR[overall])
    hf = _font(12)
    text = LABEL[overall]
    tw = d.textbbox((0, 0), text, font=hf)[2]
    d.text(((WIDTH - tw) // 2, 3), text, font=hf, fill=(0, 0, 0))

    rf = _font(11)
    y = HEADER_H + 3
    for name, level in results:
        cy = y + ROW_H // 2 - 1
        d.ellipse([7 - DOT_R, cy - DOT_R, 7 + DOT_R, cy + DOT_R], fill=COLOUR[level])
        d.text((18, y + 1), name, font=rf, fill=(235, 235, 235))
        if level != OK:                      # annotate only what needs attention
            tag = level.upper()
            tw = d.textbbox((0, 0), tag, font=rf)[2]
            d.text((WIDTH - tw - 5, y + 1), tag, font=rf, fill=COLOUR[level])
        y += ROW_H
    return img


if __name__ == "__main__":
    import sys
    res = poll()
    img = render(res)
    for name, lvl in res:
        print(f"  {name:<10} {lvl}")
    print("overall:", worst(res))
    if "--show" in sys.argv:
        from st7735s import Display
        Display().show(img)
        print("displayed on HAT")
    else:
        img.save("/tmp/status_preview.png")
        print("saved /tmp/status_preview.png")
