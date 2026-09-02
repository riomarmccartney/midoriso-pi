# upcoming-hat

Status display for the `upcoming` Raspberry Pi 3B — a Waveshare 1.44" LCD HAT
(ST7735S, 128×128, SPI).

## Files

| File | Purpose |
|---|---|
| `st7735s.py` | Panel driver. Waveshare init sequence + verified geometry. |
| `clock.py` | HH:MM view, Nimbus Sans Bold, stretched to panel height. |
| `services.py` | Service-status polling (Vercel, Cloudflare, Slack, Figma, Claude, GitHub). |
| `hat-clock.service` | systemd unit. |

## Panel configuration — do not re-derive

These were established empirically and cost real time to find:

- `MADCTL 0xC8` — `MY|MX|BGR`. The **BGR bit is required**; this panel is not RGB.
- `XOFF=3, YOFF=2` — the ST7735S has 132×162 of RAM; the 128×128 panel sits at this origin.
- `ROTATION=-90` — applied in software so the offsets above stay valid. Changing MADCTL's
  MX/MY bits instead moves the RAM origin and forces re-deriving both offsets.
- Blank all 132×162 of RAM at init, or unwritten regions show as fine lines at the edges.

**`luma.lcd` does not drive this panel.** It installs, imports, opens SPI and toggles the
backlight without error, then leaves the screen blank — its generic ST7735 init does not
match the ST7735S. Nothing fails loudly. Use `st7735s.py`.

### Debugging heuristics

| Symptom | Cause |
|---|---|
| Backlight on, screen blank | Init sequence wrong |
| Correct block geometry, wrong colours | Colour format, not offsets |
| Clipped at the *viewed bottom* | `XOFF` — `rotate(-90)` maps composed-bottom to sent-low-X |
| Fine lines at screen edges | RAM outside the 128×128 window never blanked |

## Service status gotchas

- Anthropic's endpoint returns **403 to the default `Python-urllib` User-Agent**. Send a real
  one. This fails on the Pi too, not just macOS.
- Slack is **not** Statuspage-shaped and inverts the convention: `"active"` means an incident
  is open, `"ok"` means healthy.
- macOS Python needs `certifi` to verify TLS; Debian does not.

## Deploy

    scp *.py pi@upcoming.local:~/hat/
    ssh pi@upcoming.local 'sudo systemctl restart hat-clock'

Runtime tuning without edits: `HAT_XOFF`, `HAT_YOFF`, `HAT_VMARGIN`, `HAT_DEBUG`.
