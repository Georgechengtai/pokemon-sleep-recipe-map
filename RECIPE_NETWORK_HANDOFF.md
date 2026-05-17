# 寶睡食材-料理視覺化工具 — Handoff to Claude Code

**作者：** Wallace + Claude (Cowork)
**日期：** 2026-05-16
**狀態：** Cowork 階段告一段落，準備轉 Claude Code 做正式版
**Repo 起點：** `/Users/yingtaicheng/Claude Cowork/Pokemon Sleep/`

---

## 不可妥協原則（兩條，整個專案都要守）

**P1 — 視覺自我驗證是必要條件，不是 nice-to-have**

Claude Code 改任何 HTML / CSS / 視覺輸出後，**必須**：
1. 用 Chrome MCP（優先）或 playwright（fallback）開啟頁面截圖
2. 自己看完截圖
3. 發現明顯 UI 問題自己修
4. 通過視覺檢查才能交給 Wallace 評估

**Wallace 不負責抓「字反轉」「節點重疊」「label 撞在一起」這類 UI bug。** 如果他看到這類問題，代表 Claude Code 跳過了 P1。Cowork 階段就是因為跳過 P1 才浪費掉好幾輪迭代。

實作方式：
- 寫一個 `scripts/visual_check.py`（playwright）或 `scripts/visual_check.sh`（呼叫 Chrome MCP）
- 每個 PR / commit 都跑這個 + 把截圖貼進 commit message 或 PR description
- 截圖看不出問題的，也要有「我看過了」的痕跡

**P2 — 任何 UI 元素都要可以在頁面內即時調整，不要每次都改程式碼**

每個 panel（Map / Recommender / Planner）右側都帶一個**Construction Kit**（摺疊式面板），列出該 panel 所有可調參數的滑桿 / toggle / 下拉：
- 顏色 / 透明度 / 線粗 / 字體大小
- 演算法參數（biclustering 用哪個 ordering、recommender 的 weight function、planner 的 breadth）
- Layout 參數（panel 寬度、cell 大小、padding）

這樣 Wallace（或 Claude）想試「字大一點」「對比強一點」「matrix cell 換成正方形」這類調整，**直接拖滑桿即時看到結果**，不需要 commit → reload → wait。

Cowork 階段的 v4 視覺工具箱是這個概念的雛形，正式版要每個 panel 都有自己的工具箱、能 export 當前設定到 URL hash 讓設定可分享 / 收藏。

---

## 0. 一句話定位

一個給 Discord 寶睡（Pokemon Sleep）社群玩家用的**單頁網頁工具**，讓玩家
**一眼看出食材跟料理的關係**，輔助回答：

- 我手上養成了哪幾個食材手，現在能做哪些料理？
- 下一個該抓 / 該練的食材手是什麼？ — 抓哪個能解鎖最多料理？
- 我想做這道高 CP 料理，還缺什麼？
- A / B 換島路線（見同 folder 的 CLAUDE.md）對我食材手累積數的影響？

**目標玩家：** 食材手累積數在 9–13 區間的玩家（從起步區到雙系畢業之間）。
不是已經滿配的 60AAA 玩家。

---

## 1. 真正的問題（Why）

寶睡的食材-料理結構是個典型的**二部圖（bipartite graph）**：
- 一邊是 **19 種食材**（如：醒腦咖啡豆、嫩亮酪梨、放鬆可可…）
- 另一邊是 **76 道料理**（76 = Excel 內的 row count）
- 每道料理由 **最多 4 種食材**（含數量）組成
- 料理分 **3 系**（咖哩濃湯 / 沙拉 / 點心飲料）×
  **9 個階級獎勵 tier**（+16%, +19%, +20%, +21%, +25%, +35%, +48%, +61%, +78%）

玩家的核心決策難點：

1. **跨系列共用食材**：很多食材（哞哞鮮奶、純粹油、甜甜蜜）在三系都被大量使用，
   抓這類食材的邊際效益高 — 但目前沒視覺工具能秒看出來
2. **路徑依賴**：上一階段料理用的食材組合可能跟下一階段截然不同
3. **抓食材的機會成本**：選 A 食材就等於沒選 B 食材（受睡姿、島嶼、捕捉次數限制）

整本 CLAUDE.md 描述的「A/B 路線分析」就是這個問題的策略層；
這個視覺化工具是**戰術層的決策輔助**。

---

## 2. 資料來源（已就位）

