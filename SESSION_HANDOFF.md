# Session Handoff — Path Planner Redesign

**Date:** 2026-05-24
**Status:** Python prototype is the active development artifact. `index.html` Path Planner is stale and must be replaced before launch.

---

## 0. What this project is

Single-page web app `index.html` visualises Pokémon Sleep recipe ↔ ingredient relationships for Discord玩家. Four tabs; the active work is **Tab 3 (Explore)**, which has three panels:

- **Map** — radial bipartite SVG (inner ring of 19 ings, 3 outer-ring sectors of recipes by type)
- **Recommender** — 4 mode chips suggesting next single best ing
- **Path Planner** — sequenced ordering of ings from current `S.owned` toward a chosen goal

Tab 3 is the one logic at three zoom levels — they share `S.owned`, no duplicated algorithms. The Path Planner has been rewritten multiple times this session because the algorithm/metric kept being wrong. **The current `index.html` planner is an old version (commits `63d2f27` + `6398d3a`)** that uses arbitrary hand-tuned weights and is to be discarded.

Web app conventions live in `CLAUDE.md` (this folder). The Discord-post project (寶睡料理隊島嶼策略分析) is in `ISLAND-STRATEGY.md` — *separate project*, only the recipe definitions and畢業 milestones cross over.

---

## 1. Files in play

| File | Purpose | State |
|---|---|---|
| `index.html` | The web app. Single file, no build. | **Path Planner is stale** (v2 from earlier commits). Recommender + Map fine. |
| `data.json` | 19 ings + 76 active recipes (+ 3 placeholders). Source of truth. | Stable, generated from Excel. |
| `scripts/path_planner_prototype.py` | **ACTIVE** Python prototype. The agreed algorithm lives here. | Working; some leftover code paths from earlier σ experiments. |
| `scripts/sigma_variants_comparison.py` | One-off: 4 σ formulations (sum/geo/completeness/minmax) side-by-side. | Kept for evidence; not part of main flow. |
| `scripts/value_added_variants.py` | One-off: 4 R aggregations (status/final/inv_step/linear) side-by-side. | Same. |
| `scripts/path_planner_prototype_output.txt` | Last run output of the prototype. | ~180 lines, all scenarios. |
| `scripts/PATH_PLANNER_PROTOTYPE_REPORT.md` | Earlier narrative writeup. | **Partly stale** — written before σ_sum→σ_focused revert. |
| `CLAUDE.md` | Web-app dev guide. | Up-to-date framework, but Path Planner section may now reference stale v2. |
| `ISLAND-STRATEGY.md` | Discord-post project (renamed from old Claude.md). | Untouched, separate project. |

Git: all on `main`, no branches. Latest relevant commits: `34f64b6` (σ_sum exploration, reverted), `a71f25a` (σ_focused + tier filter + Δσ reporting), `d921281` (earlier prototype + report).

---

## 2. Domain glossary

