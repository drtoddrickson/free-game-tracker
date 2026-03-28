#!/usr/bin/env python3
"""
Build a single master RSS feed at docs/master.xml from multiple RSS/Atom sources.

Step A behavior:
- Each item is only emitted once (prevents repeat notifications).
- State stored in state.json
- Titles are prefixed with tags like [PS5] [NEWS] ...
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

ALLOWED_PLATFORMS = set(SUPPORTED_PLATFORM_MARKERS.keys())
ALLOWED_TYPES = {"GAME", "DLC", "EVENT", "SEASON", "NEWS"}

STORE_TAG_MARKERS = {
    "STEAM": [
        "steam",
    ],
    "EPIC": [
        "epic games",
        "epic",
    ],
    "GOG": [
        "gog",
    ],
    "HUMBLE": [
        "humble",
        "humble games",
    ],
    "ITCH.IO": [
        "itch.io",
        "itch",
    ],
    "AMAZON": [
        "amazon games",
        "prime gaming",
        "amazon",
        "luna",
        "amazon luna",
    ],
    "PSN": [
        "playstation store",
        "playstation",
        "psn",
    ],
}

BLOCKED_STORE_MARKERS = {
    "INDIEGALA": [
        "indiegala",
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

LOOT_MARKERS = [
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
    " pack giveaway",
    " collection giveaway",
    " pack",
    " collection",
]


def is_lootscraper_game_source(src_name: str) -> bool:
    s = (src_name or "").strip().lower()
    return s.startswith("lootscraper -") and "in-game loot" not in s


def classify_lootlike_item_type(title: str, default_item_type: str) -> str:
    t = (title or "").lower()

    if any(marker in t for marker in LOOT_MARKERS):
        return "DLC"

    return default_item_type


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

    # Remove LootScraper-style leading boilerplate
    t = re.sub(
        r"^(steam|epic games|gog|humble|itch\.io|amazon games|prime gaming|playstation store)\s*\((game|games|dlc|loot|in-game loot)\)\s*-\s*",
        "",
        t,
    )

    # Remove GamerPower-style trailing store marker before giveaway words
    t = re.sub(
        r"\s*\((steam|epic games|gog|humble|itch\.io|amazon games|prime gaming|playstation|psn)\)\s*(giveaway)?\s*$",
        "",
        t,
    )

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

    # Treat GAME and DLC as the same dedupe family so source classification
    # differences do not create duplicate feed items.
    item_type_norm = item_type.strip().upper()
    key_type = "OFFER" if item_type_norm in {"GAME", "DLC"} else item_type_norm

    if norm_title:
        raw = f"{key_type}||{norm_title}".encode("utf-8")
    else:
        raw = f"{key_type}||{norm_link}".encode("utf-8")

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
    
    
def is_noise_title(title: str) -> bool:
    t = (title or "").lower()
    noise_markers = [
        "demo",
        "trial",
        "open beta",
        "closed beta",
        "beta test",
        "playtest",
        "test server",
        "public test server",
        "pts",
        "stress test",
        "server test",
        "alpha test",
    ]
    return any(m in t for m in noise_markers)


def has_blocked_platform(platforms: List[str]) -> bool:
    p = {x.strip().upper() for x in platforms}
    return "MOBILE" in p or "XBOX" in p


def should_keep_loot_item(title: str, src_name: str, tags: List[str]) -> bool:
    t = (title or "").lower()
    tags_upper = {x.strip().upper() for x in tags}

    # Keep high-signal loot ecosystems already intentionally tracked
    if "FORTNITE" in tags_upper:
        return True

    # Keep AGG loot only when it matches your existing signal model
    matched_games = [g for g in WATCH_GAMES if g in t]
    matched_triggers = [k for k in FREE_TRIGGERS if k in t]

    if matched_games and matched_triggers:
        if "code" in t and ("free" not in t and "redeem" not in t):
            return False
        return True

    return False


def is_gamerpower_all_source(src_name: str) -> bool:
    return src_name.strip() in GAMERPOWER_ALL_SOURCE_NAMES


def should_suppress_gamerpower_title(title: str) -> bool:
    t = (title or "").lower()
    return any(marker in t for marker in GAMERPOWER_SUPPRESS_MARKERS)


def detect_store_tags(title: str, src_name: str) -> List[str]:
    """
    Detect store/platform ecosystem tags from title and source name.
    Deterministic and additive only.
    """
    text = f"{src_name} {title}".lower()
    out: List[str] = []

    for store_tag, markers in STORE_TAG_MARKERS.items():
        if any(marker in text for marker in markers):
            out.append(store_tag)

    # Keep stable ordering
    order = {
        "STEAM": 0,
        "EPIC": 1,
        "GOG": 2,
        "HUMBLE": 3,
        "ITCH.IO": 4,
        "AMAZON": 5,
        "PSN": 6,
    }
    return sorted(set(out), key=lambda x: order.get(x, 99))
    
    
def is_blocked_store_item(title: str, src_name: str, link: str) -> bool:
    """
    Exclude stores we do not want from any source.
    Checks title, source name, and link deterministically.
    """
    text = f"{src_name} {title} {link}".lower()

    for markers in BLOCKED_STORE_MARKERS.values():
        if any(marker in text for marker in markers):
            return True

    return False


def infer_platforms(
    title: str,
    src_name: str,
    default_platforms: List[str],
    link: str = "",
    description: str = "",
) -> List[str]:
    """
    Infer platform from title/link/description text using word-boundary matching.

    Returns:
        [] if explicitly unsupported platform detected
        supported platform list if detected
        default_platforms if nothing detected
    """
    text = f"{title} {link} {description}".lower()

    # Detect excluded platforms first
    for markers in EXCLUDED_PLATFORM_MARKERS.values():
        for pattern in markers:
            if re.search(pattern, text):
                return []

    # Detect supported platforms
    for platform, markers in SUPPORTED_PLATFORM_MARKERS.items():
        for pattern in markers:
            if re.search(pattern, text):
                return [platform]

    return default_platforms
    
    
def get_item_status(items_state: Dict[str, Any], sid: str) -> str:
    return items_state.get(sid, {}).get("status", "ACTIVE")


def get_user_state(items_state: Dict[str, Any], sid: str) -> str:
    return items_state.get(sid, {}).get("user_state", "NONE")


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
    
    
def store_tag_score(tags: List[str]) -> int:
    """
    Higher score = better/more specific source identity for dedupe winner selection.
    Prefer direct store/platform tags over generic/untagged items.
    """
    preferred = {"PSN", "STEAM", "EPIC", "GOG", "AMAZON", "HUMBLE", "ITCH.IO"}
    return sum(1 for t in tags if t.strip().upper() in preferred)


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

        feed = feedparser.parse(
            url,
            agent="free-game-tracker/1.0 (+https://drtoddrickson.github.io/free-game-tracker/)",
            request_headers={
                "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        print(
            f"{src_name}: status={getattr(feed, 'status', 'n/a')} "
            f"bozo={getattr(feed, 'bozo', False)} entries={len(feed.entries)}"
        )

        for e in feed.entries[:50]:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            if not title or not link:
                continue
                
            # Exclude blocked stores globally
            if is_blocked_store_item(title, src_name, link):
                continue

            summary = getattr(e, "summary", "") or getattr(e, "description", "")

            platforms = infer_platforms(title, src_name, default_platforms, link, summary)

            # Drop items only when no allowed platform remains
            if not any(p in ALLOWED_PLATFORMS for p in platforms):
                continue

            # Explicit blocked-platform safeguard
            if has_blocked_platform(platforms):
                continue
            
            resolved_item_type = default_item_type
            tags_upper = {t.upper() for t in tags}

            if is_gamerpower_all_source(src_name):
                if should_suppress_gamerpower_title(title):
                    continue

                resolved_item_type = classify_lootlike_item_type(title, "GAME")

            elif is_lootscraper_game_source(src_name):
                resolved_item_type = classify_lootlike_item_type(title, default_item_type)

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
                    "offer_key": offer_key,
                    "first_seen": now.isoformat(),
                    "last_seen": now.isoformat(),
                    "status": "ACTIVE",      # ACTIVE | EXPIRED
                    "user_state": "NONE",    # NONE | CLAIMED | IGNORED
                }
            else:
                items_state[sid]["last_seen"] = now.isoformat()
                if items_state[sid].get("user_state") == "CLAIMED":
                    continue
                    
                items_state[sid]["status"] = "ACTIVE"
                # 🔹 Backfill missing fields for legacy entries
                items_state[sid].setdefault("user_state", "NONE")
                items_state[sid].setdefault("first_seen", now.isoformat())
                # 🔹 Refresh observed metadata (already in your code)
                items_state[sid]["title"] = title
                items_state[sid]["link"] = link
                items_state[sid]["source"] = src_name
                items_state[sid]["offer_key"] = offer_key

            # Build per-item tags (copy defaults)
            item_tags = list(tags)

            # Add content-routing tags
            item_tags = add_content_tags(resolved_item_type, title, item_tags)
            
            # Add store tags
            for store_tag in detect_store_tags(title, src_name):
                if not has_tag(item_tags, store_tag):
                    item_tags.append(store_tag)

            # Add CROSS-PLATFORM only when confidently detected
            if is_crossplatform_item(title):
                if not has_tag(item_tags, "CROSS-PLATFORM"):
                    item_tags.append("CROSS-PLATFORM")
            
            is_loot = has_tag(item_tags, "LOOT-DROP")

            # Global noise filter for all items
            if is_noise_title(title):
                continue

            # Preserve your existing AGG deal-spam suppression globally for noisy aggregators
            if "AGG" in tags_upper:
                title_lc = title.lower()
                if any(b in title_lc for b in DEAL_SPAM_BLOCKLIST):
                    continue

            # Filtering model refinement:
            # - Full games pass by default unless blocked elsewhere
            # - Loot stays strict
            if is_loot and not should_keep_loot_item(title, src_name, item_tags):
                continue
            
            system_status = get_item_status(items_state, sid)
            user_state = get_user_state(items_state, sid)
            
            if get_user_state(items_state, sid) == "IGNORED":
                continue

            candidate = {
                "id": offer_key,
                "published": published,
                "platforms": platforms,
                "tags": list(item_tags),
                "title": format_title(platforms, resolved_item_type, item_tags, title),
                "link": link,
                "description": (
                    f"{title}\n\n"
                    f"Source: {src_name}\n"
                    f"State ID: {sid}\n"
                    f"Offer ID: {offer_key}\n"
                    f"Status: {system_status}\n"
                    f"User State: {user_state}"
                ),
            }

            existing = offer_map.get(offer_key)

            if existing is None:
                offer_map[offer_key] = candidate
            else:
                candidate_platform_score = platform_specificity_score(candidate.get("platforms", []))
                existing_platform_score = platform_specificity_score(existing.get("platforms", []))

                candidate_store_score = store_tag_score(candidate.get("tags", []))
                existing_store_score = store_tag_score(existing.get("tags", []))

                # 1) Prefer better/more specific platform tagging
                if candidate_platform_score > existing_platform_score:
                    offer_map[offer_key] = candidate

                elif candidate_platform_score == existing_platform_score:
                    # 2) Prefer item with better store identity
                    if candidate_store_score > existing_store_score:
                        offer_map[offer_key] = candidate

                    elif candidate_store_score == existing_store_score:
                        # 3) Then prefer newer item
                        if candidate["published"] > existing["published"]:
                            offer_map[offer_key] = candidate
                        # 4) If still tied, prefer shorter rendered title
                        elif (
                            candidate["published"] == existing["published"]
                            and len(candidate["title"]) < len(existing["title"])
                        ):
                            offer_map[offer_key] = candidate
    
    out = list(offer_map.values())

    # Sort once (newest first)
    out.sort(key=lambda x: x["published"], reverse=True)

    # Keep only the most recent N items so the feed stays readable
    N = 50
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
