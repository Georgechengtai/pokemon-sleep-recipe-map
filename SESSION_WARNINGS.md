# Warnings for the next collaborator

Read this *after* `SESSION_HANDOFF.md`. That doc tells you what to do. This one tells you what tripped us up and what's still fragile.

---

## 1. Mistakes we already made (and how)

### 1a. The σ_free goal-blind bug
**What I did:** First version of the Path Planner counted "max per type" across *all 76 recipes*, ignoring the user's stated goal. **Result:** Coffee 3 path silently ballooned to 19 steps because adding avocado-related ings unlocked higher-σ avocado dishes the algorithm preferred.

**Why it's instructive:** the user told me "Coffee 3 is the goal" and I treated that as a *constraint on the terminal state* but not as a *scope restriction on what counts toward σ*. The algorithm "succeeded" at coffee by stealth-pivoting to avocado.

**Lesson:** the goal is both a *terminal constraint* AND a *scope filter*. σ must only count recipes whose ings are within what the user has committed to grinding.

### 1b. σ_sum overcorrection
**What I did:** When the user complained "pumpkin should unlock 2 recipes but you only counted the salad", I jumped to summing scores of every cookable recipe in scope.

**Why it was wrong:** the user wasn't asking for sum-of-all. They were observing that 扮演南瓜精濃湯 (+48% curry) doesn't improve σ when curry max is already +78%. The "two recipes" framing was a observational complaint about the algorithm's *output transparency*, not a request to change the σ formula.

**Lesson:** when the user describes a symptom, restate the diagnosis back before changing the algorithm. I lost 3+ turns and a wrong commit (`34f64b6` σ_sum, reverted by `a71f25a`) to this misread.

### 1c. Calling the user's analytical example a "custom goal"
**What I did:** The user wrote "for Coffee 3, compare Set A (3 intermediate dishes) vs Set B (3 intermediate dishes)". I added these to the prototype's main() as a "custom goal scenario" — Set A as the goal.

**Why it was wrong:** Set A and Set B were proposed *intermediate sets for the Coffee 3 goal*, not alternative goals. User responded with `??????????`.

**Lesson:** when the user gives you a structured example, read the structure literally. Don't squeeze it into the closest schema you already have.

### 1d. The `max_extras=3` cap
**What I did:** Scope-frontier brute-forced over subsets of size 0..3 — silently missing all k≥4 alternatives.

**Why it was wrong:** the user proposed an intermediate set requiring 4 extras. The algorithm reported "your set is suboptimal" when actually the algorithm just *wasn't looking* at the right search space.

**Lesson:** when the user proposes an alternative the algorithm rejects, verify the algorithm *considered* that alternative before defending the algorithm. Be skeptical of your own search bounds.

### 1e. R_status is structurally broken — discovered late
**The bug:** `R = Σ σ_t` rewards path length even when extras add no σ. Each padding step at peak σ contributes the peak value to R. Result: under R_status, the "optimal" Avocado k is k=10 (include all 10 non-required ings) at R=1,017,795 — even though the last 10 steps are completely flat at peak.

**Why we missed it for ~20 turns:** small-k comparisons all looked sensible. Only when we brute-forced unbounded k did the failure mode reveal itself.

**Lesson:** test metric behaviour at the extremes (k=0 AND k=full). A metric that monotonically rewards more extras is broken — there should be a natural maximum.

### 1f. "Goal-adjacent intermediates" — an arbitrary filter I proposed
**What I did:** Suggested filtering candidate extras to "ings that appear in a recipe sharing ≥1 ing with the goal". User called it out: that's still an arbitrary parameter (why ≥1 and not ≥2?).

**Lesson:** the user *will* spot arbitrary parameters dressed as "natural" rules. Push for definitions derived from the actual objective function, not pre-filters.

### 1g. CLAUDE.md / Claude.md confusion
The old `Claude.md` at repo root was the *Discord A/B-route strategy* doc, not a web-app dev guide. I'd been operating on it for half the session before user pointed out it was misleading. We renamed it to `ISLAND-STRATEGY.md` and wrote a new `CLAUDE.md`.

**Lesson:** at session start, verify what `CLAUDE.md` actually contains rather than assume it's the project guide. Filenames lie.

### 1h. Arbitrary "realistic mid-game" owned set
**What I did:** Picked `[特選蘋果, 哞哞鮮奶, 萌綠大豆]` as a starting owned set in test scenarios with no reasoning. User: "if you arbitrary select a random list, it won't be random and it will not be useful for this algorithm."

**Lesson:** test cases should be *constructed with purpose* (newbie/half-way/near-done), not "3 random items I pulled".

---

## 2. Fragile things in the current codebase

### 2a. The metric magnitudes are NOT comparable across formulations
- R_status of a Coffee path: 270,941
- R_inv_step of the same path: ~13,500
- σ_completeness path R: ~190,000

