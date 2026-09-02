#!/usr/bin/env python3
"""Verified driver for the Waveshare 1.44in LCD HAT (ST7735S, 128x128).

Confirmed empirically on this board, 2026-09-01:
  MADCTL 0xC8     MY|MX|BGR - the BGR bit is REQUIRED, this panel is BGR.
  XOFF 1, YOFF 2  ST7735S RAM is 132x162; the 128x128 panel sits at this origin.
  Waveshare's init sequence - luma.lcd's generic ST7735 init leaves the panel
                  blank (backlight on, no image) because it initialises wrongly.

ROTATION corrects the panel's physical mounting in software, so the verified
XOFF/YOFF stay valid. Changing MADCTL's MX/MY bits instead would move the RAM
origin and require re-deriving both offsets.
"""
import os
import time
import numpy as np
import spidev
import RPi.GPIO as GPIO

DC, RST, BL = 25, 27, 24
WIDTH = HEIGHT = 128
# Overridable for calibration: HAT_XOFF / HAT_YOFF env vars.
# Viewed-bottom clipping is an XOFF error, not YOFF: rotate(-90) maps the
# composed image's bottom edge onto the sent image's left (low-X) edge.
XOFF = int(os.environ.get("HAT_XOFF", 3))
YOFF = int(os.environ.get("HAT_YOFF", 2))
MADCTL = 0xC8
RAM_W, RAM_H = 132, 162   # ST7735S RAM is larger than the panel
ROTATION = -90          # degrees; PIL convention (negative = clockwise)


class Display:
    def __init__(self, speed_hz=16_000_000, rotation=None):
        self.rotation = ROTATION if rotation is None else rotation
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for p in (DC, RST, BL):
            GPIO.setup(p, GPIO.OUT)
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0
        self.backlight(True)
        self._init_panel()

    def backlight(self, on):
        GPIO.output(BL, 1 if on else 0)

    def _cmd(self, c):
        GPIO.output(DC, 0)
        self.spi.writebytes([c])

    def _dat(self, *b):
        GPIO.output(DC, 1)
        self.spi.writebytes(list(b))

    def _init_panel(self):
        GPIO.output(RST, 1); time.sleep(.1)
        GPIO.output(RST, 0); time.sleep(.1)
        GPIO.output(RST, 1); time.sleep(.12)
        self._cmd(0x11); time.sleep(.12)                     # sleep out
        self._cmd(0xB1); self._dat(0x01, 0x2C, 0x2D)         # frame rate
        self._cmd(0xB2); self._dat(0x01, 0x2C, 0x2D)
        self._cmd(0xB3); self._dat(0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D)
        self._cmd(0xB4); self._dat(0x07)                     # inversion
        self._cmd(0xC0); self._dat(0xA2, 0x02, 0x84)         # power
        self._cmd(0xC1); self._dat(0xC5)
        self._cmd(0xC2); self._dat(0x0A, 0x00)
        self._cmd(0xC3); self._dat(0x8A, 0x2A)
        self._cmd(0xC4); self._dat(0x8A, 0xEE)
        self._cmd(0xC5); self._dat(0x0E)                     # VCOM
        self._cmd(0xE0); self._dat(0x0F,0x1A,0x0F,0x18,0x2F,0x28,0x20,0x22,
                                   0x1F,0x1B,0x23,0x37,0x00,0x07,0x02,0x10)
        self._cmd(0xE1); self._dat(0x0F,0x1B,0x0F,0x17,0x33,0x2C,0x29,0x2E,
                                   0x30,0x30,0x39,0x3F,0x00,0x07,0x03,0x10)
        self._cmd(0x3A); self._dat(0x05)                     # 16-bit colour
        self._cmd(0x36); self._dat(MADCTL)
        self._cmd(0x29); time.sleep(.1)                      # display on
        self._clear_ram()

    def _clear_ram(self):
        """Blank all 132x162 of controller RAM.

        The panel shows a sliver of the RAM outside our 128x128 window; if it is
        never written it displays stale pixels as fine lines at the screen edge.
        """
        self._cmd(0x2A); self._dat(0x00, 0, 0x00, RAM_W - 1)
        self._cmd(0x2B); self._dat(0x00, 0, 0x00, RAM_H - 1)
        self._cmd(0x2C)
        GPIO.output(DC, 1)
        blank = bytes(RAM_W * RAM_H * 2)
        for i in range(0, len(blank), 4096):
            self.spi.writebytes2(blank[i:i + 4096])

    def show(self, img, rotation=None):
        """Push a 128x128 PIL image to the panel. Compose upright; this rotates."""
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.size != (WIDTH, HEIGHT):
            img = img.resize((WIDTH, HEIGHT))
        rot = self.rotation if rotation is None else rotation
        if rot:
            img = img.rotate(rot, expand=False)

        # RGB888 -> RGB565 big-endian, vectorised.
        a = np.asarray(img, dtype=np.uint16)
        v = ((a[:, :, 0] & 0xF8) << 8) | ((a[:, :, 1] & 0xFC) << 3) | (a[:, :, 2] >> 3)
        buf = v.astype(">u2").tobytes()

        self._cmd(0x2A); self._dat(0x00, XOFF, 0x00, WIDTH - 1 + XOFF)
        self._cmd(0x2B); self._dat(0x00, YOFF, 0x00, HEIGHT - 1 + YOFF)
        self._cmd(0x2C)
        GPIO.output(DC, 1)
        for i in range(0, len(buf), 4096):
            self.spi.writebytes2(buf[i:i + 4096])

    def close(self):
        self.spi.close()