### 2.1 主檔案 — `Pokemon Sleep Recipe.xlsx`（folder 內）

| Sheet | 內容 | 行數 |
|-------|------|------|
| `食材` | 19 種食材的 ID / 中英文名 / 基礎分 / 開放日期 / 內嵌圖片（15 張） | 19 |
| `食譜` | 76 道料理：名稱、英文代號、系列、tier、純食材分、加成後總分、4 個食材 + 數量 | 76 |
| `食譜橫向排版` | 同食譜的視覺版 | — |

**重要欄位（食譜 sheet）：**
- column B (`食譜名`) — 中文名
- column C (`名`) — 英文代號（如 `mixedsalad`、`defiantcoffee-dressedsalad`），**用來組 Serebii 圖片 URL**
- column E (`類型`) — `咖哩、濃湯` / `沙拉` / `點心、飲料`
- column F (`階級獎勵`) — float 0.16 ~ 0.78
- column H (`加成後`) — int 總分
- column J/L/N/P — 食材 1~4 名稱
- column K/M/O/Q — 各食材數量

**重要欄位（食材 sheet）：**
- column A — ID 1~19
- column B — 中文名
- column C — 英文名（如 `Greengrass Soybeans`）
- column F — 基礎分（90 ~ 342）
- column D — 內嵌 jpg 圖片（drawing3.xml 對應 row 1-15，row 16-19 後加入的食材沒有圖）

### 2.2 圖片資源

**Serebii hotlink（推薦，不下載）：**
```
食材：https://www.serebii.net/pokemonsleep/ingredients/{lower(name_en).replace(' ','')}.png
       例：https://www.serebii.net/pokemonsleep/ingredients/greengrasssoybeans.png
料理：https://www.serebii.net/pokemonsleep/meals/{name_en_code}.png
       例：https://www.serebii.net/pokemonsleep/meals/mixedsalad.png
```
跟 Excel 自帶的 `=IMAGE("...")` 公式是同一個來源，瀏覽器直接 fetch。

**本地 fallback：** `assets/` folder 內有 15 張食材 jpg（從 Excel 抽出，命名格式 `large_leek.jpg`）。
4 個沒圖的食材：萌綠玉米 / 醒腦咖啡豆 / 沉甸甸南瓜 / 嫩亮酪梨 — 後加的食材，Excel 沒收。

### 2.3 預處理腳本（已寫過，可重用）

從 Excel → JSON 的 Python 腳本邏輯（用 openpyxl）：
```python
import openpyxl, json
wb = openpyxl.load_workbook('Pokemon Sleep Recipe.xlsx', data_only=True)
# 解析食譜 sheet：row 3+ → name, name_en, type, tier_bonus, score_final, ingredients[]
# 解析食材 sheet：row 2+ → id, name, name_en, base_score
# 加入 Serebii URL + emoji + 本地 fallback path
```
參考現存的 `_data.js`（folder 內，已生成好的 JSON literal，可直接用）。

---

## 3. 過去 6 個版本學到了什麼

### v1–v2：3D 力導向圖（3d-force-graph CDN）
- **結論：CDN 不可靠**。unpkg / jsdelivr / cdnjs / esm.sh 都會被某些網路擋
- **結論：3D 是炫技 ≠ 教學工具**。19 個節點根本不需要 3D 旋轉
- **保留：** 力導向佈局是 OK 的概念，但 2D 就夠

### v3：邊 + 多邊形外框
- 每道料理 4 個食材 → 6 條兩兩邊 → 用一個半透明多邊形連起來
- **結論：5 道以內可讀，超過就糊**。多邊形堆疊 = 視覺垃圾
- **保留：** 多邊形作為 hover 觸發的「探照燈」效果還可以

### v4：聚焦檢視（食材中心 + 料理花瓣）
- 點食材 → 跳到放射圖：該食材在中央、料理像花瓣繞一圈
- **結論：花瓣模式 10 道以上重疊** ；放射不是好佈局
- **保留：** 「點食材跳放射」的互動模式對玩家直覺

### v5：路徑模式（每道料理 = 一條 4 點線）
- 食材按 **co-occurrence 頻次降序**排列，料理變成 trie-like 共享前綴的線
- 演算法名稱：**seriation / consensus ordering**，是 Steiner-tree 的貪心啟發式
- **結論：概念對，但實作起來標籤滿天飛、線重疊**
- **保留：** 排序演算法是正確的（共用食材在線頭）

