#!/usr/bin/env python3
"""Service status polling for the upcoming.studio HAT display.

All endpoints verified live 2026-09-02. Five are Statuspage-format and share a
parser; Slack is not Statuspage and inverts the convention - it reports
"active" when something is WRONG and "ok" when fine.

Network calls run concurrently, so total latency is one timeout, not six.
"""
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
import json
import os
import ssl
import sys

TIMEOUT = 8
DEBUG = bool(os.environ.get("HAT_DEBUG"))

# Debian (the Pi) verifies against the system CA store out of the box; macOS
# Python does not, so fall back to certifi when it is importable. Keeps this
# module testable off-device without weakening verification anywhere.
try:
    import certifi
    _SSL = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL = ssl.create_default_context()


# Some status endpoints (Anthropic's among them) return 403 to the default
# "Python-urllib/3.x" User-Agent. Identify properly instead.
UA = "upcoming-studio-hat/1.0 (+https://upcoming.studio)"


def _get(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=TIMEOUT, context=_SSL) as r:
        return json.load(r)

# normalised levels, worst last - order matters for `worst()`
OK, MINOR, MAJOR, UNKNOWN = "ok", "minor", "major", "unknown"
_RANK = {OK: 0, UNKNOWN: 1, MINOR: 2, MAJOR: 3}

# Statuspage "indicator" -> our level
_INDICATOR = {"none": OK, "minor": MINOR, "major": MAJOR, "critical": MAJOR}


def _statuspage(url):
    d = _get(url)
    return _INDICATOR.get(d.get("status", {}).get("indicator"), UNKNOWN)


def _slack(url):
    """Slack: status == 'ok' means healthy; 'active' means an incident is open."""
    d = _get(url)
    if d.get("status") == "ok":
        return OK
    incidents = d.get("active_incidents", [])
    if not incidents:
        return OK
    types = {str(i.get("type", "")).lower() for i in incidents}
    return MAJOR if "outage" in types else MINOR


# label kept <= 10 chars so it fits the 128px panel width
SERVICES = [
    ("Vercel",  "https://www.vercel-status.com/api/v2/status.json",     _statuspage),
    ("Cloudflr", "https://www.cloudflarestatus.com/api/v2/status.json", _statuspage),
    ("Slack",   "https://status.slack.com/api/v2.0.0/current",          _slack),
    ("Figma",   "https://status.figma.com/api/v2/status.json",          _statuspage),
    ("Claude",  "https://status.anthropic.com/api/v2/status.json",      _statuspage),
    ("GitHub",  "https://www.githubstatus.com/api/v2/status.json",      _statuspage),
]


def _one(entry):
    name, url, parser = entry
    try:
        return name, parser(url)
    except Exception as e:
        # A display must never crash on a flaky network, but silent failure hid a
        # real SSL misconfiguration during development - so surface it on request.
        if DEBUG:
            print(f"{name}: {type(e).__name__}: {e}", file=sys.stderr)
        return name, UNKNOWN


def poll(services=None):
    """[(name, level)] in declaration order. Never raises."""
    services = services or SERVICES
    with ThreadPoolExecutor(max_workers=len(services)) as ex:
        return list(ex.map(_one, services))


def worst(results):
    return max((lvl for _, lvl in results), key=lambda l: _RANK[l], default=UNKNOWN)


if __name__ == "__main__":
    import time
    t = time.time()
    res = poll()
    for name, lvl in res:
        print(f"  {name:<10} {lvl}")
    print(f"\nworst: {worst(res)}   ({time.time()-t:.2f}s for {len(res)} services)")
