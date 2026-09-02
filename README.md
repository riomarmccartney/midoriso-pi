# upcoming-hat

Status display for the `upcoming` Raspberry Pi 3B — a Waveshare 1.44" LCD HAT
(ST7735S, 128×128, SPI).

## Files

| File | Purpose |
|---|---|
| `st7735s.py` | Panel driver. Waveshare init sequence + verified geometry. |
| `clock.py` | HH:MM view, Nimbus Sans Bold, stretched to panel height. |
| `services.py` | Service-status polling (Vercel, Cloudflare, Slack, Figma, Claude, GitHub). |
| `status_view.py` | Service-status view for the panel. |
| `app.py` | Runs the display: cycles views, KEY1/2/3 to switch. |
| `hat-display.service` | systemd unit (supersedes `hat-clock.service`). |

## Controls

| Button | Action |
|---|---|
| KEY1 | Clock, pinned |
| KEY2 | Service status, pinned |
| KEY3 | Toggle auto-cycle |

Views auto-cycle every `HAT_CYCLE` seconds (default 8). Service polling runs on a
background thread every `HAT_POLL` seconds (default 60), so a slow or hung endpoint
can never stall rendering — the view loop always draws the last good result.

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

## SD card wear protection

The previous card failed at the controller level, so writes are kept near zero.
Measured idle write rate after these changes: **0 bytes in 90 seconds**.

Already correct out of the box on Pi OS Trixie — verify, don't assume:

| Default | Effect |
|---|---|
| `/` mounted `noatime` | No access-time write on every read |
| swap on **zram** | Compressed RAM, not a swapfile on the card |
| `/tmp` on tmpfs | Scratch files never touch the card |
| `journald Storage=volatile` | Logs live in `/run` (RAM), not `/var/log` |
| `rsyslog` inactive | No duplicate file logging |

Applied on top:

    # Batch writes into 10-minute groups (in /etc/fstab)
    PARTUUID=...  /  ext4  defaults,noatime,commit=600  0  1

    # Periodic writers. apt-daily rewrites ~147MB of package
    # indices daily; man-db rebuilds its cache.
    sudo systemctl disable --now apt-daily.timer apt-daily-upgrade.timer man-db.timer

**Keep `fstrim.timer` enabled.** TRIM lets the card's controller garbage-collect erase
blocks; disabling it shortens card life rather than extending it.

Because `apt-daily` is off, update deliberately:

    sudo apt update && sudo apt full-upgrade

This costs nothing in security terms here — `unattended-upgrades` is not installed, so
nothing was being auto-installed anyway. If you ever install it, re-enable the timers.

**Trade-off of `commit=600`:** up to 10 minutes of writes can be lost on an unclean power
cut. ext4's journal still protects filesystem *metadata*, so this risks recent data rather
than corruption. Acceptable here because the appliance holds no state worth losing — revisit
if it ever writes real data.
