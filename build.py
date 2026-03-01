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

WATCH_GAMES = [
    # your current set (kept)
    "fortnite",
    "fall guys",
    "rocket league",
    "disney dreamlight valley",
    "pokemon scarlet",
    "pokemon violet",
    "pokemon sword",
    "pokemon brilliant diamond",
    "pokemon shining pearl",
    "pokemon legends arceus",
    "minecraft",  # includes Minecraft (Switch) and Minecraft Legends keywords

    # new PS5 list (excluding ESO, and excluding Apex for now)
    "star wars battlefront ii",
    "hot wheels unleashed",
    "hot wheels unleashed 2",
    "harry potter: quidditch champions",
    "lego star wars: the skywalker saga",
    "minecraft legends",
    "lego 2k drive",
    "farming simulator 22",
    "jurassic world evolution 2",
    "diablo iv",
    "sackboy: a big adventure",
    "destiny 2",
    "hogwarts legacy",
    "the sims 4",
    "injustice 2",
]

FREE_TRIGGERS = [
    "free", "free-to-claim", "claim", "claimable",
    "drop", "drops", "reward", "cosmetic",
    "dlc", "bundle", "pack",
    "code", "redeem",
    "limited time", "expires", "ends",
    "giveaway",
]


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
    """
    Build a rolling window feed:
    - We still remember everything in state.json (so we can later suppress repeats / claimed / ignored).
    - But we always OUTPUT the most recent N items so the feed is never empty.
    """
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

            tags_upper = {t.upper() for t in tags}
            if "AGG" in tags_upper:
                summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
                combined = f"{title}\n{summary}".lower()

                if not any(g in combined for g in WATCH_GAMES):
                    continue
                if not any(k in combined for k in FREE_TRIGGERS):
                    continue

            sid = stable_id(src_name, title, link)
            published = entry_datetime(e)

            # Record it in state the first time we see it
            if sid not in items_state:
                items_state[sid] = {
                    "id": sid,
                    "source": src_name,
                    "title": title,
                    "link": link,
                    "first_seen": now.isoformat(),
                }

            # ALWAYS include it in the output feed (rolling window behavior)
            out.append(
                {
                    "id": sid,
                    "published": published,
                    "title": format_title(platforms, item_type, tags, title),
                    "link": link,
                    "description": f"{title}\n\nSource: {src_name}\nID: {sid}",
                }
            )
    
    # Sort once (newest first)
    out.sort(key=lambda x: x["published"], reverse=True)

    # Keep only the most recent N items so the feed stays readable
    N = 25
    return out[:N]


def render_rss(items: List[Dict[str, Any]], site_url: str) -> str:
    now = datetime.now(tz=timezone.utc
    ttl_time = now + timedetla(minutes=20)

    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<rss version="2.0">')
    parts.append("<channel>")
    parts.append("<title>Free Game Tracker - Master Feed</title>")
    parts.append(f"<link>{site_url}</link>")
    parts.append("<description>Free games + free DLC/cosmetics/drops tracker</description>")
    parts.append(f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>")
    parts.append(f"<generator>build-{int(now.timestamp())}</generator>")
    parts.append(f"<ttl>{int(ttl_time.timestamp())}</ttl>")

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

    print(f"Wrote {OUT_PATH} with {len(items)} items (rolling window).")


if __name__ == "__main__":
    main()