Don't accidentally compare numbers from different metrics. The prototype output prints the metric name, but it's easy to skim past.

### 2b. The transparency report is coupled to σ_focused's structure
`report_path()` in `path_planner_prototype.py` traces "which type's max changed" — only correct under max-per-type σ. If σ changes to σ_sum or σ_geo, the report logic must change too.

### 2c. Tie-break order matters and is fragile
Current beam-search tie-break: `(gain, appears_in_count, -ing_id)`. Reordering these *changes the output path*. Pure determinism but the chosen order is somewhat arbitrary (appears_in_count was chosen to penalize "useless dead-weight" ings, ing_id is just a stable id-vote).

If you swap to a different σ where ties are rarer, this matters less. With tier-filter σ_focused, ties are *very common* (many steps have Δσ=0) so tie-break is the path-deciding logic, not the value calculation.

### 2d. Brute-force k-search is borderline expensive
For Avocado (9 required, 10 candidate extras): 2^10 = 1024 subsets × beam K=50 × ~14 ings/path = ~52s.

For a goal with fewer required ings, candidate_extras grows and 2^|extras| explodes:
- 8 required, 11 extras: 2048 subsets, ~100s
- 7 required, 12 extras: 4096 subsets, ~200s

In the web app this will need a progress indicator, web-worker, or some pruning heuristic. **As-is, this won't fit in a synchronous render call.**

### 2e. The `min_tier=0.35` filter is hard-coded as a default
It's a parameter on every function but the default 0.35 is repeated 8+ times. If the planned UI toggle (the "include low-tier recipes" button) gets wired, it must propagate consistently through `sigma()`, `path_R()`, `beam_path()`, `report_path()`, `scope_frontier()`. Easy to miss one.

### 2f. The `World` data structure caches `by_type` and `by_name`
If you mutate `world.recipes` (e.g., to apply a tier filter at load time instead of at scoring time), the caches go stale. Currently no mutation happens but adding `world.copy_with_tier_filter()` would be a footgun.

### 2g. `index.html` Path Planner ID collisions
The web app's old planner uses IDs `plan-goal-mode`, `plan-algo`, `plan-focus`, `plan-show-math`, `plan-custom-modal`, etc. When you replace the planner with the new algorithm, keep the IDs *or* update every event listener AND hash-state key. There's no abstraction layer.

---

## 3. Surprising findings

### 3a. The pumpkin+mushroom+corn cluster
For Avocado 3 goal, the *true* k=3 optimum under R_inv_step is extras = `(品鮮蘑菇, 豆製肉, 沉甸甸南瓜)`. These three together unlock:
- 大塊滿滿熱水沙拉 (+61% salad, 25,356) at step 4 — *beats* 嫩亮酪梨's 茂盛焗烤酪梨 +78% (24,802) at step 4!
- 扮演南瓜精濃湯 (+48% curry, 15,621) at step 5 — bonus

This is a Pareto improvement over k=0 at *every* step from t=4 onward, and the algorithm only found it under unbounded k-search with R_inv_step. The simpler algorithms (R_status, smaller k cap) missed this entirely.

**Implication:** the "obvious" extras (like 嫩亮酪梨 for +78% curry) are not always the best — clusters of 2-3 less obvious ings can dominate.

### 3b. Beam width K=20 ≈ K=500 in nearly all tested cases
Increasing beam width almost never changes the answer. The problem doesn't have many local optima at this scale. Don't tune K hoping for improvements — change the metric instead.

### 3c. Σ Δσ_t × (n − t + 1) = Σ σ_t exactly
Many "weighted value-added" formulations collapse to the AUC. The user intuitively expected `value-added` to be different from `total sum`; mathematically they're identical *unless* the weighting is non-monotone in t. Only formulations like `Σ Δσ_t / t` truly differ from R_status. This is non-obvious and was a source of confusion.

### 3d. σ_geo and σ_minmax give long σ=0 stretches
Under "geometric mean of 3 type maxes", σ stays at exactly 0 until *all 3 types* have a cookable ≥35% recipe — typically 6-8 steps into a 10-step path. The trajectory is psychologically wrong: the player appears to make zero progress for most of the path, then everything snaps on at once.

User intuition: "I want broad coverage" doesn't mean "I want σ=0 until I have everything." Be careful with strict-balance metrics.

### 3e. σ_completeness × c/3 doesn't strongly differ from σ_sum for Avocado
For tightly-coupled goal sets (where every ing serves multiple goal recipes), the type-coverage multiplier doesn't change rankings much. σ_completeness mainly helps Coffee-type scenarios where ings build separate stacks. So the choice between σ_focused (= σ_sum) and σ_completeness depends on goal-set topology — not a universal preference.

