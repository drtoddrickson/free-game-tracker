# RSS Free Game Tracker Roadmap
Version: 2026-03-28  
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

## ACTIVE

### R-001) Feed structure evolution
Status: ACTIVE  
Scope:
- Add `full_games.xml`
- Keep `master.xml`
- Keep `loot.xml`

---

### R-002) Manual state management workflow
Status: ACTIVE  
Scope:
- Easier way to update `state.json`
- Support:
  - CLAIMED
  - IGNORED
  - FORCE_EXPIRED

---

### R-003) Owned games YAML
Status: ACTIVE  
Scope:
- File-based owned game inventory
- YAML structure aligned with current system

---

## BACKLOG

### R-004) Owned-aware DLC targeting
Status: BACKLOG  
- Use owned data to filter/prioritize loot

### R-005) Platform inference improvements
Status: BACKLOG  

### R-006) Store detection expansion
Status: BACKLOG  

### R-007) Dedupe improvements
Status: BACKLOG  

### R-008) Source reliability scoring
Status: BACKLOG  

### R-009) Email digest
Status: BACKLOG  

### R-010) User-facing state controls (Discord/UI)
Status: BACKLOG  

---

## EXPERIMENTAL

### R-011) Multi-deal extraction from aggregator articles
Status: EXPERIMENTAL  

### R-012) Alienware Arena integration
Status: EXPERIMENTAL  

### R-013) Performance / efficiency tuning
Status: EXPERIMENTAL  

---

## PARKING LOT

### Expiration enhancements
- Broader date parsing
- Expiring-soon prioritization
- Urgency routing

### Future personalization
- Platform-specific feeds
- SQLite migration (if needed)
- Advanced routing controls

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