- **19 ingredients (`ings`)** with in-game IDs 0–18.
- **76 recipes**, each with:
  - `type_en`: one of `curry`, `salad`, `dessert`
  - `tier_bonus`: ∈ {0.16, 0.19, 0.20, 0.21, 0.25, 0.35, 0.48, 0.61, 0.78}
  - `score_final` = `score_base × (1 + tier_bonus)` (the game's published meal score)
  - `ings`: frozenset of ing indices (4 ings for +78% dishes, 3 for many lower-tier ones)
- **Tier distribution**: +16:1, +19:21, +20:4, +21:6, +25:14, **+35:10, +48:9, +61:6, +78:5**
- Only **5 dishes at +78%** total — the absolute final-goal pool.

Two canonical "goal sets" used in all testing:
- **Coffee 3** (all +61%): 覺醒力量濃湯 / 不服輸咖啡沙拉 / 土王閃電泡芙. 10 unique required ings.
- **Avocado 3** (all +78%): 茂盛焗烤酪梨 / 重踏酪梨醬脆片 / 採蜜巧克力格子鬆餅. 9 unique required ings.

---

## 3. The current algorithm (Python prototype)

### Data structures (`path_planner_prototype.py`)

```python
@dataclass(frozen=True)
class Recipe:
    name: str
    type_en: str          # 'curry' | 'salad' | 'dessert'
    tier_bonus: float
    score_final: int
    ings: frozenset[int]  # set of ing indices

@dataclass
class World:
    ingredients: list[str]              # name list, indexed
    name_to_idx: dict[str, int]
    recipes: list[Recipe]
    by_name: dict[str, Recipe]
    by_type: dict[str, list[Recipe]]    # type_en → recipes

def load_world(data_path) -> World     # reads data.json
```

### σ — agreed definition

```python
MIN_TIER = 0.35  # recipes with tier_bonus < 0.35 contribute 0 (will be UI toggle)

def sigma_focused(owned: frozenset[int], world: World, scope: frozenset[int],
                  min_tier: float = 0.35) -> int:
    """Max-per-type sigma, restricted to scope and tier filter.
    
    σ = max curry score + max salad score + max dessert score
    where each max is over recipes that are:
      - tier_bonus >= min_tier
      - r.ings ⊆ owned   (cookable now)
      - r.ings ⊆ scope   (within user's grinding commitment)
    """
```

`scope` is the union of (goal ings) ∪ (optional extras the user accepts to grind). Path = ordering of `(scope - start_owned)`.

### R aggregation — currently undecided but leaning R_inv_step

Two contenders, both parameter-free:

```python
def R_status(path) -> int:
    # = Σ σ_t over each step
    # MATHEMATICALLY EQUIVALENT to Σ Δσ_t × (n - t + 1)
    # BROKEN: monotonically rewards more extras (each padding step credits at peak σ)

def R_inv_step(path) -> float:
    # = Σ Δσ_t / t (1-indexed)
    # Penalizes late improvements; flat steps contribute 0
    # NATURALLY caps optimal-k around 3-8 extras, then declines
```

**Latest call** (end of session): R_inv_step is the better metric. Under R_status, "optimal k" is to include all 10 candidate extras (gives R=1,017,795 for Avocado padded with 10 flat-σ steps at peak — meaningless). Under R_inv_step, optimum is k=3 with R=13,567 and longer paths actively hurt.

### σ alternatives explored (most rejected)

```python
def sigma_free(owned, world)   # max-per-type across ALL 76 recipes (goal-blind) — REJECTED (silently swaps goal dishes)
def sigma_sum(owned, scope)    # sum of all in-scope cookable scores — REJECTED by user (too generous)
def sigma_geo(owned, scope)    # geomean of 3 type maxes — TOO HARSH (σ=0 until all 3 types non-zero)
def sigma_completeness(owned, scope)  # sigma_focused × (count_types_cooked / 3) — VIABLE alternative, encourages spatial balance, parameter-free
def sigma_minmax(owned, scope) # min of 3 type maxes — TOO HARSH
```

`σ_completeness` is the only viable alternative to `σ_focused`. Wallace expressed mild preference for it earlier ("balance slightly") but in latest exchange tilted toward `σ_focused` for not being too explore-heavy. **Decision not finalized.**

### Search algorithms

```python
def greedy_path(start, goals, world, *, scope, min_tier) -> list[int]:
    """K=1 beam = pick ing maximizing σ-gain at each step.
    Tie-break: by appears-in count, then by smaller ing-id."""

def beam_path(start, goals, world, *, beam=50, scope, min_tier, alpha=0.0) -> list[int]:
    """K-wide beam. Rank partial paths by R(prefix). Currently uses R_status
    internally for ranking — TO BE CHANGED to R_inv_step per latest agreement.
    Default beam=50; experiments showed K>50 doesn't improve."""

def two_opt_polish(start, path, world, ...) -> list[int]:
    """Swap adjacent pairs while R improves. Set is fixed, only order changes.
    Rarely improves over beam=50 result in practice."""

def scope_frontier(goals, world, max_extras=4, beam=50, alpha=0.0):
    """Brute-force: for each k in 0..max_extras, enumerate all C(|extras|, k)
    subsets, find best one under chosen R. Reports Pareto frontier.
    
    LATEST DECISION: max_extras should be unbounded (= len(candidate_extras)).
    Search cost is 52s for Avocado k=0..10 — acceptable.
    Currently still capped at 3 in main(); MUST BE RAISED."""
```

### Reporting

`report_path(...)` and `report_scenario(...)` print per-step breakdowns showing:
- step #, ing name, σ value, Δσ
- which type's max changed (e.g. `curry: ∅ → +35% 絕對睡眠奶油咖哩(9,010)`)
- "no max change" if Δσ=0

This transparency is essential. Users (Wallace) checks every σ jump against the listed recipe unlocks.

---

## 4. Design decisions and rationale

| Decision | Why |
|---|---|
| **σ_focused (max per type)** | User's intuition: "what's the best dish I can cook right now per meal type?" Adding a +48% recipe to a slot already maxed by +78% doesn't improve the kitchen, so it shouldn't count toward σ. |
| **Tier filter ≥ 0.35** | User said: "set a discount rate of <35% recipe to 100% such that it does not contribute to path at all". Real gameplay doesn't care about +19/+25 dishes; they're noise. Future: UI toggle. |
| **R_inv_step (Σ Δσ/t)** | R_status was structurally broken — rewards any path length increase because each padding step contributes peak σ. R_inv_step penalises late steps, so useless extras yield ~0 R. Validated: under R_inv_step, k=10 (all ings) gives R=12,750 < k=3 optimum at 13,567. |
| **Beam K=50** | Empirically sufficient. K=100, K=500 give same or worse R for same scope. Local optima are rare in this problem. |
| **Unbounded k-search** | User's instruction: search cost is acceptable, don't artificially cap. For Avocado, 2^10=1024 subsets × beam 50 = ~52s. Acceptable. Must be applied across all goals. |
| **Goals as 3 specific recipes, not "top 3 by type"** | User: "we basically need a top 1 recipe by type but that's top-energy recipe", with custom override. Three modes: smart-auto, pre-baked themes (咖啡/酪梨), custom 3-dish picker. |
| **No pre-selected intermediates** | Earlier algorithm tried to "pick intermediate dishes" separately. Wrong abstraction. Intermediates emerge from the path's scope — they're whatever dish becomes cookable as ings are added. User chooses the SCOPE (req ∪ extras), algorithm chooses the ORDER. |
| **Path is directional** | User emphasised this multiple times. Output is a numbered sequence (1 → 2 → 3 …) with arrows. Tie-breaking is explicit and deterministic. |

---

## 5. Algorithm taxonomy (clarified mid-session)

| Panel | Sees goals? | Decision horizon |
|---|---|---|
| **Recommender** | ❌ no (stateless greedy) | 1 step |
| **Planner Local** | ✅ yes, step-by-step | 1 step (K=1 greedy) |
| **Planner Global** | ✅ yes, holistic | full path (K=50 beam) |

User noted this also raises the question: **is Planner Local redundant with Recommender?** They're both single-step greedy. The only difference is Local respects the goal constraint (path must terminate with goal_ings owned). Pending: decide whether to drop Local or keep as a "lightweight" mode.

---

## 6. What `index.html`'s Path Planner currently does (stale)

The web app's current implementation (in commits before this session's prototype work):