### v6：5-tab 多視圖探索器（矩陣 / 弦圖 / 2D 網路 / 卡片 / 聚焦同心圓）
- 目標：讓使用者比較 4 種視覺化典範哪個對胃口
- **結論：**
  - **矩陣** — 最資訊密度高，但欄位標題（vertical-rl + rotate(180deg)）會反轉，是 CSS 陷阱
  - **弦圖** — 視覺漂亮但 76 條 ribbon 無法辨識單道料理；spotlight mode 必要
  - **2D 網路** — 力導向參數沒調好會塌陷成一團；標籤要避免重疊
  - **卡片** — 最易讀但失去網路結構
  - **聚焦同心圓** — 概念好（角度=系列、半徑=tier）但實作沒做對

### 視覺自我驗證的失敗
- Cowork 環境的 Chrome MCP 無法從 `chrome://newtab/` navigate 出去
- sandbox 也擋 pip / npm registry，裝不了 playwright
- **結果：** Cowork 階段我（Claude）沒能視覺驗證自己的輸出，玩家（Wallace）變成 QA
- **Claude Code 應該優先解決：** headless screenshot workflow（playwright 或 puppeteer 應該能裝）

---

## 4. 目前已驗證可用的技術選擇

1. ✅ **純 SVG / DOM 渲染**（不用 canvas），圖片 hotlink 穩定
2. ✅ **單一 HTML + 一個 _data.js**，雙擊就能跑
3. ✅ **Serebii URL 模式**：`<img src="https://www.serebii.net/...">` 可跨 origin 載入
4. ✅ **co-occurrence frequency sort** 解 trie 共享前綴問題
5. ✅ **tier 篩選按鈕** UX：5 段、預設只開 +48% 以上
6. ❌ **canvas drawImage + crossOrigin='anonymous'** ← 別用，會被 CORS 拒
7. ❌ **3D force-directed for 19 nodes** ← 別用，過度設計
8. ❌ **多邊形料理外框 default-on** ← 別用，超過 5 道就糊

---

## 5. 工具規格 — 三個目標、三個面板、一個頁面

Wallace 明確列出的三個目標，每個對應一個演算法問題：

| 目標 | 玩家視角 | 對應數學問題 | 對應面板 |
|------|----------|--------------|----------|
| G1 | 「探索食材-料理關係」 | bipartite hypergraph 結構視覺化 | **Map Panel** |
| G2 | 「我有這些食材，下一個該抓什麼？」 | submodular maximization / greedy marginal gain | **Recommender Panel** |
| G3 | 「最少步數達成三系畢業」 | set cover with category constraint | **Planner Panel** |

**重要結論：不要再做多 tab 切換**。三個面板**同時可見**在一個頁面上，
linked highlighting（互動聯動），這是 multi-coordinated-view 標準做法（Roberts 2007）。

```
┌─────────────────────────────────────────────────────────────────┐
│  Top bar: tier filter · search · owned-ingredient picker (19)   │
├──────────────────────────────────┬──────────────────────────────┤
│                                  │  Recommender (G2)            │
│                                  │  ─ Owned: 5 / 19            │
│   Map Panel (G1)                 │  ─ Recipes complete: 3 / 76 │
│   ─ Biclustered matrix 19×76     │  ─ Suggested next ingredient:│
│   ─ Side: 19×19 co-occurrence    │     1. 醒腦咖啡豆 +12 recipes │
│     (updates on row hover)       │     2. 哞哞鮮奶   +8         │
│                                  │     3. 純粹油    +6          │
│                                  ├──────────────────────────────┤
│                                  │  Planner (G3)                │
│                                  │  Target: ☑ 三系畢業 @ +78%   │
│                                  │  Required ingredients: 11    │
│                                  │  You have: 4 / 11            │
│                                  │  Still need: [list]          │
└──────────────────────────────────┴──────────────────────────────┘
```

Hover/click 在任一面板 → 其他面板對應元素亮起來。

### 5.1 Map Panel — Goal 1：結構探索

**主視圖**：Spectral biclustered 19×76 incidence matrix.

**演算法**：
```
M = 19×76 binary incidence matrix (M[i,j] = 1 if recipe j uses ingredient i)
D_r = diag(row sums of M)        # ingredient degree
D_c = diag(col sums of M)        # recipe degree (always 4 for full recipes)
A = D_r^(-1/2) M D_c^(-1/2)      # normalized

U, S, V = SVD(A)
# Use second smallest singular vector pair (u_2, v_2) as Fiedler-like ordering:
row_order = sort_indices_by(u_2)
col_order = sort_indices_by(v_2)
```

