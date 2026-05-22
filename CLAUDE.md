# Pokemon Sleep Recipe Map — Web App Dev Guide | CLAUDE.md

> **This file describes the web app.** For the Discord A/B-route analysis writeup (寶睡料理隊島嶼策略分析), see `ISLAND-STRATEGY.md`.

---

## 0. What this project is

A **single-page web app** that visualizes Pokémon Sleep recipe ↔ ingredient relationships for the Discord寶睡 community. Target audience: players deciding which ingredients to chase next.

- **Live URL:** GitHub Pages (`Georgechengtai/pokemon-sleep-recipe-map`)
- **Author:** Wallace
- **Deliverable:** `index.html` — a self-contained HTML file that fetches `data.json` and renders 4 tabs.

---

## 1. Tech stack & files

| File | Purpose |
|------|---------|
| `index.html` | **Everything.** HTML + CSS + JS embedded; no build step, no bundler. |
| `data.json` | Source of truth for ingredients (19) + recipes (80). Generated from `Pokemon Sleep Recipe.xlsx`. |
| `scripts/visual_check.py` | Pre-commit screenshot job (Playwright). Must pass before any commit touching `index.html`. |
| `scripts/build_data.py` | Excel → `data.json` conversion (only re-run when game data changes). |
| `screenshots/latest/` | Latest visual_check output. Auto-overwritten. |
| `ISLAND-STRATEGY.md` | Discord A/B-route writeup project (separate from this web app). |

**Constraints:**
- **No build step.** Edits go directly into `index.html`. Reload to see changes.
- **No external runtime deps** beyond what's in the CDN-free file.
- **GitHub Pages auto-deploys** on push to `main`. Build duration ~30s–5min depending on cache.

---

## 2. Tab architecture

The app has 4 tabs sharing one global state object `S` (in-memory, persisted to URL hash).

### Tab 1 — 料理瀏覽 (Browser) — manual mode
- Recipe grid + global controls (tier filter, owned chip strip).
- Single-recipe focus; user picks ings via the owned-strip popover.
- **Convention:** in-game ID ordering, hide (not dim) excluded recipes.

### Tab 2 — 統計 (Stats)
- Stats table + bipartite arc graph (`renderArcGraph`).
- Type filter (curry / salad / dessert), order by ID / occurrence.
- Sub-tabs: table view / matrix view.

### Tab 3 — 探索 (Explore) — 演算法 mode
**Tab 3 is one logic at three complexity levels** sharing state, no duplicate algorithms:
- **Map** (`renderRadialGraph`): radial bipartite SVG — inner ring of 19 ings, 3 outer-ring sectors of recipes (咖哩 / 沙拉 / 點心). Hover ing → highlights cookable recipes.
- **Recommender** (`buildRecommender`): 4 player-intent modes — 多解料理 / 衝高分 / 補弱系 / 離完成最近. Each mode renders custom anchor cards, not a 10-recipe dump.
- **Path Planner** (`buildPlanner`): simulates the directional sequence of ings to add from current owned → target畢業 recipes. Per-step shows what unlocks.

The three panels are visual zoom levels of the **same** recipe ↔ ing system; they must not embed independent algorithms.

### Tab 4 — 動畫 (Animation) — placeholder
Future: export ing-order from Browser or Planner, animate the cookable-recipe expansion as each ing is added.

---

## 3. Key functions (where to start when editing)

| Function | Lines (approx) | What it does |
|---|---|---|
| `loadData()` / `init()` | top of `<script>` | Fetch `data.json`, build all tabs, restore hash. |
| `renderRadialGraph(svg)` | Tab 3 Map | Adaptive radial layout. Invariants: `r1Floor`, `ringGap`, `labelGap`. |
| `renderArcGraph(svg)` | Tab 2 | Bipartite arc graph. Writes to `#map-state-summary-tab2` only. |
| `buildRecommender()` | Tab 3 right-top | 4-mode picker → per-mode card layout. |
| `buildPlanner()` | Tab 3 right-bottom | Greedy / lookahead ordered補食材 path. |
| `ghostPreviewIng(idx)` / `clearGhostPreview()` | shared | Map preview on hover. Used by Recommender + Planner. |
| `highlightIngOnGraph(idx)` | shared | Persistent highlight on Map. |
| `toggleOwned(idx)` | shared | Add/remove ing from `S.owned`; triggers `refreshAll()`. |
| `saveHash()` / `loadHash()` | persistence | URL fragment state round-trip. |