- Goal source dropdown: smart auto / 咖啡套組 / 酪梨套組 / 自選 3 道 (modal popup)
- Algorithm: local / global
- Focus: efficiency / worst (the old "lift weakest type" heuristic)
- 🔍 顯示分數 toggle: shows per-row Δσ math under each section

**Internally uses arbitrary weights** — `worstBoost=50`, `wasteGlobal=200`, `wasteLocal=0.3*avgValue`, `coverageBonus=1000` — all hand-tuned, all to be deleted.

The Recommender (4 modes) was not touched this session; uses its own scoring per mode.

State keys in `S` (the global state object):
```
S.planAlgo        // 'local' | 'global'
S.planFocus       // 'efficiency' | 'worst'
S.planGoalMode    // 'smart' | 'coffee' | 'avocado' | 'custom'
S.planCustomGoals // { curry, salad, dessert } recipe names
S.planShowMath    // bool
```

Hash persistence keys mirror these.

---

## 7. Where things stand (end of session)

### Decided
- **σ definition**: `sigma_focused` (max per type, tier_bonus ≥ 0.35) is the agreed σ.
- **Search algorithm**: beam K=50, unbounded k for extras, optional 2-opt polish.
- **Search cost is acceptable** — full brute-force over all 2^|extras| subsets.
- **R aggregation**: leaning **R_inv_step** (Σ Δσ/t) per user's preference for "improvement over status". R_status confirmed broken.