結果：行列重排後 1 自然聚集成 blocks。咖啡系食材排在一起、咖啡系料理排在一起。

**參考實作**：`numpy.linalg.svd` + indexing。19×76 < 10ms。
JS 端用 `numeric.js` 或寫一個極簡 SVD（19 是小資料）。

**互動**：
- Hover ingredient row → 該行所有 cells 亮起，**右側 19×19 co-occurrence 也亮起 row i**
- Hover recipe column → 該列 cells 亮起，bottom 顯示料理名
- 玩家勾選「已有食材」→ 該行被標記，cells 變綠

**輔助視圖**：Ingredient co-occurrence 19×19，跟主矩陣並排或浮動。
`C = M · Mᵀ`，cell[i,j] = i 和 j 共同出現的料理數。對稱矩陣，hover cell 看共享料理列表。

**可選 (showcase only)**：3D bipartite force-directed。**不是主視圖**。
若做，stable layout：食材按 degree 排在內球面、料理當衛星，避免 free force collapse 問題。
Phase 3 完成後再加，不阻擋 v1 發布。

### 5.2 Recommender Panel — Goal 2：下一個食材建議

**目標數學**：給定玩家持有食材集合 P ⊆ Ingredients，求 next pick 使邊際效益最大。

**演算法（greedy marginal gain）**：
```
For each candidate ingredient x ∉ P:
    gain(x) = Σ over recipes R:
        weight(R) × [completion(P ∪ {x}, R) - completion(P, R)]

where:
    completion(S, R) = 1 if R.ingredients ⊆ S else 0    # binary version
    weight(R) = R.score_final × tier_multiplier         # higher tier weight more

Recommend top-3 by gain(x)
```

**進階變體（fractional completion）**：
```
completion(S, R) = |R.ingredients ∩ S| / |R.ingredients|
gain(x) = "expected score added" 把所有「再加一個食材會完成的料理」也算進來
```

**輸出**：top-3 食材推薦，每個顯示「能讓 N 道料理變得可做」+ 那些料理列表。

數學名詞：submodular function maximization（greedy 有 1-1/e ≈ 0.63 近似保證，by Nemhauser-Wolsey-Fisher 1978）。對 19 個 candidates × 76 recipes 的小資料，greedy 直接得最佳解附近。

### 5.3 Planner Panel — Goal 3：trinity 畢業路徑

**目標數學**：給定目標料理集合 U（例如：三系各最高 tier 料理），求最小食材集合 S 使每道 R ∈ U 滿足 R.ingredients ⊆ S。

**演算法（exact set union, no optimization needed for fixed target）**：
```
function required_ingredients(target_recipes):
    return ∪ (R.ingredients for R in target_recipes)

function trinity_at_tier(t):
    return [top recipe per type with tier_bonus >= t]

# Example: trinity at +78%
target = trinity_at_tier(0.78)
need = required_ingredients(target)  # union of 3 recipes' ingredients
gap = need \ player_owned             # what's still missing
```

**Variants**：
- 「最寬鬆」：target = top-1 recipe per type at top tier → 約 9-12 個食材
- 「次寬」：target = top-3 recipes per type → 約 13-15 個食材
- 「完全」：target = all +78% recipes → 約 17 個食材

**UI**：滑桿選擇 target tier 跟 breadth（單道 / 前 3 / 全部），即時顯示 need set 跟 gap。

**進階（multi-target Steiner-like）**：
如果 player 想 minimize steps to reach multiple disjoint targets，這是 NP-hard 的 weighted set cover。對 19 食材小資料，ILP（Python `pulp` 或 JS `glpk.js`）秒解。v1 不必，v2 加。

### 5.4 Cross-panel linked highlighting

- Hover ingredient anywhere → 三個面板都把它高亮
- Click ingredient in any panel → 加入 / 移除 owned set
- Select recipe → 三個面板都把它高亮
- Tier filter 改變 → 三個面板同步重算

這是 multi-coordinated-view 的核心模式，比 tab 切換好太多。

---

## 6. 技術備忘 / 陷阱

