# RSS Free Game Tracker Roadmap
Version: 2026-04-04  
Status: Source-of-truth roadmap for architecture, prioritization, and feature sequencing.

---

## Purpose
Controls direction of:
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

Outputs:
- `master.xml`
- `loot.xml`

---

## Tech Stack

Core:
- Python 3.11
- `feedparser` (RSS ingestion)
- `PyYAML` (source config)

Infrastructure:
- GitHub Actions (15-minute scheduled runs)
- GitHub Pages (RSS hosting via `/docs`)

Data / State:
- YAML (`sources.yaml`) for source configuration
- JSON (`state.json`) for lifecycle + user state

Output:
- RSS (XML feeds)
  - `master.xml`
  - `loot.xml`

Distribution:
- MonitoRSS (Discord delivery)

Architecture:
- Deterministic pipeline
- File-based state
- No database currently
- No ML / no external APIs in core pipeline

---

## Planned / Future Stack

Delivery:
- Email digest system
  - SMTP (Gmail / custom domain) and/or
  - Resend / SendGrid

Interaction:
- Discord bot or webhook layer for `user_state` updates
  - `CLAIMED`
  - `IGNORED`
  - `FORCE_EXPIRED`
  - future: `OWNED`

Data / Storage (conditional):
- SQLite only if:
  - Discord interaction becomes real
  - querying becomes complex
  - file-based workflow stops being sufficient

Enhancements:
- Optional article fetching for richer parsing
- Synthetic source adapters (example: Alienware Arena)

Architecture direction:
- Stay lightweight unless clear value
- Transition from “feed generator” to “stateful tracking system” only if needed

---

## Accuracy Strategy
Preferred signal hierarchy for future accuracy improvements:
1. Structured feed fields (if available)
2. Source-specific parsing
3. Title heuristics
4. HTML scrape (last resort)

Notes:
- Use the strongest deterministic signal available
- Avoid scraping-first design
- Keep HTML fetching limited and controlled

---

## ACTIVE

### R-001) Feed structure evolution
Status: ACTIVE  
Scope:
- Add `full_games.xml`
- Keep `master.xml`
- Keep `loot.xml`

Intent:
- Clean split between full games and loot
- Reduce downstream filtering burden
- Improve future email digest structure

---

### R-002) Manual state management workflow
Status: ACTIVE  

Scope:
- Provide a clean CLI-based workflow for interacting with `state.json`
- Support setting:
  - `CLAIMED`
  - `IGNORED`
  - `FORCE_EXPIRED`
- Add discovery and management tools:
  - `--list` → show recent items (with state_id, title, status, user_state)
  - `--search <query>` → find items by title or state_id
  - `--reset <state_id>` → revert `user_state` back to `NONE`

Intent:
- Make state features practical and fast to use
- Eliminate need for manual JSON editing
- Enable safe experimentation (via reset)
- Improve usability of:
  - filtering (`IGNORED`)
  - lifecycle overrides (`FORCE_EXPIRED`)
  - tracking (`CLAIMED`)

Notes:
- Extend existing CLI pattern (`--ignore`, `--claim`, `--force-expire`)
- Keep deterministic, local-only workflow (no external dependencies)
- Acts as bridge toward future Discord/UI-based interaction

---

### R-003) Owned games YAML
Status: ACTIVE  
Scope:
- File-based owned game inventory
- YAML structure aligned with current system
- Normalize item titles before matching against owned/wanted lists
  - Strip punctuation, special characters
  - Normalize whitespace and casing
  - Remove common noise words (e.g., "free", "bundle", "giveaway", "dlc")
- Support optional platform-specific ownership metadata
  - Allow owned/wanted entries to specify one or more platforms
  - Use platform data to improve DLC / loot relevance matching
  - Keep platform optional so simple title-only ownership remains valid

Intent:
- Move watch/ownership data out of code and into data
- Improve maintainability and personalization
- Increase matching accuracy for platform-specific games, DLC, and cross-platform titles
- Keep storage simple and repo-friendly

Notes:
- Start with title-only matching as valid baseline behavior
- Treat platform as an optional refinement, not a required field
- Most useful for:
  - DLC / loot targeting
  - cross-platform titles
  - games owned on one ecosystem but not another

