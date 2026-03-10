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

import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import feedparser
import yaml

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources.yaml"
STATE_PATH = ROOT / "state.json"
OUT_DIR = ROOT / "docs"
OUT_PATH = OUT_DIR / "master.xml"
OUT_LOOT_PATH = OUT_DIR / "loot.xml"

ALLOWED_PLATFORMS = set(SUPPORTED_PLATFORM_MARKERS.keys())
ALLOWED_TYPES = {"GAME", "DLC", "EVENT", "SEASON", "NEWS"}


SUPPORTED_PLATFORM_MARKERS = {
    "PC": [
        r"\bsteam\b",
        r"\bepic\b",
        r"\bepic games\b",
        r"\bgog\b",
        r"\bitch\.io\b",
        r"\bhumble\b",
        r"\bprime gaming\b",
        r"\bwindows\b",
        r"\bpc\b",
    ],
    "PS5": [
        r"\bps5\b",
        r"\bplaystation\b",
        r"\bpsn\b",
        r"\bps4\b",
    ],
    "SWITCH": [
        r"\bnintendo switch\b",
        r"\bswitch\b",
        r"\bnintendo\b",
    ],
}

EXCLUDED_PLATFORM_MARKERS = {
    "XBOX": [
        r"\bxbox\b",
        r"\bxbox one\b",
        r"\bxbox series\b",
        r"\bmicrosoft store\b",
    ],
    "MOBILE": [
        r"\bandroid\b",
        r"\bios\b",
        r"\biphone\b",
        r"\bipad\b",
        r"\bmobile\b",
        r"\bgoogle play\b",
        r"\bapp store\b",
    ],
}

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

CROSSPLATFORM_GAMES = [
    "fortnite",
    "rocket league",
    "fall guys",
]

FREE_TRIGGERS = [
    # Strong “free” language
    "free",
    "free-to-claim",
    "free to claim",
    "claim free",
    "claimable",
    "no cost",
    "at no cost",

    # Redeem/code language (keep but require “redeem” or “free” via rule below)
    "redeem",
    "redemption",
    "mystery gift",

    # Time sensitivity
    "limited time",
    "ends",
    "ending",
    "expires",
    "expiring",
    "last chance",

    # Content type signals
    "free dlc",
    "free cosmetic",
    "free skin",
    "free pack",
    "free bundle",
]

DEAL_SPAM_BLOCKLIST = [
    # price drop language
    "drops to $",
    "dropped to $",
    "price drop",
    "lowest price",
    "now $",
    "only $",

    # generic deal spam
    "deal",
    "deals",
    "best deal",
    "save ",
    "save up to",
    "discount",
    "sale",
    "% off",
    "off ",
    "coupon",

    # hardware spam
    "monitor",
    "tv",
    "keyboard",
    "mouse",
    "controller",
    "headset",
    "laptop",
    "ssd",
    "graphics card",
    "gpu",
]

GAMERPOWER_ALL_SOURCE_NAMES = {
    "GamerPower - All (Giveaways)",
}

GAMERPOWER_SUPPRESS_MARKERS = [
    "beta",
    "playtest",
    "play test",
    "demo",
    "trial",
]

GAMERPOWER_LOOT_MARKERS = [
    "dlc",
    "loot",
    "drop",
    "drops",
    "skin",
    "skins",
    "cosmetic",
    "cosmetics",
    "emote",
    "spray",
    "wrap",
    "starter pack",
    "in-game",
    "in game",
    "bonus content",
    "booster",
]


def load_sources() -> List[Dict[str, Any]]:
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])


def xml_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


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