| 問題 | 別這樣 | 應該 |
|------|--------|------|
| 中文垂直字反轉 | `writing-mode: vertical-rl; transform: rotate(180deg);` | `writing-mode: vertical-rl; text-orientation: upright;` |
| 圖片載不到 canvas | `img.crossOrigin = 'anonymous'` | 不設 crossOrigin，drawImage 仍可用（只是 canvas tainted） |
| 力導向塌陷 | gravity 0.005 + spring 100 | gravity 0.002 + spring 200，repulsion 30000 |
| SVG 寬高比浪費 | 1000×1000 viewBox 在寬螢幕 | 用螢幕比 1400×900 之類 |
| CDN 不可靠 | 依賴 unpkg / jsdelivr | inline 或 pure JS，最多一個輕量 lib |

---

## 7. Claude Code 接手的建議起手式

**Phase 0 — 環境（半天）**
1. 新建 git repo（最終目標 GitHub Pages 公開）
2. 把這個 folder 全部 commit 進去：xlsx、`_data.js`、`assets/`、CLAUDE.md、這份 handoff
3. `.gitignore` 排除 Cowork 階段的舊 HTML（保留作為歷史 ref，不阻擋新版開發）

**Phase 1 — Self-QA 基礎設施（半天，P1 強制執行）**
這個 phase 不通過，其他 phase 一律不准動。

優先順序：
1. **Chrome MCP** — 在 Claude Code 環境試 `mcp__Claude_in_Chrome__*`，能用就優先用
2. **Playwright fallback** — `pip install playwright && playwright install chromium`
3. 寫 `scripts/visual_check.py`：HTML → headless → 截圖 5 個視角（desktop wide / desktop narrow / tablet / mobile / 各 panel 單獨）→ 存 `screenshots/{commit_hash}/`
4. 加 git pre-commit hook：HTML 有改動就要求附最新截圖

**驗證 phase 1 通過 = Claude Code 能用 `scripts/visual_check.py index.html` 拿到至少 5 張截圖、且自己看完能描述出畫面內容**（不能只是「跑成功」就算）。

**Phase 2 — Data 預處理（1 小時）**
寫 `scripts/prep_data.py`：讀 Excel → 輸出 `data.json`（不用 `_data.js` 包成 JS literal，純 JSON 比較乾淨）。
JSON schema 同 §2.3。

**Phase 3 — 三面板架構 v1（2-3 天）**
不要碰舊的 v6 explorer，從零開始 `index.html`。實作優先順序：

1. **Construction Kit shell**（先做這個！P2 強制） — 一個 collapsible side panel + 一套 binding helper (`<input type=range>` ↔ CSS var ↔ JS state)。先做 framework，後面 panel 加參數時直接掛上去
2. **Map Panel** 的 biclustered matrix（§5.1） — 純展示，無互動
   - 寫一個極簡 JS SVD（19×76 的 power iteration 也行）或 use ML library
   - 矩陣渲染：SVG 或 DOM CSS Grid，cell hover 顯示用量
   - **Construction Kit 掛上**：cell 大小、顏色、字體、行列 ordering 算法選擇
3. **Recommender Panel**（§5.2） — owned ingredient picker + top-3 推薦
   - **Construction Kit 掛上**：marginal gain 的 weight function（binary/fractional/tier-weighted）、top-N 顯示數量、推薦字體
4. **Planner Panel**（§5.3） — target tier 滑桿 + need / gap 顯示
   - **Construction Kit 掛上**：breadth 模式預設、need set 排序方式
5. **Linked highlighting**（§5.4） — hover/click 三面板聯動
6. Co-occurrence 19×19 inset 加在 Map Panel 旁

每加一個功能 → 跑 `scripts/visual_check.py` → 看截圖 → 確認 OK 才繼續下一個。

**Phase 4 — Polish + 發布（1-2 天）**
- 玩家 owned set 存到 URL hash（分享連結）
- Mobile responsive（Discord 玩家會用手機）
- GitHub Pages 部署
- README 寫好讓玩家「打開就會用」

**Phase 5 — Optional 進階（如有時間）**
- 3D bipartite showcase view（§5.1 末尾）
- ILP-based 精確最少食材集合（§5.3 進階）
- 路徑模擬：給定 owned set + target，顯示推薦的「下三步」食材序列

---

## 8. 驗收條件（給 Claude Code 的「Done」定義）

對應三個 goal，每個列具體 acceptance：