### Open
- **σ_focused vs σ_completeness**: user wavered. Latest: σ_focused. Could expose as a UI toggle ("Sprint mode" vs "Balanced mode"). Not decided.
- **Local vs Global as separate panels**: Local (K=1) is essentially Recommender-with-goal-constraint. Worth keeping?
- **Patience knob α**: introduced earlier (R / n^α), abandoned in favour of swapping R formula directly. Could still expose for advanced users.
- **The output format** for the planner panel in `index.html` — what to show by default vs only when 顯示分數 is on.

### Buggy / unfinished
1. **`index.html` Path Planner is the OLD v2 algorithm.** No code from the prototype has been ported. The whole panel needs replacement once R/σ are locked.
2. **`scripts/path_planner_prototype.py`**:
   - `main()` still has `max_extras=3` in `scope_frontier` calls. Must be raised to `len(all_candidate_extras)`.
   - `beam_path` uses R_status internally for ranking. Switching to R_inv_step is a one-line change but not yet done.
   - Contains leftover σ_sum, σ_geo etc. code paths that are dispatched via `mode='sum' | 'focused'`. Default was flipped to 'focused' but the code is messy.
3. **`PATH_PLANNER_PROTOTYPE_REPORT.md`** has narrative from σ_sum era — stale, do not trust.
4. **`CLAUDE.md` §3 (key functions)** references buildPlanner in `index.html` which is about to be rewritten. Will need update.
5. **The Recommender** (4 modes) wasn't touched and still has its own heuristic scoring. Probably fine as a separate panel, but algorithmically inconsistent with the new Planner.
6. **Visual overlap sweep** was passed earlier in session but only verified against the old planner. After the new planner lands, redo the visual stress test (Chrome MCP detector at owned ∈ {0, 3, 9, 12, 15, 19} × toggle combinations).

---

## 8. Concrete numbers (sanity benchmarks)

To verify a fresh implementation gives the same answers:

**Coffee 3, no extras, σ_focused (tier≥0.35), R_status:**
- Greedy (K=1): R = 250,056
- Beam K=50: R = 270,941
- Optimal path: `哞哞鮮奶 → 甜甜蜜 → 醒腦咖啡豆 → 放鬆可可 → 窩心洋芋 → 豆製肉 → 純粹油 → 好眠番茄 → 品鮮蘑菇 → 萌綠大豆`
- σ trajectory: `[0, 0, 6793, 20885, 20885, 20885, 41103, 50113, 50113, 60164]`

**Avocado 3, no extras, σ_focused (tier≥0.35), R_status:**
- Beam K=50: R = 282,176
- σ trajectory: `[0, 0, 0, 24802, 31927, 37975, 56012, 56012, 75448]`

