#!/usr/bin/env python3
"""
Build a single master RSS feed at docs/master.xml from multiple RSS/Atom sources.

Step A behavior:
- Each item is only emitted once (prevents repeat notifications).
- State stored in state.json
- Titles are prefixed with tags like [PS5] [NEWS] ...
- CLAIMED/IGNORED support will come later; for now we just do "seen once".
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Dict, List

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources.yaml"
STATE_PATH = ROOT / "state.json"
OUT_PATH = ROOT / "master.xml"

ALLOWED_PLATFORMS = {"PC", "PS5", "SWITCH"}
ALLOWED_TYPES = {"GAME", "DLC", "EVENT", "SEASON", "NEWS"}


def load_sources() -> List[Dict[str, Any]]:
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"items": {}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def stable_id(source_name: str, title: str, link: str) -> str:
    raw = f"{source_name}||{title.strip()}||{link.strip()}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def normalize_platforms(platforms: List[str]) -> List[str]:
    out = []
    for p in platforms:
        p2 = p.strip().upper()
        if p2 == "SWITCH":
            out.append("SWITCH")
        elif p2 in ALLOWED_PLATFORMS:
            out.append(p2)
    # Keep a consistent order
    order = {"PC": 0, "PS5": 1, "SWITCH": 2}
    return sorted(set(out), key=lambda x: order.get(x, 99))


def normalize_type(t: str) -> str:
    t2 = t.strip().upper()
    return t2 if t2 in ALLOWED_TYPES else "NEWS"


def format_title(platforms: List[str], item_type: str, tags: List[str], title: str) -> str:
    parts: List[str] = []
    for p in platforms:
        parts.append(f"[{p}]")
    parts.append(f"[{item_type}]")
    for tag in tags:
        tag2 = tag.strip().upper().replace(" ", "-")
        parts.append(f"[{tag2}]")
    parts.append(title.strip())
    return " ".join(parts)


def entry_datetime(entry: Any) -> datetime:
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
    if getattr(entry, "updated_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


def build_items(sources: List[Dict[str, Any]], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    items_state: Dict[str, Any] = state.setdefault("items", {})

    out: List[Dict[str, Any]] = []
    now = datetime.now(tz=timezone.utc)

    for src in sources:
        src_name = src["name"]
        url = src["url"]

        platforms = normalize_platforms(src.get("default_platforms", []))
        item_type = normalize_type(src.get("default_type", "NEWS"))
        tags = src.get("default_tags", [])

        feed = feedparser.parse(url)

        for e in feed.entries[:50]:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            if not title or not link:
                continue

            sid = stable_id(src_name, title, link)

            # Only emit once ever
            if sid in items_state:
                continue

            items_state[sid] = {
                "id": sid,
                "source": src_name,
                "title": title,
                "link": link,
                "first_seen": now.isoformat(),
            }

            published = entry_datetime(e)

            out.append(
                {
                    "id": sid,
                    "published": published,
                    "title": format_title(platforms, item_type, tags, title),
                    "link": link,
                    "description": f"{title}\n\nSource: {src_name}\nID: {sid}",
                }
            )

    out.sort(key=lambda x: x["published"], reverse=True)
    return out


def render_rss(items: List[Dict[str, Any]], site_url: str) -> str:
    now = datetime.now(tz=timezone.utc)

    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<rss version="2.0">')
    parts.append("<channel>")
    parts.append("<title>Free Game Tracker - Master Feed</title>")
    parts.append(f"<link>{site_url}</link>")
    parts.append("<description>Free games + free DLC/cosmetics/drops tracker</description>")
    parts.append(f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>")

    for it in items:
        parts.append("<item>")
        parts.append(f"<title><![CDATA[{it['title']}]]></title>")
        parts.append(f"<link>{it['link']}</link>")
        parts.append(f"<guid isPermaLink='false'>{it['id']}</guid>")
        parts.append(f"<pubDate>{format_datetime(it['published'])}</pubDate>")
        parts.append(f"<description><![CDATA[{it['description']}]]></description>")
        parts.append("</item>")

    parts.append("</channel>")
    parts.append("</rss>")
    return "\n".join(parts)


def main() -> None:
    sources = load_sources()
    state = load_state()

    site_url = "https://drtoddrickson.github.io/free-game-tracker/"

    items = build_items(sources, state)
    rss_xml = render_rss(items, site_url)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rss_xml, encoding="utf-8")

    save_state(state)

    print(f"Wrote {OUT_PATH} with {len(items)} NEW items.")


if __name__ == "__main__":
    main()
