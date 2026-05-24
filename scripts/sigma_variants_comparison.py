"""One-off comparison: 4 σ variants side-by-side across key scenarios.

All variants use: tier_bonus >= 0.35 filter, max-per-type as the building block.
The 4 variants differ in how the 3 type-maxes are combined into a single σ:

A. σ_sum            = curry_max + salad_max + dessert_max         (current default)
B. σ_geo            = (curry_max × salad_max × dessert_max)^(1/3) (geomean — strict balance)
C. σ_completeness   = sum × (count_types_cooked / 3)              (soft balance)
D. σ_minmax         = min(curry_max, salad_max, dessert_max)      (bottleneck on weakest)

R(π) = Σ σ(O_t) over the path. Beam search ranks partial paths by R(prefix).
"""

from __future__ import annotations
import sys, json
from pathlib import Path
from itertools import combinations

sys.path.insert(0, str(Path(__file__).resolve().parent))
from path_planner_prototype import load_world, required_ings, fmt_path

MIN_TIER = 0.35

def best_per_type(owned, scope, world):
    out = [0, 0, 0]
    for ti, t in enumerate(('curry','salad','dessert')):
        for r in world.by_type[t]:
            if r.tier_bonus < MIN_TIER: continue
            if r.ings.issubset(owned) and r.ings.issubset(scope) and r.score_final > out[ti]:
                out[ti] = r.score_final
    return out

def sigma_sum(owned, scope, world):
    return sum(best_per_type(owned, scope, world))

def sigma_geo(owned, scope, world):
    bp = best_per_type(owned, scope, world)
    if any(x == 0 for x in bp): return 0
    return int((bp[0] * bp[1] * bp[2]) ** (1/3))

def sigma_completeness(owned, scope, world):
    bp = best_per_type(owned, scope, world)
    c = sum(1 for x in bp if x > 0)
    return int(sum(bp) * c / 3)

def sigma_minmax(owned, scope, world):
    return min(best_per_type(owned, scope, world))

VARIANTS = [
    ('A. σ_sum         ', sigma_sum),
    ('B. σ_geo         ', sigma_geo),
    ('C. σ_completeness', sigma_completeness),
    ('D. σ_minmax      ', sigma_minmax),
]

def path_R(start, path, scope, sig_fn, world):
    o = set(start)
    tot = 0
    for i in path:
        o.add(i)
        tot += sig_fn(frozenset(o), scope, world)
    return tot

def sigma_traj(start, path, scope, sig_fn, world):
    o = set(start)
    out = []
    for i in path:
        o.add(i)
        out.append(sig_fn(frozenset(o), scope, world))
    return out

def beam_search(start, scope, sig_fn, world, beam=50):
    pool = scope - start
    n = len(pool)
    frontier = [([], frozenset(start))]
    while frontier and len(frontier[0][0]) < n:
        nxt = []
        for path, owned in frontier:
            for i in pool - owned:
                nxt.append((path + [i], owned | {i}))
        nxt.sort(key=lambda it: path_R(start, it[0], scope, sig_fn, world), reverse=True)
        frontier = nxt[:beam]
    return frontier[0][0] if frontier else []