---

## BACKLOG

### R-004) Owned-aware DLC targeting
Status: BACKLOG  
Scope:
- Use owned / wanted game data to filter or prioritize loot
- Keep full games broad, keep loot targeted

---

### R-005) Platform inference improvements
Status: BACKLOG  
Scope:
- Reduce false positives
- Improve confidence across mixed-source titles
- Apply signal hierarchy:
  1. Structured feed fields
  2. Source-specific parsing
  3. Title heuristics
  4. HTML scrape (last resort)

---

### R-006) Store detection expansion
Status: BACKLOG  
Scope:
- Improve store / ecosystem tagging accuracy
- Support better routing and dedupe tie-breaking

---

### R-007) Dedupe improvements
Status: BACKLOG  
Scope:
- Refine winner selection logic
- Balance store priority, signal quality, and recency

---

### R-008) Source reliability scoring
Status: BACKLOG  
Scope:
- Score sources based on quality / usefulness
- Use later for tie-breaking and source evaluation

---

### R-009) Email digest
Status: BACKLOG  
Scope:
- Add digest-style delivery in addition to Discord
- Likely daily / summary-oriented rather than alert-first

---

### R-010) User-facing state controls (Discord/UI)
Status: BACKLOG  
Scope:
- Discord-triggered or future UI-triggered updates
- Set `CLAIMED`, `IGNORED`, `FORCE_EXPIRED`, and later `OWNED`

---

### R-018) Platform ambiguity handling
Status: BACKLOG  
Scope:
- Detect multi-platform / low-confidence items
- Strip platform tags or tag as `MULTI-PLATFORM`
- Add optional routing for uncertain items

Intent:
- Reduce noisy Discord routing
- Prevent misleading platform classification on weak signals

---

## EXPERIMENTAL

### R-011) Multi-deal extraction from aggregator articles
Status: EXPERIMENTAL  
Scope:
- Extract multiple items from a single roundup article
- Whitelisted domains only
- Deterministic parsers first
- Fallback-safe behavior only

Notes:
- Use accuracy hierarchy
- Do not become a general scraping system

---

### R-012) Alienware Arena integration
Status: EXPERIMENTAL  
Scope:
- Synthetic source integration for giveaway pages
- Deterministic extraction only
- Treat as a new source class, not just another feed

---

### R-013) Performance / efficiency tuning
Status: EXPERIMENTAL  
Scope:
- Reduce unnecessary recomputation
- Keep builds fast as feature set grows

---

## PARKING LOT

### Expiration enhancements
- Broader date parsing:
  - “available until”
  - “ends on”
  - “valid through”
- Prioritize items with known expiration
- Surface “expiring soon” higher
- Expiring-soon prioritization logic
- Urgency routing (email / Discord tiers)

### Future personalization
- Platform-specific feeds
- SQLite migration (if needed)
- Advanced routing controls
- Owned / claimed / ignored workflows driven directly from Discord

### Source / parsing ideas
- Expand structured-field use where sources provide it
- Add narrowly scoped source-specific parsing before considering scraping
- Keep HTML scraping as a last resort only

---

## COMPLETED

### R-014) State tracking expansion
Status: COMPLETED (2026-03-27)

### R-015) Filtering model refinement
Status: COMPLETED (2026-03-27)

### R-016) Source pruning + block logic
Status: COMPLETED (2026-03-27)

### R-017) Expiration tracking
Status: COMPLETED (2026-03-27)

---

## CHANGE LOG

### 2026-03-27
- Completed: R-014 State tracking expansion
- Completed: R-015 Filtering model refinement
- Completed: R-016 Source pruning + block logic
- Completed: R-017 Expiration tracking
- Added: R-002 Manual state management workflow (ACTIVE)
- Added: R-003 Owned games YAML (ACTIVE)

### 2026-03-28
- Added: R-018 Platform ambiguity handling (BACKLOG)
- Added: Tech Stack section
- Added: Planned / Future Stack (including email system)
- Added: Accuracy hierarchy guidance
- Added: Expiration parsing and prioritization enhancements (PARKING LOT)

### 2026-04-04
- Standardized roadmap overwrite behavior
- Restored full-detail roadmap format
- Kept version date aligned to overwrite date
