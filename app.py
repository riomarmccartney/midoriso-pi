#!/usr/bin/env python3
"""upcoming.studio HAT display — cycles views, switchable with KEY1/2/3.

Service polling runs on a background thread so a slow or hung endpoint can
never stall rendering; the view loop always draws from the last good result.
"""
import os
import signal
import threading
import time

import RPi.GPIO as GPIO
from PIL import Image

import clock as clock_view
import status_view
from services import poll
from st7735s import Display, WIDTH, HEIGHT

KEY1, KEY2, KEY3 = 21, 20, 16          # HAT buttons, active-low
CYCLE_SECS = int(os.environ.get("HAT_CYCLE", 8))
POLL_SECS = int(os.environ.get("HAT_POLL", 60))

VIEWS = ["clock", "status"]            # "nowplaying" to be added


class Poller(threading.Thread):
    """Refreshes service status in the background; never blocks the display."""

    daemon = True

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._results = None          # None until the first poll lands
        self._stop = threading.Event()

    @property
    def results(self):
        with self._lock:
            return list(self._results) if self._results else None

    def run(self):
        while not self._stop.is_set():
            try:
                r = poll()
                with self._lock:
                    self._results = r
            except Exception:
                pass                    # keep the last good result
            self._stop.wait(POLL_SECS)

    def stop(self):
        self._stop.set()


class App:
    def __init__(self):
        self.dev = Display()
        self.font = clock_view.load_font()[0]
        self.poller = Poller()
        self.poller.start()
        self.index = 0
        self.pinned = False
        self.last_switch = time.time()
        self.last_frame = None
        self._setup_buttons()

    def _setup_buttons(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in (KEY1, KEY2, KEY3):
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(KEY1, GPIO.FALLING,
                              callback=lambda _: self.select(0), bouncetime=250)
        GPIO.add_event_detect(KEY2, GPIO.FALLING,
                              callback=lambda _: self.select(1), bouncetime=250)
        GPIO.add_event_detect(KEY3, GPIO.FALLING,
                              callback=lambda _: self.toggle_pin(), bouncetime=250)

    def select(self, i):
        if i < len(VIEWS):
            self.index = i
            self.pinned = True
            self.last_switch = time.time()
            self.last_frame = None      # force redraw

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.last_switch = time.time()

    def frame(self):
        view = VIEWS[self.index]
        if view == "clock":
            return "clock:" + time.strftime("%H:%M"), \
                   lambda: clock_view.render(time.strftime("%H:%M"), self.font)
        results = self.poller.results
        key = "status:" + ",".join(f"{n}={l}" for n, l in (results or []))
        return key, lambda: status_view.render(results) if results else \
            Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))

    def run(self):
        try:
            while True:
                if not self.pinned and time.time() - self.last_switch >= CYCLE_SECS:
                    self.index = (self.index + 1) % len(VIEWS)
                    self.last_switch = time.time()
                key, build = self.frame()
                if key != self.last_frame:      # only push when something changed
                    self.dev.show(build())
                    self.last_frame = key
                time.sleep(0.3)
        finally:
            self.shutdown()

    def shutdown(self):
        self.poller.stop()
        try:
            self.dev.show(Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)))
            self.dev.close()
        except Exception:
            pass
        GPIO.cleanup()


def main():
    app = App()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    try:
        app.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
