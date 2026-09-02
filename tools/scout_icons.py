"""Finds the game's own art for the items the calculator talks about but cannot show.

This container cannot reach any warera host, so the search runs on an Actions
runner instead. It does three things and reports all of them, because the useful
answer is as often "that name does not exist" as it is a file:

  1. walks the live app's script bundles for asset URLs,
  2. probes the naming conventions the calculator already relies on,
  3. downloads whatever resolves, so the run itself is the delivery.

Read-only against every host it touches, and it asks for each file exactly once.
"""

import concurrent.futures as futures
import hashlib
import io
import os
import re
import sys
import urllib.error
import urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "icons"
UA = "warera-case1-collector icon scout (github actions; fan project)"
TIMEOUT = 20
MAX_BUNDLES = 40

# What we are missing. Names are guesses on purpose - the probe is how we find
# out which of them the game actually uses.
WANTED = [
    "case", "case1", "caseI", "case_1", "cases", "weaponcase", "weaponCase",
    "equipmentCase", "lootbox", "crate", "box",
    "scrap", "scraps", "scrapMetal", "scrap_metal", "junk",
    "steel", "iron", "metal", "ingot", "alloy",
]

BASES = [
    "https://warerastats.io/items/{}.png",
    "https://warerastats.io/items/{}.webp",
    "https://warera.wiki/{}.png",
    "https://warera.wiki/other/{}.png",
    "https://warera.wiki/items/{}.png",
    "https://media.warera.io/items/{}.png",
    "https://media.warera.io/items/{}.webp",
    "https://media.warera.io/images/{}.png",
    "https://media.warera.io/assets/{}.png",
]

# A code we know exists, so a whole base failing is distinguishable from a name
# failing. Without this a dead host reads identically to a bad guess.
CONTROL = "knife"

ASSET = re.compile(r'["\'\(](/?[\w./@-]*?[\w@-]+\.(?:png|webp|svg|jpe?g|avif))["\'\)]')
SCRIPT = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']')
INTEREST = re.compile(r"case|scrap|steel|iron|metal|crate|resource|material", re.I)


def get(url, cap=6_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read(cap)


def try_get(url):
    try:
        return get(url)
    except urllib.error.HTTPError as e:
        return e.code, "", b""
    except Exception as e:                                    # noqa: BLE001
        return 0, type(e).__name__, b""


def absolute(src, page):
    if src.startswith("http"):
        return src
    if src.startswith("//"):
        return "https:" + src
    root = page.rstrip("/")
    return root + src if src.startswith("/") else root + "/" + src


def walk_bundles(page):
    """Follow the app's own scripts and collect every asset path they mention."""
    print(f"\n## Bundle walk: {page}")
    code, ctype, body = try_get(page)
    print(f"  page {code} {ctype} {len(body)}B")
    if not body:
        return set()

    text = body.decode("utf-8", "replace")
    scripts = [absolute(s, page) for s in SCRIPT.findall(text)][:MAX_BUNDLES]
    print(f"  {len(scripts)} script tags")

    found = set(ASSET.findall(text))
    for src in scripts:
        c, _, b = try_get(src)
        hits = set(ASSET.findall(b.decode("utf-8", "replace"))) if b else set()
        found |= hits
        flag = " <-- interesting" if any(INTEREST.search(h) for h in hits) else ""
        print(f"  {c:>3} {len(b):>8}B {src.split('/')[-1][:52]:<54}{len(hits):>4} assets{flag}")

    hot = sorted(a for a in found if INTEREST.search(a))
    print(f"\n  {len(found)} distinct asset paths, {len(hot)} matching what we want:")
    for a in hot[:80]:
        print("   ", a)
    return {absolute(a, page) for a in hot}


def probe():
    """Ask each naming convention for each name, with a control per base."""
    print("\n## Name probe")
    jobs, live = [], {}
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        for base in BASES:
            ctl = pool.submit(try_get, base.format(CONTROL))
            for name in WANTED:
                jobs.append((base, name, pool.submit(try_get, base.format(name))))
            live[base] = ctl

        for base, ctl in live.items():
            code, ctype, body = ctl.result()
            state = "up" if code == 200 else f"control {code}"
            print(f"\n  {base}  [{state}]")
            if code != 200:
                print("    base does not serve the control file; misses below are not informative")
            for b, name, fut in jobs:
                if b != base:
                    continue
                c, t, data = fut.result()
                if c == 200 and data:
                    print(f"    {name:<16} {c} {len(data):>7}B {t}")
                    yield base.format(name), data


def save(url, data):
    name = url.rsplit("/", 1)[-1].split("?")[0]
    path = os.path.join(OUT, name)
    with open(path, "wb") as f:
        f.write(data)
    return path, hashlib.sha256(data).hexdigest()[:12], len(data)


def main():
    os.makedirs(OUT, exist_ok=True)
    kept = {}

    for url, data in probe():
        kept[url] = data

    for page in ("https://app.warera.io/", "https://warera.wiki/"):
        for url in walk_bundles(page):
            if url in kept:
                continue
            c, _, data = try_get(url)
            if c == 200 and data:
                kept[url] = data

    print("\n## Downloaded")
    if not kept:
        print("  nothing - every candidate name and every bundle path came back empty")
        return 0
    for url, data in sorted(kept.items()):
        path, digest, size = save(url, data)
        print(f"  {path:<40} {size:>8}B sha {digest}   {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
