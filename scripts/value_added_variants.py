"""Test 'value-added' R formulations to inspect flat-step treatment.

Setup: σ uses σ_sum (max-per-type, tier_bonus>=0.35).
We compare 4 R formulations that aggregate Δσ_t = σ_t - σ_{t-1}:

R1. R_status        = Σ σ_t                              (= Σ Δσ_t × (n−t+1)) — current
R2. R_final         = σ_n                                  (= Σ Δσ_t, no weight) — only end matters
R3. R_inv_step      = Σ Δσ_t / t                           (strong early bias, flat steps = 0 contrib)
R4. R_linear        = Σ Δσ_t × (1 − (t−1)/n)               (linear early bias)

These differ in how they treat:
- Flat-σ steps (where Δσ = 0): R1 still adds σ_t (carry-forward credit). R2/R3/R4 add nothing.
- Late improvements: R1 partial penalty. R3 strong penalty (× 1/n at last step). R2 no penalty.
"""

from __future__ import annotations
import sys
from pathlib import Path

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

def deltas(start, path, scope, world):
    o = set(start)
    prev = sigma_sum(frozenset(o), scope, world)
    out = []
    for i in path:
        o.add(i)
        cur = sigma_sum(frozenset(o), scope, world)
        out.append(cur - prev)
        prev = cur
    return out

def sigma_traj(start, path, scope, world):
    o = set(start)
    out = []
    for i in path:
        o.add(i)
        out.append(sigma_sum(frozenset(o), scope, world))
    return out

def R_status(start, path, scope, world):
    return sum(sigma_traj(start, path, scope, world))

def R_final(start, path, scope, world):
    return sigma_traj(start, path, scope, world)[-1] if path else 0

def R_inv_step(start, path, scope, world):
    d = deltas(start, path, scope, world)
    return sum(dx / (t+1) for t, dx in enumerate(d))

def R_linear(start, path, scope, world):
    n = len(path)
    d = deltas(start, path, scope, world)
    return sum(dx * (1 - t/n) for t, dx in enumerate(d))

FORMULAS = [
    ('R1. R_status      ', R_status, 'Σ σ_t                            (current)'),
    ('R2. R_final       ', R_final, 'σ_n                              (only final state)'),
    ('R3. R_inv_step    ', R_inv_step, 'Σ Δσ_t / t                       (strong early)'),
    ('R4. R_linear      ', R_linear, 'Σ Δσ_t × (1 − (t−1)/n)            (linear early)'),
]

def beam_search(start, scope, world, R_fn, beam=50):
    pool = scope - start
    n = len(pool)
    frontier = [([], frozenset(start))]
    while frontier and len(frontier[0][0]) < n:
        nxt = []
        for path, owned in frontier:
            for i in pool - owned:
                nxt.append((path + [i], owned | {i}))
        nxt.sort(key=lambda it: R_fn(start, it[0], scope, world), reverse=True)
        frontier = nxt[:beam]
    return frontier[0][0] if frontier else []

def report_scenario(label, goal_names, world, scope_extras=(), beam=50):
    print('━' * 100)
    print(f"{label}")
    goals = [world.by_name[n] for n in goal_names]
    req = required_ings(goals)
    extras = frozenset(world.name_to_idx[n] for n in scope_extras)
    scope = frozenset(req | extras)
    print(f"  Goals: {goal_names}")
    if scope_extras: print(f"  Extras: {list(scope_extras)}")
    print(f"  scope size: {len(scope)}, beam K: {beam}")
    print('━' * 100)

    results = []
    for name, fn, desc in FORMULAS:
        p = beam_search(frozenset(), scope, world, fn, beam=beam)
        results.append({
            'name': name, 'desc': desc, 'path': p,
            'R': fn(frozenset(), p, scope, world),
            'traj': sigma_traj(frozenset(), p, scope, world),
            'deltas': deltas(frozenset(), p, scope, world),
        })

    print(f"\n  {'formula':<22}{'description':<48}{'R':<12}")
    for r in results:
        if isinstance(r['R'], float):
            print(f"  {r['name']}{r['desc']:<48}{r['R']:<12,.1f}")
        else:
            print(f"  {r['name']}{r['desc']:<48}{r['R']:<12,}")

    print(f"\n  Paths:")
    for r in results:
        seq = ' → '.join(world.ingredients[i] for i in r['path'])
        # mark extras
        if scope_extras:
            marks = []
            for idx, i in enumerate(r['path']):
                name = world.ingredients[i]
                marks.append(f"[{idx+1}]{name}" if name in scope_extras else name)
            seq = ' → '.join(marks)
        print(f"  {r['name']}: {seq}")

    print(f"\n  σ trajectories:")
    for r in results:
        print(f"  {r['name']}: {r['traj']}")

    print(f"\n  Δσ per step:")
    for r in results:
        print(f"  {r['name']}: {r['deltas']}")
    print()

def main():
    world = load_world(Path(__file__).resolve().parent.parent / 'data.json')

    report_scenario(
        "SCENARIO 1: Coffee 3, no extras",
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, scope_extras=(), beam=50,
    )

    report_scenario(
        "SCENARIO 2: Coffee 3 + Set A extras (火辣香草, 特選蘋果, 萌綠玉米)",
        ['覺醒力量濃湯', '不服輸咖啡沙拉', '土王閃電泡芙'],
        world, scope_extras=['火辣香草', '特選蘋果', '萌綠玉米'], beam=50,
    )

    report_scenario(
        "SCENARIO 3: Avocado 3, no extras",
        ['茂盛焗烤酪梨', '重踏酪梨醬脆片', '採蜜巧克力格子鬆餅'],
        world, scope_extras=(), beam=50,
    )

if __name__ == '__main__':
    main()