**Avocado 3, brute-force unbounded k under R_inv_step:**
- k=3 reaches global max R_inv_step = 13,567 with extras = `(品鮮蘑菇, 豆製肉, 沉甸甸南瓜)`
- k=4–7 tie at same R (multiple subsets give R=13,567)
- k=10 R drops to 12,750 (penalty for forcing useless ings)
- The k=3 path achieves σ=25,356 at step 4 (vs k=0's σ=24,802 at step 4) — a Pareto improvement at every step from t=4 onward

**Coffee 3, brute-force unbounded k under R_status (BROKEN METRIC, for reference only):**
- R grows monotonically with k. k=10 R=1,017,795. Last 10 steps are flat at peak σ.
- This is why R_status was rejected.

---

## 9. What the fresh session should do next

In rough order:

1. **Lock σ and R**. Read this doc. Decide:
   - σ_focused (default) vs σ_completeness — recommend σ_focused per latest exchange
   - R_inv_step (default) — confirmed
2. **Clean up prototype**: in `path_planner_prototype.py`:
   - Remove σ_sum and σ_completeness code paths (unless keeping as toggle)
   - Switch beam_path's internal ranking from R_status to R_inv_step
   - Raise scope_frontier `max_extras` to unlimited
   - Re-run all scenarios, regenerate `path_planner_prototype_output.txt`
3. **Update `PATH_PLANNER_PROTOTYPE_REPORT.md`** to reflect final algorithm.
4. **Port to `index.html`**: replace the entire Path Planner block (HTML controls + state + `buildPlanner` + listeners) with the prototype's logic transliterated to JS.
   - Reuse the existing UI shell (goal dropdown, algo select, focus removed, modal)
   - Drop `S.planFocus` (worst-type is gone)
   - Replace `S.planAlgo` 'local'/'global' with the new taxonomy (Greedy K=1 or Beam K=50)
   - 顯示分數 toggle: show Δσ per row and which recipe became the new type-max
   - Scope-frontier UI: 0/1/2/3/4… presented as a list of "+N extras → R = X" trade-offs (user clicks a row to commit to that scope)
5. **Re-run visual overlap sweep** against the new planner.
6. **Update `CLAUDE.md`** §3 to point at the new `buildPlanner`.

---

## 10. Things the fresh session should NOT assume

- Don't trust `PATH_PLANNER_PROTOTYPE_REPORT.md` — written before σ direction was settled.
- Don't assume `index.html`'s current Planner is correct — it's the v2 stub with arbitrary weights, to be discarded.
- Don't introduce arbitrary parameters. User has been strict about this — every weight must be derived from data or natural math, not "magic number 50".
- Don't pursue σ_sum (sum of all cookable) — rejected.
- Don't pursue σ_geo or σ_minmax — too harsh.
- Don't add a "guided planner" mode where the user picks intermediate dishes by name — user explicitly rejected ("we cannot just build a guide planner at all"). The algorithm must find optimal intermediates via scope-frontier search.

---

## 11. User communication preferences

- Wallace pushes back on arbitrary parameters, undercounting, and any algorithm that misses globally optimal alternatives.
- Wallace values transparency: every σ jump must be explainable in terms of which specific recipe was newly unlocked or upgraded.
- Wallace explicitly invoked explore-vs-exploit framing for this problem — comfort with that vocabulary.
- Wallace can do brute-force enumeration on his own (mentally) and will catch when the algorithm misses cases. Don't bluff; show math.
- Wallace's instructions are sometimes precise ("set discount of <35% to 100%") and sometimes directional ("balance slightly"). Always confirm direction before coding when uncertain.

---

**Last commit relevant to this work:** `a71f25a` (Revert prototype to σ_focused + add tier_bonus≥0.35 filter + Δσ reporting). Subsequent test scripts (`sigma_variants_comparison.py`, `value_added_variants.py`) and the math investigation are committed too. Latest brute-force findings (R_inv_step + unbounded k) are *only in chat history* — not yet codified in the prototype's `main()`.