### G1：探索食材-料理關係
1. ✅ 打開頁面 5 秒內看到 19×76 biclustered matrix，食材 cluster 視覺上明顯
2. ✅ Hover 任一食材 row → 該行 cells 亮、co-occurrence panel 該食材 row 同步亮
3. ✅ Hover 任一料理 col → 該列亮、底部顯示料理名 + 階級 + 總分
4. ✅ Tier filter button 過濾 → matrix col 變窄，重排不重 layout shift

### G2：下一個食材推薦
5. ✅ Owned ingredient picker：勾選 / 反勾立即生效
6. ✅ 推薦面板顯示 top-3 食材，每個帶「解鎖 N 道新料理」+ 料理列表
7. ✅ Empty state（owned=∅）顯示「先勾你已有的食材」提示
8. ✅ Full state（owned=all 19）顯示「全部達成」

### G3：Trinity 路徑優化
9. ✅ Tier 滑桿選 target（+25% / +35% / +48% / +61% / +78%）
10. ✅ Need set 即時顯示：列出需要的食材 + 共 N 個
11. ✅ Gap 顯示：你已有 X / N，還缺 [list]
12. ✅ Breadth toggle（top-1 / top-3 / all per type）改變 need set

### 跨 goal
13. ✅ 手機 viewport（375px 寬）不破版（Discord 多數人手機看）
14. ✅ 用 Serebii sprite，沒網路時 fallback 到本地 jpg 或 emoji
15. ✅ URL 含 owned set hash，玩家可分享自己進度的連結

### P1 / P2 強制 acceptance
16. ✅ **P1**：每個 PR 都有 `scripts/visual_check.py` 產生的至少 5 張截圖（desktop wide / narrow / tablet / mobile / 各 panel 單獨）
17. ✅ **P1**：commit message 或 PR description 有 Claude Code 自己「我看到了什麼」的文字描述（防止只跑沒看）
18. ✅ **P2**：三個 panel 各有自己的 Construction Kit，所有顏色 / 字體 / 大小 / 演算法選項都能即時拖動
19. ✅ **P2**：Construction Kit 設定可以序列化到 URL hash，玩家或 Wallace 能分享「我用這個配色看起來最舒服」的連結

### 給 Claude Code 自己的 checklist
- [ ] 每次 PR 前跑 `scripts/visual_check.py` + 看完截圖
- [ ] 數學算法都有 unit test（spectral 結果、marginal gain top-3、set cover need set 對得上 ground truth）
- [ ] 三面板都能獨立關閉 / 開啟（debug）
- [ ] Construction Kit 在頁面內可摺疊收起（玩家用時不擋畫面）
- [ ] Wallace 看 PR 時只需評估「資訊清不清楚」「演算法結果合不合理」，不評估「字體大小」「顏色對比」這類純 UI 議題（那些是 Claude Code 用 P1 + P2 自己解決的）

---

## 9. Folder Inventory（轉移時帶走）

```
/Pokemon Sleep/
├── CLAUDE.md                              # A/B 路線分析的原始 project doc
├── RECIPE_NETWORK_HANDOFF.md              # 這份檔案
├── Pokemon Sleep Recipe.xlsx              # 主資料來源（必帶）
├── Pokemon Sleep User Values v1.41.xlsx   # 個人配置檔（次要）
├── _data.js                               # 從 Excel 預處理出的 JSON literal（可用作起點）
├── assets/                                # 15 張食材 jpg（Excel 抽出）
│   ├── bean_sausage.jpg
│   ├── fancy_apple.jpg
│   └── ... (共 15 張)
├── pokemon_sleep_recipe_network.html      # v5.2 舊版（含 3D / 2D 切換）
└── pokemon_sleep_explorer_v6.html         # v6.2 最新但仍有問題（5 tab 多視圖）
```

舊 HTML 可以保留作參考，但**不要試圖在上面繼續改**。Claude Code 砍掉重寫。

---

## 10. 給 Wallace 自己的提醒

- 這個工具不必一次做完美。**「能用、能發 Discord 收 feedback」**比「演算法完美」重要
- 玩家不在意你用 trie 還是 chord diagram，他們在意「我能不能秒看出該抓什麼」
- 視覺化選擇沒有銀色子彈，**矩陣 + 卡片**這種樸素組合在實戰可能比花俏 3D 更有用
- 如果 Claude Code 又陷入「修不完的 bug」迴圈，**砍掉重來**比修補便宜

---

**結束。Claude Code 拿到這份檔，先讀完，再讀 CLAUDE.md，再問 Wallace §5 的 4 個問題，再動手。**