def normalize_title_for_match(title: str) -> str:
    t = (title or "").lower().strip()

    # Remove bracketed prefixes your own feed may add later if reused
    t = re.sub(r"\[[^\]]+\]\s*", "", t)

    # Normalize common separators/punctuation
    t = t.replace("–", "-").replace("—", "-").replace(":", " ")
    t = re.sub(r"[^a-z0-9\s\-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    # Remove noisy offer words that vary by source
    noise = {
        "free", "claim", "claimed", "redeem", "redeemable", "giveaway",
        "loot", "drop", "drops", "dlc", "bonus", "pack", "bundle",
        "trial", "demo", "exclusive", "limited", "offer"
    }
    words = [w for w in t.split() if w not in noise]
    return " ".join(words).strip()


def canonicalize_link(link: str) -> str:
    """
    Normalize links so tracking params don't create fake duplicates.
    Keep host/path and sorted non-tracking query params.
    """
    if not link:
        return ""

    p = urlparse(link.strip())
    host = (p.netloc or "").lower()
    path = (p.path or "").rstrip("/")

    filtered_q = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        kl = k.lower()
        if kl.startswith("utm_"):
            continue
        if kl in {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}:
            continue
        filtered_q.append((k, v))

    filtered_q.sort()
    query = urlencode(filtered_q, doseq=True)

    return urlunparse((p.scheme.lower(), host, path, "", query, ""))


def canonical_offer_key(title: str, link: str, item_type: str) -> str:
    """
    Cross-source dedupe key.
    Prefer title-based identity so the same offer from different article URLs
    can still collapse into one item.
    """
    norm_title = normalize_title_for_match(title)
    norm_link = canonicalize_link(link)
    item_type_norm = item_type.strip().upper()

    # Primary key: title + type only
    # This is intentionally aggressive so duplicate aggregator/article URLs collapse.
    if norm_title:
        raw = f"{item_type_norm}||{norm_title}".encode("utf-8")
    else:
        # Fallback only if title normalization somehow empties out
        raw = f"{item_type_norm}||{norm_link}".encode("utf-8")

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


def has_tag(tags: List[str], target: str) -> bool:
    return any(t.strip().upper() == target.upper() for t in tags)


def format_title(platforms: List[str], item_type: str, tags: List[str], title: str) -> str:
    parts = []

    for p in platforms:
        parts.append(f"[{p}]")

    # Prefer specific display tags over generic type labels
    if item_type == "GAME" and has_tag(tags, "FULL-GAME"):
        pass
    elif item_type == "DLC" and has_tag(tags, "LOOT-DROP"):
        pass
    elif item_type:
        parts.append(f"[{item_type}]")

    for t in tags:
        parts.append(f"[{t}]")

    parts.append(title)
    return " ".join(parts)


def add_content_tags(item_type: str, title: str, item_tags: List[str]) -> List[str]:
    """
    Add routing tags without changing core item types.
    - GAME -> FULL-GAME
    - DLC  -> LOOT-DROP
    """
    out = list(item_tags)

    if item_type == "GAME" and not has_tag(out, "FULL-GAME"):
        out.append("FULL-GAME")

    if item_type == "DLC" and not has_tag(out, "LOOT-DROP"):
        out.append("LOOT-DROP")

    return out


def is_gamerpower_all_source(src_name: str) -> bool:
    return src_name.strip() in GAMERPOWER_ALL_SOURCE_NAMES


def should_suppress_gamerpower_title(title: str) -> bool:
    t = (title or "").lower()
    return any(marker in t for marker in GAMERPOWER_SUPPRESS_MARKERS)


def classify_gamerpower_item_type(title: str) -> str:
    """
    GamerPower - All (Giveaways) is mixed-content input.
    Deterministic rule:
    - obvious loot/DLC markers => DLC
    - otherwise => GAME
    """
    t = (title or "").lower()

    if any(marker in t for marker in GAMERPOWER_LOOT_MARKERS):
        return "DLC"

    return "GAME"


def infer_platforms(title: str, src_name: str, default_platforms: List[str]) -> List[str]:
    """
    Infer platform from title text using word-boundary matching.

    Returns:
        [] if explicitly unsupported platform detected
        supported platform list if detected
        default_platforms if nothing detected
    """

    t = (title or "").lower()

    # Detect excluded platforms first
    for markers in EXCLUDED_PLATFORM_MARKERS.values():
        for pattern in markers:
            if re.search(pattern, t):
                return []

    # Detect supported platforms
    for platform, markers in SUPPORTED_PLATFORM_MARKERS.items():
        for pattern in markers:
            if re.search(pattern, t):
                return [platform]

    return default_platforms


def is_crossplatform_item(title: str) -> bool:
    """
    Conservative rule:
    - Only tag as CROSS-PLATFORM if the item is explicitly for one of our known cross-account games.
    - Source doesn't matter; we infer from title.
    """
    t = (title or "").lower()
    return any(g in t for g in CROSSPLATFORM_GAMES)
    

def entry_datetime(entry: Any) -> datetime:
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
    if getattr(entry, "updated_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


def platform_specificity_score(platforms: List[str]) -> int:
    """
    Higher score = better / more specific routing.
    Prefer a single clear platform over broad defaults.
    """
    p = normalize_platforms(platforms)

    if not p:
        return 0
    if len(p) == 1:
        return 100
    if len(p) == 2:
        return 50
    return 10


def build_items(sources: List[Dict[str, Any]], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build a rolling window feed:
    - We still remember everything in state.json (so we can later suppress repeats / claimed / ignored).
    - But we always OUTPUT the most recent N items so the feed is never empty.
    """
    items_state: Dict[str, Any] = state.setdefault("items", {})

    out: List[Dict[str, Any]] = []
    now = datetime.now(tz=timezone.utc)
    offer_map: Dict[str, Dict[str, Any]] = {}

    for src in sources:
        src_name = src["name"]
        url = src["url"]

        default_platforms = normalize_platforms(src.get("default_platforms", []))
        default_item_type = normalize_type(src.get("default_type", "NEWS"))
        tags = src.get("default_tags", [])

        feed = feedparser.parse(url)

        for e in feed.entries[:50]:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            if not title or not link:
                continue

            platforms = infer_platforms(title, src_name, default_platforms)
            # Drop items for platforms we do not track yet
            if not any(p in ALLOWED_PLATFORMS for p in platforms):
                continue
            
            resolved_item_type = default_item_type
            tags_upper = {t.upper() for t in tags}

            if is_gamerpower_all_source(src_name):
                if should_suppress_gamerpower_title(title):
                    continue

                resolved_item_type = classify_gamerpower_item_type(title)

                matched_games = []
                matched_triggers = []

            elif "AGG" in tags_upper:
                title_lc = title.lower()

                # Block obvious deal spam early
                if any(b in title_lc for b in DEAL_SPAM_BLOCKLIST):
                    continue

                matched_games = [g for g in WATCH_GAMES if g in title_lc]
                matched_triggers = [k for k in FREE_TRIGGERS if k in title_lc]

                if not matched_games or not matched_triggers:
                    continue

                # Guardrail: "code" mentions are noisy unless explicitly free/redeem
                if "code" in title_lc and ("free" not in title_lc and "redeem" not in title_lc):
                    continue
            else:
                matched_games = []
                matched_triggers = []

            sid = stable_id(src_name, title, link)
            published = entry_datetime(e)
            offer_key = canonical_offer_key(title, link, resolved_item_type)

            # Record it in state the first time we see it
            if sid not in items_state:
                items_state[sid] = {
                    "id": sid,
                    "source": src_name,
                    "title": title,
                    "link": link,
                    "first_seen": now.isoformat(),
                }

            # Build per-item tags (copy defaults)
            item_tags = list(tags)

            # Add content-routing tags
            item_tags = add_content_tags(resolved_item_type, title, item_tags)

            # Add CROSS-PLATFORM only when confidently detected
            if is_crossplatform_item(title):
                if not has_tag(item_tags, "CROSS-PLATFORM"):
                    item_tags.append("CROSS-PLATFORM")

            candidate = {
                "id": offer_key,
                "published": published,
                "platforms": platforms,
                "title": format_title(platforms, resolved_item_type, item_tags, title),
                "link": link,
                "description": f"{title}\n\nSource: {src_name}\nState ID: {sid}\nOffer ID: {offer_key}",
            }

            existing = offer_map.get(offer_key)

            if existing is None:
                offer_map[offer_key] = candidate
            else:
                candidate_score = platform_specificity_score(candidate.get("platforms", []))
                existing_score = platform_specificity_score(existing.get("platforms", []))
            
                # First prefer better/more specific platform tagging
                if candidate_score > existing_score:
                    offer_map[offer_key] = candidate
            
                elif candidate_score == existing_score:
                    # Then prefer newer item
                    if candidate["published"] > existing["published"]:
                        offer_map[offer_key] = candidate
                    # If tied, prefer shorter rendered title
                    elif (
                        candidate["published"] == existing["published"]
                        and len(candidate["title"]) < len(existing["title"])
                    ):
                        offer_map[offer_key] = candidate
    
    out = list(offer_map.values())

    # Sort once (newest first)
    out.sort(key=lambda x: x["published"], reverse=True)

    # Keep only the most recent N items so the feed stays readable
    N = 25
    return out[:N]


def filter_items_by_tag(items: List[Dict[str, Any]], tag: str) -> List[Dict[str, Any]]:
    needle = f"[{tag.strip().upper()}]"
    return [it for it in items if needle in it.get("title", "")]


def render_rss(
    items: List[Dict[str, Any]],
    site_url: str,
    feed_title: str = "Free Game Tracker - Master Feed",
    feed_description: str = "Free games + free DLC/cosmetics/drops tracker",
) -> str:
    now = datetime.now(tz=timezone.utc)

    # NEW: make build date stable unless items change
    build_dt = max((it["published"] for it in items), default=now)

    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">')
    parts.append("<channel>")
    parts.append(f"<title>{xml_escape(feed_title)}</title>")
    parts.append(f"<link>{xml_escape(site_url)}</link>")
    parts.append(f"<description>{xml_escape(feed_description)}</description>")
    parts.append(f'<atom:link href="{xml_escape(site_url)}" rel="self" type="application/rss+xml" />')
    parts.append(f"<pubDate>{format_datetime(build_dt)}</pubDate>")
    parts.append("<ttl>15</ttl>")
    parts.append(f"<lastBuildDate>{format_datetime(now)}</lastBuildDate>")
    parts.append("<generator>free-game-tracker/build.py</generator>")
    
    for it in items:
        parts.append("<item>")
        parts.append(f"<title><![CDATA[{it['title']}]]></title>")
        parts.append(f"<link>{xml_escape(it['link'])}</link>")
        parts.append(f"<guid isPermaLink='false'>{xml_escape(it['id'])}</guid>")
        parts.append(f"<pubDate>{format_datetime(it['published'])}</pubDate>")
        parts.append(f"<description><![CDATA[{it['description']}]]></description>")
        parts.append("</item>")

    parts.append("</channel>")
    parts.append("</rss>")
    return "\n".join(parts)


def main() -> None:
    sources = load_sources()
    state = load_state()

    site_root = "https://drtoddrickson.github.io/free-game-tracker/"
    master_feed_url = site_root + "master.xml"
    loot_feed_url = site_root + "loot.xml"

    items = build_items(sources, state)
    loot_items = filter_items_by_tag(items, "LOOT-DROP")

    rss_xml = render_rss(
        items,
        master_feed_url,
        feed_title="Free Game Tracker - Master Feed",
        feed_description="Free games + free DLC/cosmetics/drops tracker",
    )
    
    loot_rss_xml = render_rss(
        loot_items,
        loot_feed_url,
        feed_title="Free Game Tracker - Loot Drops",
        feed_description="Free DLC, cosmetics, in-game loot, and drops",
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rss_xml, encoding="utf-8")
    OUT_LOOT_PATH.write_text(loot_rss_xml, encoding="utf-8")

    save_state(state)

    print(f"Wrote {OUT_PATH} with {len(items)} items (rolling window).")
    print(f"Wrote {OUT_LOOT_PATH} with {len(loot_items)} items.")


if __name__ == "__main__":
    main()
