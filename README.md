# 寶睡料理食材圖 | Pokémon Sleep Recipe Map

給 Discord 寶睡社群玩家用的**單頁互動工具**，秒看食材跟料理的關係、找出下一個該抓的食材。

**[→ 打開工具](https://your-github-pages-url)**（GitHub Pages，手機也能用）

---

## 這個工具在解什麼問題

寶睡的 19 種食材 × 76 道料理構成一個二部圖。玩家常見的困惑：

- 我現在有這些食材，能做哪些料理？
- 下一個該養哪個食材手？抓哪個解鎖最多料理？
- 我想衝 +78% 頂級三系畢業，還差幾種食材？

這個工具提供三個同步面板回答這三個問題。

---

## 功能說明

### 🗺 Map Panel — 食材 × 料理矩陣
- **19×N 二部圖矩陣**，食材為列（SVD spectral 排序），料理為欄（按類型分色）
  - 🟠 橙色 = 咖哩／濃湯　🟢 綠色 = 沙拉　🩷 粉色 = 點心／飲料
- Hover 食材 → 該食材出現的所有料理高亮，右側共現矩陣同步標記
- Hover 料理 → 所需食材高亮
- **點食材** = 切換「已有」狀態（綠色 = 你已有）
- 右側 19×19 **共現矩陣**：哪些食材經常同時出現在同一道料理

### 💡 Recommender Panel — 下一個食材推薦
- 選完你已有的食材後，顯示 top-3 推薦
- 演算法：**greedy marginal gain**（次模函數最大化，Nemhauser-Wolsey-Fisher 1978）
  - 有料理可以直接解鎖 → 顯示「+N 道」
  - 還差多個食材 → 顯示「+X 進度」（fractional completion × score 加權）

### 🎯 Planner Panel — 畢業路徑規劃
- 選目標階級（+25% ~ +78%）和每系列幾道（最高 1 / 前 3 / 全部）
- 自動計算需要哪些食材、你還差幾種
- 點 badge 可直接加入「已有」

### 互動聯動
Hover 或點任何食材 → 三個面板同步高亮。

### ⚙ Construction Kit
右下角「調整」按鈕 → 即時拖滑桿改格子大小、間距、顏色，無需改程式碼。

---

## 如何使用

1. 在 **Recommender** 的食材選擇器點選你已有的食材（或直接點矩陣左側的食材名）
2. 看右側推薦面板：top-3 裡優先去抓 **+N 道** 最大的那個
3. 切換 Planner 的目標階級，看「還缺幾種食材」決定換島策略

---

## 資料來源

- 食材 / 料理數據：`Pokemon Sleep Recipe.xlsx`（Wallace 整理，格子鬆餅更新後版本）
- 圖片：[Serebii Pokémon Sleep](https://www.serebii.net/pokemonsleep/)（hotlink）
- 演算法實作：純 JavaScript，無外部依賴

---

## 本地執行

```bash
# 任一 HTTP server 都行，不能直接雙擊 HTML（fetch data.json 需要 HTTP）
python3 -m http.server 8080
# 然後打開 http://localhost:8080
```

---

## 開發

```bash
# 資料更新（Excel 改了之後重跑）
python3 scripts/prep_data.py

# 演算法單元測試
python3 scripts/test_algorithms.py

# 視覺驗證（failsafe 用，互動時優先用 Chrome MCP）
python3 scripts/visual_check.py index.html
```

**P1 視覺驗證流程**：日常互動由 Claude 直接驅動 Chrome MCP（navigate / resize / screenshot / JS exec），`visual_check.py` 只是 pre-commit hook 的 headless fallback。

---

*分析框架詳見 [CLAUDE.md](CLAUDE.md) · 工具規格詳見 [RECIPE_NETWORK_HANDOFF.md](RECIPE_NETWORK_HANDOFF.md)*
