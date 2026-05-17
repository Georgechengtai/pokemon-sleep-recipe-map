#!/usr/bin/env python3
"""
fetch_icons.py — download Serebii sprites for all ingredients + recipes.

Saves to:
  assets/icons/ingredients/{key}.png   (19 files, key = name_en lower no-space)
  assets/icons/recipes/{name_en}.png   (80 files)

Idempotent: skips files that already exist.
Gentle on Serebii (100ms delay between requests).
Prints per-file status; failed downloads listed at end.
"""

import json
import urllib.request
import urllib.error
import ssl
import time
from pathlib import Path

# macOS Python ships without OS cert chain; Serebii images are public so verification adds no value here.
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

ROOT = Path(__file__).parent.parent
DATA = json.loads((ROOT / "data.json").read_text())

ING_DIR = ROOT / "assets" / "icons" / "ingredients"
REC_DIR = ROOT / "assets" / "icons" / "recipes"
ING_DIR.mkdir(parents=True, exist_ok=True)
REC_DIR.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (compatible; pokemon-sleep-recipe-map/1.0; +https://github.com/Georgechengtai/pokemon-sleep-recipe-map)"


def fetch(url: str, dest: Path) -> str:
    if dest.exists() and dest.stat().st_size > 0:
        return "cached"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as resp:
            content = resp.read()
            if len(content) < 100:
                return f"too_small ({len(content)}B)"
            dest.write_bytes(content)
            return f"ok ({len(content)}B)"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except Exception as e:
        return f"err {type(e).__name__}: {e}"


def main():
    ings = DATA["ingredients"]
    recs = DATA["recipes"]
    print(f"== Fetching {len(ings)} ingredients + {len(recs)} recipes ==\n")

    failed = []
    ok = cached = 0

    print("-- Ingredients --")
    for ing in ings:
        url = ing["img_serebii"]
        dest = ING_DIR / f"{ing['key']}.png"
        status = fetch(url, dest)
        if status.startswith("ok"):
            ok += 1
        elif status == "cached":
            cached += 1
        else:
            failed.append(("ing", ing["name"], url, status))
        print(f"  {ing['name']:12s} {ing['key']:22s} → {status}")
        time.sleep(0.1)

    print("\n-- Recipes --")
    for rec in recs:
        if not rec.get("name_en"):
            continue
        url = rec["img_serebii"]
        dest = REC_DIR / f"{rec['name_en']}.png"
        status = fetch(url, dest)
        if status.startswith("ok"):
            ok += 1
        elif status == "cached":
            cached += 1
        else:
            failed.append(("rec", rec["name"], url, status))
        print(f"  {rec['name']:24s} {rec['name_en']:35s} → {status}")
        time.sleep(0.1)

    print(f"\n=== Summary ===")
    print(f"  ok:     {ok}")
    print(f"  cached: {cached}")
    print(f"  failed: {len(failed)}")
    if failed:
        print("\nFailed:")
        for kind, name, url, status in failed:
            print(f"  [{kind}] {name}: {url}  →  {status}")


if __name__ == "__main__":
    main()
