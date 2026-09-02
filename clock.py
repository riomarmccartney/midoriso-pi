#!/usr/bin/env python3
"""upcoming.studio clock for the Waveshare 1.44in LCD HAT.

Renders HH:MM in Nimbus Sans (URW's Helvetica clone - metrically identical),
cropped to the glyph ink and stretched to the full panel width, with a small
vertical margin so the digits do not touch the top and bottom edges.

The composed image is in viewer-upright orientation; st7735s.Display.show()
applies the panel rotation, so VMARGIN maps directly to the viewed top/bottom.
"""
import os
import time
from PIL import Image, ImageDraw, ImageFont
from st7735s import Display, WIDTH, HEIGHT

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
    "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
RENDER_PT = 200                                     # oversized, then cropped + scaled
VMARGIN = int(os.environ.get("HAT_VMARGIN", 1))     # px of black at top AND bottom
FG = (255, 255, 255)
BG = (0, 0, 0)


def load_font():
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, RENDER_PT), path
        except OSError:
            continue
    raise SystemExit("no usable font found")


def render(text, font, vmargin=None):
    """Draw text oversized, crop to the ink, stretch to fill minus the margin."""
    m = VMARGIN if vmargin is None else vmargin
    pad = RENDER_PT
    canvas = Image.new("RGB", (pad * 6, pad * 3), BG)
    ImageDraw.Draw(canvas).text((pad, pad // 2), text, font=font, fill=FG)
    bbox = canvas.getbbox()                 # tight box around non-black pixels
    frame = Image.new("RGB", (WIDTH, HEIGHT), BG)
    if not bbox:
        return frame
    inner_h = max(1, HEIGHT - 2 * m)
    frame.paste(canvas.crop(bbox).resize((WIDTH, inner_h), Image.LANCZOS), (0, m))
    return frame


def main():
    font, path = load_font()
    print(f"font: {path}  vmargin: {VMARGIN}px")
    dev = Display()
    last = None
    try:
        while True:
            now = time.strftime("%H:%M")
            if now != last:
                dev.show(render(now, font))
                last = now
            time.sleep(0.5)
    except KeyboardInterrupt:
        dev.show(Image.new("RGB", (WIDTH, HEIGHT), BG))
        dev.close()


if __name__ == "__main__":
    main()