### 3f. The 4-mode Recommender wasn't touched all session
The Recommender's logic ("多解料理 / 衝高分 / 補弱系 / 離完成最近") is from an earlier sprint. It uses its own scoring per mode, mostly goal-blind. It's been *consistent* with the panel relationship the user defined ("Recommender = stateless greedy") but algorithmically it's an island — no shared σ definition with the Planner.

**Mild risk:** when the Planner becomes σ_focused + R_inv_step, the Recommender will look philosophically inconsistent. May want to harmonize later.

---

## 4. Anti-patterns to avoid

### Don't add magic constants
Even if they're "small" or "make the test case work". The user will catch them and will be right to push back. Every weight must have a derivation from data or from a natural math operation (sum, mean, max, min, geomean, count).

### Don't build a "guided planner" mode
The user explicitly rejected having users name intermediate dishes manually. The algorithm must find optima via scope-frontier brute-force, not user-curation. Don't let scope creep bring back a "specify intermediates" UI.

### Don't patch the algorithm when the metric is wrong
When the output looked weird, my first instinct was always to add a tie-break, a bonus, a discount. Several times the real problem was the σ or R formula itself, not the search. Try changing the metric first.

### Don't claim "Algorithm A is better than Algorithm B" without testing at extremes
"R_status gives 584k vs 570k for these two paths" is meaningless if R_status would also pick a 19-step padded path over either. Always test what the algorithm does at k=0, k=max, and k=intermediate. Compare *behavioural shapes*, not just specific R numbers.

### Don't conflate the algorithmic search problem with the player's strategic choice
The algorithm can find σ-maximum paths. It cannot tell the player "you might prefer this aesthetically-themed intermediate dish over the σ-optimal one." If the user wants to commit to specific dishes, that's a separate input mode, not a search-quality issue. Trying to make the algorithm "discover" the user's preferences via heuristics is a tar pit.

### Don't treat σ values as comparable across formulations
σ_sum = 60,164 and σ_completeness = 19,939 *for the same state* aren't measuring the same thing. Don't ratio them, don't average them, don't claim "σ_sum is 3× σ_completeness".

---

## 5. Bugs the current code still has

(In `scripts/path_planner_prototype.py` unless noted.)

1. **`beam_path()` defaults to `mode='focused'` but internally still uses R_status for ranking.** Latest agreement is R_inv_step. One-line change but not yet done.

2. **`scope_frontier()` still has `max_extras=3` in `main()` call.** Should be `max_extras=len(candidate_extras)`. Single line.

3. **The prototype has leftover σ mode dispatch** (`mode='sum'` branch in `sigma()` dispatch). σ_sum is rejected — remove the code or keep but never call.

4. **`report_path()` always uses `mode` and `min_tier` from arguments** — but the σ tracing logic in the function assumes σ_focused structure. If `mode='sum'` is passed, the "which type's max changed" output will be wrong.

5. **`index.html` Path Planner is the v2 stub** with arbitrary weights. To be replaced.

6. **`PATH_PLANNER_PROTOTYPE_REPORT.md`** still describes σ_sum era. Stale — either rewrite or delete.

7. **No unit tests anywhere.** All validation is via running scenarios and eyeballing trajectories. If you refactor, you'll regress without noticing. At minimum, capture the sanity numbers in `SESSION_HANDOFF.md` §8 as expected values and write a test.

8. **`scripts/path_planner_prototype_output.txt`** is the output from one of multiple algorithm states this session. Not guaranteed to match what `main()` produces *now*. Re-run to refresh.

---

## 6. Things I'd verify before trusting a fresh implementation

If you re-implement σ + R + beam + brute-force k-search from scratch:

1. **Coffee 3 no extras, σ_focused, R_status, beam K=50**: R must equal **270,941**. σ trajectory must equal `[0, 0, 6793, 20885, 20885, 20885, 41103, 50113, 50113, 60164]`.
2. **Avocado 3 no extras, σ_focused, R_status, beam K=50**: R = **282,176**. σ trajectory `[0, 0, 0, 24802, 31927, 37975, 56012, 56012, 75448]`.
3. **Avocado 3 brute-force, R_inv_step**: the best k=3 extras must be `(品鮮蘑菇, 豆製肉, 沉甸甸南瓜)` with R_inv_step ≈ **13,567**.
4. **Avocado 3 brute-force, R_status, k=10**: must give R = **1,017,795** with σ trajectory ending in flat 10-step plateau at 75,642. (Confirms the R_status pathology.)

If any of these are off, the implementation diverged.

---

## 7. The single most important thing

The user can do math. When the algorithm produces an answer that disagrees with the user's hand-built example, **show the user the math**. Don't argue. Either the algorithm has a bug, or the user will see why their example was sub-optimal once the numbers are laid out. Both outcomes move the work forward; defending the algorithm verbally doesn't.

The session got productive when I started running brute-force comparisons and posting σ trajectories per step. It stalled when I argued from the algorithm's design instead. Lead with the trace, follow with interpretation.