def report_scenario(label, goal_names, world, scope_extras=(), beam=50):
    print('━' * 100)
    print(f"{label}")
    goals = [world.by_name[n] for n in goal_names]
    req = required_ings(goals)
    extra_ings = frozenset(world.name_to_idx[n] for n in scope_extras)
    scope = frozenset(req | extra_ings)
    print(f"  Goals: {goal_names}")
    if scope_extras:
        print(f"  Extra scope ings: {list(scope_extras)}")
    print(f"  scope size: {len(scope)}, beam K: {beam}, min_tier: {MIN_TIER}")
    print('━' * 100)

    rows = []
    for name, fn in VARIANTS:
        p = beam_search(frozenset(), scope, fn, world, beam=beam)
        R = path_R(frozenset(), p, scope, fn, world)
        traj = sigma_traj(frozenset(), p, scope, fn, world)
        final_bp = best_per_type(set(p), scope, world)
        rows.append({
            'name': name, 'p': p, 'R': R, 'traj': traj, 'final_bp': final_bp,
        })

    # Side-by-side table: variant | R | curry / salad / dessert (final) | path
    print(f"\n  {'variant':<22}{'R(π)':<14}{'final per-type (curry / salad / dessert)':<48}")
    for r in rows:
        bp = r['final_bp']
        print(f"  {r['name']}  {r['R']:<12,}  {bp[0]:>6,} / {bp[1]:>6,} / {bp[2]:>6,}")

    print(f"\n  Paths:")
    for r in rows:
        seq = ' → '.join(world.ingredients[i] for i in r['p'])
        # mark extra positions
        if scope_extras:
            marks = [f"[{idx+1}] {world.ingredients[i]}" if world.ingredients[i] in scope_extras
                     else world.ingredients[i] for idx,i in enumerate(r['p'])]
            seq = ' → '.join(marks)
        print(f"  {r['name']}: {seq}")

    print(f"\n  σ trajectories:")
    for r in rows:
        print(f"  {r['name']}: {r['traj']}")

    # Step-by-step value-added analysis under variant C (the recommendation)
    print(f"\n  --- Step-by-step (variant C. σ_completeness): ---")
    c_row = next(r for r in rows if 'completeness' in r['name'])
    p = c_row['p']
    o = set()
    prev_bp = best_per_type(o, scope, world)
    prev_sigma = sigma_completeness(frozenset(o), scope, world)
    print(f"    {'t':<3}{'ing':<14}{'σ':<10}{'Δσ':<10}{'types-cooked':<14}{'change'}")
    for step, ing_i in enumerate(p, 1):
        o.add(ing_i)
        nb = best_per_type(o, scope, world)
        s = sigma_completeness(frozenset(o), scope, world)
        delta = s - prev_sigma
        c_now = sum(1 for x in nb if x > 0)
        changes = []
        for ti, t in enumerate(('curry','salad','dessert')):
            if prev_bp[ti] != nb[ti]:
                if prev_bp[ti] == 0:
                    # find what enabled it
                    for r in world.by_type[t]:
                        if r.score_final == nb[ti] and r.ings.issubset(o) and r.ings.issubset(scope):
                            changes.append(f"{t}: ∅ → +{int(r.tier_bonus*100)}% {r.name}({r.score_final:,})")
                            break
                else:
                    for r in world.by_type[t]:
                        if r.score_final == nb[ti] and r.ings.issubset(o) and r.ings.issubset(scope):
                            changes.append(f"{t}: {prev_bp[ti]:,} → +{int(r.tier_bonus*100)}% {r.name}({r.score_final:,})")
                            break
        chg = '; '.join(changes) if changes else '—'
        marker = '↑' if delta > 0 else ' '
        print(f"    {step:<3}{world.ingredients[ing_i]:<14}{s:<10,}{marker}+{delta:<6,}  {c_now}/3            {chg}")
        prev_bp = nb
        prev_sigma = s
    print()

def main():
    from path_planner_prototype import load_world
    world = load_world(Path(__file__).resolve().parent.parent / 'data.json')

    # Scenarios:
    report_scenario(
        "SCENARIO 1: Coffee 3 — no extras (just the 10 required ings)",
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, scope_extras=(), beam=50,
    )

    report_scenario(
        "SCENARIO 2: Coffee 3 + Set A extras (Wallace's 6-ing intermediate set)",
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, scope_extras=['火辣香草', '特選蘋果', '萌綠玉米'], beam=50,
    )

    report_scenario(
        "SCENARIO 3: Coffee 3 + Set B extras (Wallace's 8-ing intermediate set)",
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, scope_extras=['火辣香草', '萌綠玉米'], beam=50,
    )

    report_scenario(
        "SCENARIO 4: Avocado 3 — no extras (9 required ings)",
        ['茂盛焗烤酪梨', '重踏酪梨醬脆片', '採蜜巧克力格子鬆餅'],
        world, scope_extras=(), beam=50,
    )

    report_scenario(
        "SCENARIO 5: Avocado 3 + 醒腦咖啡豆 (cross-goal extra — unlocks coffee +61% dessert?)",
        ['茂盛焗烤酪梨', '重踏酪梨醬脆片', '採蜜巧克力格子鬆餅'],
        world, scope_extras=['醒腦咖啡豆'], beam=50,
    )

if __name__ == '__main__':
    main()
