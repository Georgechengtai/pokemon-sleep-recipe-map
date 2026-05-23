"""Path Planner Prototype — Progressive Coverage Maximization

Goal: given 3 final-goal recipes, find an ordered ing path π that maximizes
the area under the per-step coverage curve σ(O_t).

σ(O_t) = Σ_{type ∈ {curry, salad, dessert}} max{tier_score(r) : r cookable in O_t, r.type = type}

R(π) = Σ_{t=1..n} σ(O_t)  [optionally divided by n^α for patience knob]

Constraint: final_ings ⊆ O_n.

Algorithms:
- greedy(K=1): at each step, pick ing maximizing σ(O_{t+1}); breaks ties by appears-in count
- beam(K=20): keep top-K partial paths ranked by R(prefix), expand each
- 2-opt: post-polish by swapping adjacent ings while R improves

No "intermediate" pre-selection — intermediates EMERGE from the path as σ jumps.

Usage:
    python3 path_planner_prototype.py
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable, Sequence
from dataclasses import dataclass


# ── Data loading ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Recipe:
    name: str
    type_en: str  # 'curry' | 'salad' | 'dessert'
    tier_bonus: float
    score_final: int
    ings: frozenset[int]  # ing-idx set


@dataclass
class World:
    ingredients: list[str]  # name list, indexed
    name_to_idx: dict[str, int]
    recipes: list[Recipe]
    by_name: dict[str, Recipe]
    by_type: dict[str, list[Recipe]]


def load_world(data_path: Path) -> World:
    raw = json.loads(data_path.read_text())
    ings = [x['name'] for x in raw['ingredients']]
    name_to_idx = {n: i for i, n in enumerate(ings)}
    recipes: list[Recipe] = []
    for r in raw['recipes']:
        if r.get('is_placeholder'):
            continue
        ing_idxs = frozenset(name_to_idx[i['name']] for i in r['ingredients'])
        recipes.append(Recipe(
            name=r['name'], type_en=r['type_en'],
            tier_bonus=float(r['tier_bonus']),
            score_final=int(r['score_final']),
            ings=ing_idxs,
        ))
    by_name = {r.name: r for r in recipes}
    by_type: dict[str, list[Recipe]] = {'curry': [], 'salad': [], 'dessert': []}
    for r in recipes:
        if r.type_en in by_type:
            by_type[r.type_en].append(r)
    return World(ings, name_to_idx, recipes, by_name, by_type)


# ── Reward functions ─────────────────────────────────────────────────────────

def sigma_free(owned: frozenset[int], world: World) -> int:
    """Goal-blind σ: best cookable recipe per type across ALL recipes (original buggy form)."""
    total = 0
    for t in ('curry', 'salad', 'dessert'):
        best = 0
        for r in world.by_type[t]:
            if r.ings.issubset(owned) and r.score_final > best:
                best = r.score_final
        total += best
    return total


def sigma_focused(owned: frozenset[int], world: World, scope: frozenset[int]) -> int:
    """Goal-scoped σ: only recipes whose ings ⊆ scope count.

    `scope` is the set of ings the user is willing to grind (typically the goal's
    union of ings; can be extended to include explicit optionals).
    """
    total = 0
    for t in ('curry', 'salad', 'dessert'):
        best = 0
        for r in world.by_type[t]:
            if r.ings.issubset(owned) and r.ings.issubset(scope) and r.score_final > best:
                best = r.score_final
        total += best
    return total


def sigma(owned: frozenset[int], world: World, scope: frozenset[int] | None = None) -> int:
    """Dispatch helper: focused if scope given, else free."""
    if scope is None:
        return sigma_free(owned, world)
    return sigma_focused(owned, world, scope)


def path_R(start_owned: frozenset[int], path: Sequence[int], world: World,
           alpha: float = 0.0, scope: frozenset[int] | None = None) -> float:
    """R(π) = sum of σ(O_t) over each step; optionally divided by n^α."""
    o = set(start_owned)
    total = 0
    for i in path:
        o.add(i)
        total += sigma(frozenset(o), world, scope)
    n = max(1, len(path))
    return total / (n ** alpha) if alpha > 0 else float(total)


def sigma_trajectory(start_owned: frozenset[int], path: Sequence[int], world: World,
                     scope: frozenset[int] | None = None) -> list[int]:
    """The σ value after each step. For diagnostics."""
    o = set(start_owned)
    traj = []
    for i in path:
        o.add(i)
        traj.append(sigma(frozenset(o), world, scope))
    return traj


def emergent_milestones(start_owned: frozenset[int], path: Sequence[int], world: World) -> list[tuple[int, Recipe]]:
    """At which step does each new recipe become cookable? Returns [(step_idx, recipe), ...]."""
    o = set(start_owned)
    already = set(r.name for r in world.recipes if r.ings.issubset(o))
    out = []
    for step, i in enumerate(path, 1):
        o.add(i)
        for r in world.recipes:
            if r.name in already:
                continue
            if r.ings.issubset(o):
                out.append((step, r))
                already.add(r.name)
    return out


# ── Algorithms ───────────────────────────────────────────────────────────────

def required_ings(goals: Sequence[Recipe]) -> frozenset[int]:
    out: set[int] = set()
    for g in goals:
        out |= g.ings
    return frozenset(out)


def appears_in_count(world: World) -> list[int]:
    """For each ing-idx, how many recipes use it. Stable tiebreaker."""
    counts = [0] * len(world.ingredients)
    for r in world.recipes:
        for i in r.ings:
            counts[i] += 1
    return counts


def greedy_path(
    start_owned: frozenset[int],
    goals: Sequence[Recipe],
    world: World,
    *,
    scope: frozenset[int] | None = None,
    alpha: float = 0.0,
) -> list[int]:
    """K=1 greedy over required ings (= scope ∪ goal-ings) — picks σ-maximizing next ing.

    The path is exactly the ordering of (scope ∪ goal-ings) minus start.
    `scope` defaults to required (goal ings union). To allow extras, expand scope.
    σ is goal-scoped: only counts recipes whose ings ⊆ scope.
    """
    req = required_ings(goals)
    effective_scope = (req | scope) if scope else req
    appears = appears_in_count(world)

    owned = set(start_owned)
    path: list[int] = []
    pool: set[int] = set(effective_scope - owned)

    while pool:
        candidates = list(pool)
        before = sigma(frozenset(owned), world, effective_scope)
        best = None  # (gain, appears, -i, ing_idx)
        for i in candidates:
            gain = sigma(frozenset(owned | {i}), world, effective_scope) - before
            key = (gain, appears[i], -i)
            if best is None or key > best[:3]:
                best = (gain, appears[i], -i, i)
        i_chosen = best[3]
        owned.add(i_chosen)
        path.append(i_chosen)
        pool.discard(i_chosen)
    return path


def beam_path(
    start_owned: frozenset[int],
    goals: Sequence[Recipe],
    world: World,
    *,
    beam: int = 20,
    alpha: float = 0.0,
    scope: frozenset[int] | None = None,
) -> list[int]:
    """Beam search over orderings of (effective_scope - owned). Ranks partial paths by R(prefix)
    with patience α. The set of ings in the final path is fixed (= effective_scope − start_owned);
    only the ORDER is optimized."""
    req = required_ings(goals)
    effective_scope = (req | scope) if scope else req
    pool_universe = effective_scope - start_owned
    n_target = len(pool_universe)
    appears = appears_in_count(world)

    Path = list[int]
    Frontier = list[tuple[Path, frozenset[int]]]

    frontier: Frontier = [([], frozenset(start_owned))]
    while frontier and len(frontier[0][0]) < n_target:
        next_frontier: Frontier = []
        for path, owned in frontier:
            remaining = pool_universe - owned
            for i in remaining:
                npath = path + [i]
                nowned = owned | {i}
                next_frontier.append((npath, nowned))
        # Rank by R(prefix) with patience
        def rank_key(item):
            p, _ = item
            return (path_R(start_owned, p, world, alpha=alpha, scope=effective_scope),
                    sum(appears[i] for i in p))
        next_frontier.sort(key=rank_key, reverse=True)
        frontier = next_frontier[:beam]
    return frontier[0][0] if frontier else []


def two_opt_polish(
    start_owned: frozenset[int],
    path: Sequence[int],
    world: World,
    alpha: float = 0.0,
    scope: frozenset[int] | None = None,
) -> list[int]:
    """Swap adjacent pairs while R improves. The set is fixed; only the order changes."""
    cur = list(path)
    improved = True
    while improved:
        improved = False
        for i in range(len(cur) - 1):
            swap = cur[:i] + [cur[i + 1], cur[i]] + cur[i + 2:]
            if path_R(start_owned, swap, world, alpha=alpha, scope=scope) > \
               path_R(start_owned, cur, world, alpha=alpha, scope=scope):
                cur = swap
                improved = True
    return cur


# ── Reporting ────────────────────────────────────────────────────────────────

def fmt_path(path: Sequence[int], world: World) -> str:
    return ' → '.join(world.ingredients[i] for i in path)


def report_path(label: str, start_owned: frozenset[int], path: Sequence[int], world: World,
                alpha: float = 0.0, scope: frozenset[int] | None = None) -> None:
    print(f"\n=== {label} ===")
    print(f"  path length: {len(path)}")
    print(f"  R(π) (α={alpha}, scope size={len(scope) if scope else 'free'}): "
          f"{path_R(start_owned, path, world, alpha=alpha, scope=scope):,.2f}")
    print(f"  sequence: {fmt_path(path, world)}")
    traj = sigma_trajectory(start_owned, path, world, scope=scope)
    print(f"  σ trajectory: {traj}")
    ms = emergent_milestones(start_owned, path, world)
    if ms:
        # Only show milestones that are in scope (if scope given) — these are the
        # "real" intermediate milestones the user can credit toward the path.
        in_scope_ms = [(t, r) for t, r in ms if (scope is None or r.ings.issubset(scope))]
        if in_scope_ms:
            print(f"  in-scope milestones (recipe lit up at step):")
            for step, r in in_scope_ms:
                print(f"    t={step:2d}  +{int(r.tier_bonus*100):2d}% {r.type_en:<7} {r.name:<22} ({r.score_final:,})")
        out_of_scope = [(t, r) for t, r in ms if scope is not None and not r.ings.issubset(scope)]
        if out_of_scope:
            print(f"  out-of-scope side-effects ({len(out_of_scope)} recipes lit but not in goal scope, suppressed)")
    print()


def report_scenario(label: str, goals_names: list[str], world: World, *,
                    owned_names: list[str] = (), alpha: float = 0.0, beam: int = 20,
                    extra_scope_ings: list[str] = ()) -> None:
    print('━' * 80)
    print(f"SCENARIO: {label}")
    print(f"  Goals: {goals_names}")
    print(f"  Owned at start: {list(owned_names) or '∅'}")
    if extra_scope_ings:
        print(f"  Extra scope ings (user-extended optionals): {extra_scope_ings}")
    print(f"  patience α: {alpha}; beam K: {beam}")
    print('━' * 80)
    goals = [world.by_name[n] for n in goals_names]
    start = frozenset(world.name_to_idx[n] for n in owned_names)

    req = required_ings(goals)
    print(f"  required (final_ings, {len(req)}): {sorted(world.ingredients[i] for i in req)}")

    extra_set = frozenset(world.name_to_idx[n] for n in extra_scope_ings)
    scope = req | extra_set
    print(f"  effective scope ({len(scope)}): {sorted(world.ingredients[i] for i in scope)}")

    p_g = greedy_path(start, goals, world, scope=scope, alpha=alpha)
    report_path('A. Greedy (Local)', start, p_g, world, alpha=alpha, scope=scope)

    p_b = beam_path(start, goals, world, beam=beam, alpha=alpha, scope=scope)
    report_path(f'B. Beam (Global, K={beam})', start, p_b, world, alpha=alpha, scope=scope)

    p_polished = two_opt_polish(start, p_b, world, alpha=alpha, scope=scope)
    if p_polished != p_b:
        report_path('C. Beam + 2-opt polish', start, p_polished, world, alpha=alpha, scope=scope)
    else:
        print(f"  C. 2-opt polish: no improvement over Beam")


# ── Main ─────────────────────────────────────────────────────────────────────

def scope_frontier(world: World, goal_names: list[str], max_extras: int = 4, beam: int = 20, alpha: float = 0.0) -> None:
    """Enumerate small subsets of extra ings (beyond required), report the best path R for each.
    Helps the user choose how much grind they want for how much payoff."""
    from itertools import combinations
    goals = [world.by_name[n] for n in goal_names]
    req = required_ings(goals)
    all_ings = set(range(len(world.ingredients)))
    candidate_extras = sorted(all_ings - req)
    print('━' * 80)
    print(f"SCOPE FRONTIER for goals {goal_names} (k = number of extra ings to include):")
    print('━' * 80)
    print(f"  required (final_ings, {len(req)}): {sorted(world.ingredients[i] for i in req)}")
    print(f"  candidate extras: {[world.ingredients[i] for i in candidate_extras]}")
    print()

    best_per_k = {}  # k -> (R, extras, path)
    for k in range(0, min(max_extras, len(candidate_extras)) + 1):
        best = None
        for combo in combinations(candidate_extras, k):
            scope = frozenset(req | set(combo))
            p = beam_path(frozenset(), goals, world, beam=beam, alpha=alpha, scope=scope)
            R = path_R(frozenset(), p, world, alpha=alpha, scope=scope)
            if best is None or R > best[0]:
                best = (R, list(combo), p, scope)
        best_per_k[k] = best
        R, extras, p, scope = best
        extras_names = [world.ingredients[i] for i in extras]
        if alpha > 0:
            R_total = path_R(frozenset(), p, world, alpha=0.0, scope=scope)
            print(f"  k={k} (path {len(p):2d} steps, R={R_total:,.0f}, R/n^{alpha}={R:,.0f}): extras = {extras_names}")
        else:
            print(f"  k={k} (path {len(p):2d} steps, R={R:,.0f}): extras = {extras_names}")
        traj = sigma_trajectory(frozenset(), p, world, scope=scope)
        print(f"      σ trajectory: {traj}")
    print()


def sanity_set_compare(world: World, goal_names: list[str], set_A: list[str], set_B: list[str], alpha: float = 0.0) -> None:
    """For a given final goal, compare 2 hand-picked intermediate sets.
    Forces the algorithm to use each set's ings (scope = goal_ings ∪ set_ings),
    reports R(π) and shows which one the user-mentioned alternatives produce.
    Also runs the unrestricted algorithm and shows if it matches A, B, or neither.
    """
    goals = [world.by_name[n] for n in goal_names]
    coffee_req = required_ings(goals)
    print('━' * 80)
    print(f"SANITY for goal {goal_names}:")
    print('━' * 80)

    for label, names in (('Set A', set_A), ('Set B', set_B)):
        rs = [world.by_name[n] for n in names]
        union = set()
        for r in rs:
            union |= r.ings
        full_scope = frozenset(union | coffee_req)
        extras = sorted(world.ingredients[i] for i in (union - coffee_req))
        print(f"\n  {label} = {names}")
        print(f"    extra ings added by these intermediates: {extras} (adds {len(extras)} to {len(coffee_req)} required)")
        p = beam_path(frozenset(), goals, world, beam=20, alpha=alpha, scope=full_scope)
        R = path_R(frozenset(), p, world, alpha=alpha, scope=full_scope)
        print(f"    optimal path within {label}'s scope ({len(p)} steps, R = {R:,.0f}):")
        print(f"      {fmt_path(p, world)}")
        traj = sigma_trajectory(frozenset(), p, world, scope=full_scope)
        print(f"      σ trajectory: {traj}")

    # Also: what's the OPTIMAL path with NO extras (req-only scope)?
    p_req = beam_path(frozenset(), goals, world, beam=20, alpha=alpha, scope=coffee_req)
    R_req = path_R(frozenset(), p_req, world, alpha=alpha, scope=coffee_req)
    print(f"\n  No-extras path (required only, scope = {len(coffee_req)} ings):")
    print(f"    {len(p_req)} steps, R = {R_req:,.0f}")
    print(f"    {fmt_path(p_req, world)}")
    print(f"    σ trajectory: {sigma_trajectory(frozenset(), p_req, world, scope=coffee_req)}")


def main() -> None:
    data = Path(__file__).resolve().parent.parent / 'data.json'
    world = load_world(data)

    print(f"Loaded {len(world.recipes)} recipes, {len(world.ingredients)} ingredients.\n")

    # Scenario 1: Coffee 3, no owned, σ_focused on coffee ings only.
    report_scenario(
        'Coffee 3 (σ scoped to coffee final_ings only — no avocado detour)',
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, owned_names=[], alpha=0.0, beam=20,
    )

    # Scenario 2: Avocado 3
    report_scenario(
        'Avocado 3 (σ scoped to avocado final_ings only)',
        ['茂盛焗烤酪梨', '重踏酪梨醬脆片', '採蜜巧克力格子鬆餅'],
        world, owned_names=[], alpha=0.0, beam=20,
    )

    # Scenario 3: Coffee 3 with patience α=0.5 (penalize long paths)
    report_scenario(
        'Coffee 3 with patience α=0.5 (R divided by n^0.5)',
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, owned_names=[], alpha=0.5, beam=20,
    )

    # Scenario 4: Sanity for Wallace's 6-vs-8 example
    sanity_set_compare(
        world,
        goal_names=['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        set_A=['迷昏拳辣味咖哩', '冥想香甜沙拉', '破格玉米香提拉米蘇'],
        set_B=['迷昏拳辣味咖哩', '萌綠沙拉', '破格玉米香提拉米蘇'],
        alpha=0.0,
    )

    # Scenario 5: Starting partially-owned (e.g., 3 ings already grinded)
    report_scenario(
        'Coffee 3 with 3 owned (特選蘋果 / 哞哞鮮奶 / 萌綠大豆) — realistic mid-game',
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, owned_names=['特選蘋果', '哞哞鮮奶', '萌綠大豆'], alpha=0.0, beam=20,
    )

    # Scenario 6: Pareto frontier of scope-extension for Coffee 3
    scope_frontier(world,
                   goal_names=['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
                   max_extras=3, beam=20, alpha=0.0)

    # Scenario 7: Pareto frontier for Avocado 3
    scope_frontier(world,
                   goal_names=['茂盛焗烤酪梨', '重踏酪梨醬脆片', '採蜜巧克力格子鬆餅'],
                   max_extras=3, beam=20, alpha=0.0)

    # Scenario 8: Same frontier under patience α=0.5
    scope_frontier(world,
                   goal_names=['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
                   max_extras=3, beam=20, alpha=0.5)


if __name__ == '__main__':
    main()
