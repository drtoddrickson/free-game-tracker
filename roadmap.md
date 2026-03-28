# RSS Free Game Tracker Roadmap
Version: 2026-03-28  
Status: Current source-of-truth roadmap for architecture, prioritization, and feature sequencing.

---

## Purpose
This roadmap controls the direction of:
- Build / Feature Development
- Debugging follow-up priorities
- Source / Feed Optimization decisions

Principles:
- Deterministic logic over fragile heuristics
- Stability before expansion
- Source-agnostic solutions where possible
- Minimal, composable changes
- Keep MonitoRSS compatibility
- Preserve clean, readable pipeline behavior

---

## Current System Snapshot
Infrastructure:
- GitHub Actions runs every 15 minutes
- `build.py` aggregates configured sources from `sources.yaml`
- `state.json` persists lifecycle and manual state
- GitHub Pages serves feeds from `/docs`
- MonitoRSS distributes RSS output to Discord

Current outputs:
- `master.xml`
- `loot.xml`

Completed foundations:
- State tracking expansion
- Filtering model refinement
- Source pruning / block logic updates
- Expiration tracking

---

## ACTIVE
These are the next intended implementation targets, in order.

### 1) Feed structure evolution
Priority: High

Scope:
- Add `full_games.xml`
- Keep `master.xml`
- Keep `loot.xml`

Intent:
- Clean split between full games and loot
- Reduce downstream filtering burden
- Improve future email digest structure

---

### 2) Manual state management workflow
Priority: High

Scope:
- Create a cleaner manual workflow for updating `state.json`
- Support easy setting of:
  - `CLAIMED`
  - `IGNORED`
  - `FORCE_EXPIRED`

Intent:
- Make current state features practical to use
- Avoid tedious direct editing
- Bridge toward future user-facing controls

---

### 3) Owned games YAML
Priority: High

Scope:
- Add a file-based owned library
- Keep storage simple and repo-friendly
- Prepare for owned-aware loot targeting later

Intent:
- Move watch/ownership data out of code and into data
- Improve maintainability and personalization
- Stay aligned with current YAML-based architecture

---

## BACKLOG
Important features that should likely be built after the active tier.

### 4) Owned-aware DLC targeting
- Use wanted/owned game data to filter or prioritize loot
- Keep full games broad, keep loot targeted

### 5) Platform inference improvements
- Reduce false positives
- Improve confidence across mixed-source titles

### 6) Store detection expansion
- Improve store/ecosystem tagging accuracy
- Support better routing and dedupe tie-breaking

### 7) Dedupe improvements
- Refine winner selection logic
- Balance platform specificity, store quality, and recency

### 8) Source reliability scoring
- Score sources based on quality / usefulness
- Use later for source selection and tie-breaking

### 9) Email digest
- Add digest-style delivery in addition to Discord
- Likely daily/summary-oriented rather than alert-first

### 10) User-facing state controls
- Discord-triggered or future UI-triggered updates
- Set `CLAIMED`, `IGNORED`, `FORCE_EXPIRED`, and later `OWNED`

---

## EXPERIMENTAL
Promising ideas that are worthwhile but should stay controlled and narrowly scoped.

### 11) Multi-deal extraction from aggregator articles
- Extract multiple items from a single roundup article
- Whitelisted domains only
- Deterministic parsers first, fallback-safe behavior only

### 12) Alienware Arena integration
- Synthetic source integration for giveaway pages
- Deterministic extraction only
- Treat as a new source class, not just another feed

### 13) Performance / efficiency tuning
- Reduce unnecessary recomputation
- Keep builds fast as feature set grows

---

## PARKING LOT
Useful ideas to revisit later, but not needed for current roadmap completion.

### Expiration-related enhancements
- Broader date parsing for more source formats
- Expiring-soon priority boosts
- Special urgency routing for expiring-soon items
- Email/Discord urgency tiers

### Future personalization / expansion ideas
- Platform-specific feeds
- More granular routing by store/platform/type
- Owned database migration to SQLite if interaction becomes heavier
- Claimed/ignored/owned workflows driven directly from Discord

---

## COMPLETED
Keep this section short and milestone-focused.

### Completed roadmap items
- State tracking expansion
- Filtering model refinement
- Source pruning + block logic
- Expiration tracking

---

## Update Rules
When updating this roadmap:
1. Change priorities intentionally
2. Keep ACTIVE short
3. Move finished items to COMPLETED
4. Move speculative ideas to EXPERIMENTAL or PARKING LOT
5. Bump the version date when meaningful roadmap changes occur

---

## Suggested Repository Placement
Recommended path in your GitHub repo:

`/roadmap.md`

Why:
- Easy to find at repo root
- Easy to reference in chats
- Easy to version in Git
- Keeps it parallel to other core control files like `sources.yaml`

Alternative if you want a docs-style structure later:
- `/docs/roadmap.md`

Current recommendation:
- Put it at the repo root as `roadmap.md`
