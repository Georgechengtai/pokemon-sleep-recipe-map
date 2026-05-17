#!/usr/bin/env python3
"""
test_algorithms.py — verify recommender + planner logic against known ground truth.

Ground truth from CLAUDE.md §1.4:
  咖啡畢業 (+61%) 3道: 覺醒力量濃湯, 不服輸咖啡沙拉, 土王閃電泡芙
  酪梨畢業 (+78%) 3道: 茂盛焗烤酪梨, 重踏酪梨醬脆片, 採蜜巧克力格子鬆餅
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = json.loads((ROOT / "data.json").read_text())

ingredients = DATA["ingredients"]
recipes     = DATA["recipes"]
incidence   = DATA["incidence"]   # 19 × 79

ing_idx = {ing["name"]: i for i, ing in enumerate(ingredients)}

PASS = "✅"
FAIL = "❌"
errors = 0


def check(label, cond, detail=""):
    global errors
    if cond:
        print(f"{PASS} {label}")
    else:
        print(f"{FAIL} {label}{': ' + detail if detail else ''}")
        errors += 1


# ── Data integrity ──────────────────────────────────────────────
def test_data():
    check("19 種食材", len(ingredients) == 19)
    check("79 筆食譜（含 3 個佔位符）", len(recipes) == 79)
    real = [r for r in recipes if not r["is_placeholder"]]
    check("76 道真實料理", len(real) == 76)
    tiers = sorted(set(r["tier_bonus"] for r in real))
    check("階級 9 段", len(tiers) == 9, str(tiers))
    check("最高階 0.78", 0.78 in tiers)
    check("incidence 19×79", len(incidence) == 19 and all(len(row) == 79 for row in incidence))


# ── Planner — set union required ingredients ─────────────────────
def required_ingredients(target_recipes):
    names = set()
    for r in target_recipes:
        for i in r["ingredients"]:
            names.add(i["name"])
    return {ing_idx[n] for n in names if n in ing_idx}


def top_n_per_type(tier_ge: float, n: int):
    types = ["curry", "salad", "dessert"]
    result = []
    for t in types:
        pool = sorted(
            [r for r in recipes if not r["is_placeholder"] and r["type_en"] == t and r["tier_bonus"] >= tier_ge],
            key=lambda r: -r["score_final"]
        )
        result.extend(pool[:n])
    return result


def test_planner():
    # +78% top-1: 3 recipes, 9 ingredients
    target_78_1 = top_n_per_type(0.78, 1)
    check("+78% top-1 = 3 道", len(target_78_1) == 3,
          str([r["name"] for r in target_78_1]))
    need_78_1 = required_ingredients(target_78_1)
    check("+78% top-1 需要 9 種食材", len(need_78_1) == 9,
          str([ingredients[i]["name"] for i in sorted(need_78_1)]))

    # Verify specific ingredient set
    expected_78_1 = {"嫩亮酪梨", "窩心洋芋", "哞哞鮮奶", "純粹油",
                     "萌綠玉米", "火辣香草", "萌綠大豆", "甜甜蜜", "放鬆可可"}
    actual_78_1 = {ingredients[i]["name"] for i in need_78_1}
    check("+78% top-1 食材組合正確", actual_78_1 == expected_78_1,
          f"got {actual_78_1 - expected_78_1} extra, missing {expected_78_1 - actual_78_1}")

    # +61% top-1: filter picks highest-score per type at ≥61%, which means
    # curry = 茂盛焗烤酪梨 (+78%), salad = 大塊滿滿熱水沙拉 (+61%), dessert = 採蜜巧克力格子鬆餅 (+78%)
    target_61_1 = top_n_per_type(0.61, 1)
    names_61_1 = [r["name"] for r in target_61_1]
    check("+61% top-1 咖哩 = 茂盛焗烤酪梨", "茂盛焗烤酪梨" in names_61_1)
    check("+61% top-1 點心 = 採蜜巧克力格子鬆餅", "採蜜巧克力格子鬆餅" in names_61_1)
    need_61_1 = required_ingredients(target_61_1)
    # Union: {嫩亮酪梨,窩心洋芋,哞哞鮮奶,純粹油} ∪ {沉甸甸南瓜,窩心洋芋,萌綠玉米,品鮮蘑菇} ∪ {甜甜蜜,萌綠玉米,純粹油,放鬆可可} = 9
    check("+61% top-1 需要 9 種食材（score-sorted）", len(need_61_1) == 9,
          str({ingredients[i]["name"] for i in need_61_1}))

    # Gap: if owned = {哞哞鮮奶, 窩心洋芋} (both in need set), gap should be 7
    owned_test = {ing_idx["哞哞鮮奶"], ing_idx["窩心洋芋"]}
    gap = need_61_1 - owned_test
    check("+61% top-1 gap with 2 owned = 7", len(gap) == 7)


# ── Recommender — greedy marginal gain ───────────────────────────
def greedy_top3(owned: set[int], tier_ge: float = 0.48) -> list[dict]:
    active = [r for r in recipes if not r["is_placeholder"] and r["tier_bonus"] >= tier_ge]

    def completion(owned_set, recipe):
        return all(
            ing_idx.get(i["name"], -1) in owned_set
            for i in recipe["ingredients"]
        )

    def frac_completion(owned_set, recipe):
        total = len(recipe["ingredients"])
        have = sum(1 for i in recipe["ingredients"] if ing_idx.get(i["name"], -1) in owned_set)
        return have / total if total else 0

    candidates = []
    for ci in range(19):
        if ci in owned:
            continue
        trial = owned | {ci}
        binary_gain = sum(
            1 for r in active
            if not completion(owned, r) and completion(trial, r)
        )
        frac_gain = sum(
            (frac_completion(trial, r) - frac_completion(owned, r)) * r["score_final"] / 10000
            for r in active
        )
        new_recipes = [r for r in active if not completion(owned, r) and completion(trial, r)]
        candidates.append({"idx": ci, "binary_gain": binary_gain, "frac_gain": frac_gain, "new_recipes": new_recipes})

    candidates.sort(key=lambda c: (-c["binary_gain"], -c["frac_gain"]))
    return candidates[:3]


def test_recommender():
    # Empty owned → binary gain = 0 for all (need 4 ings to complete any recipe).
    # Ranking falls to frac_gain weighted by score_final.
    # At +48% (20 recipes), 萌綠玉米 wins by frac_gain (appears in high-score +78% recipes).
    top3_empty = greedy_top3(set(), 0.48)
    check("空 owned 能計算 top-3", len(top3_empty) == 3)
    check("空 owned 所有候選 binary_gain = 0（需 4 種食材才能完成料理）",
          all(c["binary_gain"] == 0 for c in top3_empty))
    top_ing = ingredients[top3_empty[0]["idx"]]["name"]
    check(f"空 owned top-1 = 萌綠玉米（frac_gain 最高）（got {top_ing}）",
          top_ing == "萌綠玉米")

    # Owned = all but one → that one should be top pick
    all_but_18 = set(range(18))  # all except index 18 (嫩亮酪梨)
    top3_all = greedy_top3(all_but_18, 0.48)
    check("已有 18 種時 top-1 是剩餘食材", top3_all[0]["idx"] == 18,
          f"got {ingredients[top3_all[0]['idx']]['name']}")

    # Owned = {哞哞鮮奶} at +78% — binary_gain still 0 (need 4 ings to complete)
    # but frac_gain > 0 (partial completion improves)
    owned_one = {ing_idx["哞哞鮮奶"]}
    top3_one = greedy_top3(owned_one, 0.78)
    check("有哞哞鮮奶時所有候選 binary_gain = 0（+78% 料理都需要 ≥ 4 食材）",
          all(c["binary_gain"] == 0 for c in top3_one))
    check("有哞哞鮮奶時 top-1 frac_gain > 0（能增進部分完成度）",
          top3_one[0]["frac_gain"] > 0)

    # Submodularity spot-check: gain of x given {} ≥ gain of x given {anything}
    empty_gains = {c["idx"]: c["binary_gain"] for c in greedy_top3(set(), 0.78)}
    one_gains   = {c["idx"]: c["binary_gain"] for c in greedy_top3(owned_one, 0.78)}
    # The top pick with empty set should have gain ≥ its gain with more owned
    top_idx = max(empty_gains, key=empty_gains.get)
    if top_idx in one_gains:
        check("次模性：gain({x}|∅) ≥ gain({x}|{哞哞鮮奶})",
              empty_gains[top_idx] >= one_gains[top_idx])


# ── Run ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== Algorithm Unit Tests ===\n")
    print("── Data integrity ──")
    test_data()
    print("\n── Planner (set cover) ──")
    test_planner()
    print("\n── Recommender (greedy marginal gain) ──")
    test_recommender()
    print()
    if errors:
        print(f"FAILED: {errors} test(s) failed")
        sys.exit(1)
    else:
        print(f"All tests passed.")