**Global state:** `const S = { owned, ownedOrder, excluded, minTier, tab, ... }`. Mutate via the toggle/setter helpers — never reach into `S` directly from a render function.

---

## 4. Dev workflow

### Before any commit touching `index.html`

```bash
python3 scripts/visual_check.py index.html
```

This captures 5 screenshots (desktop_wide, desktop_narrow, tablet, mobile, panel_top) and writes `screenshots/latest/`. **A pre-commit hook blocks committing `index.html` if the screenshots are older than the file.**

### Visual QA after a change

Use **Chrome MCP first** (`mcp__Claude_in_Chrome__*`). Per the memory note, Playwright is fallback only. Steps:
1. `tabs_context_mcp` → get tabId
2. `navigate` to `http://localhost:8765/index.html#owned=...&tab=...`
3. `computer screenshot` and/or `javascript_tool` for DOM inspection
4. For overlap checks, run the inline detector (counts bbox intersections of `image.g-ing-img`, `image.g-rec-icon`, `text.g-type-label`, etc.)

Start a local server if not running: `python3 -m http.server 8765`.

### Stress states to check before declaring a Tab 3 change done

Sweep across these `S.owned` cardinalities **with each combination of** `hideOwn` / `hideSup` / `showIngLabels` toggles:
- 0 owned, 3 owned, 9 owned (起跑), 12 owned (咖啡畢業), 13 owned (酪梨畢業), 15, 19 (全收集)

Expected: **0 overlaps** for all `image-image`, `image-text`, `text-text` pairs inside the radial SVG. The Recommender + Planner panels must never crush each other below ~180px.

### Commit + deploy

```bash
git add index.html ...
git commit -m "..."
git push  # auto-deploys to GH Pages in 30s–5min
```

Never commit `.claude/settings.local.json` (it's in the working tree but gitignored from intent — drop with `git restore --staged`).

---

## 5. Project conventions (from past feedback memos)

These come from `~/.claude/projects/-Users-yingtaicheng-Claude-Cowork-Pokemon-Sleep/memory/` and have been re-litigated more than once — respect them.

| Rule | Why |
|---|---|
| **In-game ID ordering** for ingredient lists | Matches what players see in-game; familiar mental model. |
| **Hide, don't dim** excluded recipes | Dimming creates visual noise; players asked for clean removal. |
| **No inter-tab dependency** | Shared state edits must be per-tab or global — never "Tab 1 only" affecting Tab 2/3. |
| **One logic at three levels** (Tab 3) | Map / Recommender / Planner must share algorithms, not re-implement. |
| **Verify before asking** | Use Chrome MCP to inspect bug hypotheses before bouncing back to Wallace. Propose UX decisions; ask only on genuine ambiguity. |
| **Align before coding on large redesigns** | For multi-panel / architecture changes: paraphrase the goal, ask once, then code. |
| **Claude does the overlap sweep, not Wallace** | If Wallace has to count overlaps in a screenshot, the QA pass failed. |

---

## 6. Domain glossary

- **食材手 (N)** — count of player's accumulated ingredient-specialist Pokémon (the unit of progression in this project; see `ISLAND-STRATEGY.md` §1.3 for thresholds).
- **畢業** — having 3 system-tier recipes (curry / salad / dessert) stably cookable. See `ISLAND-STRATEGY.md` §1.4.
- **+48% / +61% / +78% tier** — recipe upgrade stages from the `tier_bonus` field. +78% is the current max.
- **Sector** — one of the 3 outer-ring arcs on the Tab 3 radial graph (curry / salad / dessert).
- **Ghost preview** — semi-transparent overlay on Map when user hovers a Recommender card or Planner step.
- **Owned strip** — the chip strip near the header showing currently-owned ingredients in user-defined order.

---

## 7. Known open items (May 2026)

- **Path Planner v2** — in progress; needs "intermediate" semantics clarified before finishing. Current draft has tier-checkbox UI but `buildPlanner` not yet rewritten — page is broken until resolved or reverted.
- **Tab 4 (Animation)** — placeholder; not yet built.
- **Tab 3 click → focus 2D ring view** — deferred.

---

**Last updated:** 2026-05-22
**Maintained by:** Claude + Wallace
