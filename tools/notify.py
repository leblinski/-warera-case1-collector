#!/usr/bin/env python3
"""Say on Discord what the run just did, so a dark collector is noticed rather than found.

The collector went quiet for four hours this week and the only sign was the cache not
moving. Nothing watched it, because watching was a thing a person did by looking.

Reads the run's own output and posts a short line. The webhook is passed in the
environment and never printed: it is a bearer credential, so anyone holding the URL can
post to the channel, and a URL echoed into a log is a URL in the log forever.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREEN, AMBER, RED = 0x6BB8A8, 0xC89B3C, 0xC2703F


def read(path):
    try:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def summarise(outcome):
    """One embed. Red when the run did not finish, amber when it finished degraded."""
    cache = read("data/warera_case1_market.json") or {}
    flow = read("public/flow.json") or {}
    health = cache.get("health") or {}
    status = cache.get("status")
    failed = list(health.get("failed_categories") or []) + list(health.get("failed_commodities") or [])
    degraded = list(health.get("degraded_commodities") or [])

    if outcome != "success" or not cache:
        colour, title = RED, "Collector did not finish"
    elif status != "ok" or failed:
        colour, title = AMBER, "Collector finished degraded"
    else:
        colour, title = GREEN, "Collector ran"

    fields = []
    if cache.get("generated_at"):
        fields.append(("Generated", cache["generated_at"], True))
    if health:
        fields.append(("Categories", f"{health.get('categories_ok', '?')} of "
                                     f"{health.get('category_count', '?')}", True))
    if flow.get("fills"):
        pct = str(min(flow.get("percentiles") or [2]))
        whales = (flow.get("whale_accounts") or {}).get(pct) or {}
        fields.append(("Fills held", f"{flow['fills']:,}", True))
        if whales:
            fields.append((f"Whales (top {pct}%)",
                           f"{whales.get('whales', '?')} of {whales.get('qualified', '?'):,}", True))
    if failed:
        fields.append(("Failed", ", ".join(sorted(failed)[:12]), False))
    if degraded:
        fields.append(("Degraded", ", ".join(sorted(degraded)[:12]), False))

    return {"embeds": [{"title": title, "color": colour,
                        "fields": [{"name": n, "value": str(v), "inline": i} for n, v, i in fields]
                        or [{"name": "Detail", "value": "No cache was written.", "inline": False}]}]}


def main():
    hook = os.environ.get("DISCORD_WEBHOOK", "").strip()
    if not hook:
        print("No DISCORD_WEBHOOK set; nothing to say.")
        return 0
    outcome = os.environ.get("COLLECT_OUTCOME", "success")
    quiet = os.environ.get("DISCORD_ONLY_WHEN_WRONG", "").strip().lower() in ("1", "true", "yes")
    payload = summarise(outcome)
    if quiet and payload["embeds"][0]["color"] == GREEN:
        print("Run was clean and only-when-wrong is set; staying quiet.")
        return 0
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(hook, data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(f"Posted to Discord: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        # Never the URL: a webhook is a bearer credential and a log is forever.
        print(f"Discord refused the post: HTTP {exc.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"Could not reach Discord: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
