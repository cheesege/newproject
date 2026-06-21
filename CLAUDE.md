# CLAUDE.md

> 本檔是給 **Claude Code** 的專案工作指引。開工前先讀本檔，再讀 `FEATURES.md`（完整遊戲願景與架構）與 `DEVELOPMENT_PLAN.md`（任務）。

## 專案是什麼

「**體感硬核健身房**」——一個**以使用者養成為核心**的體感健身遊戲。玩家用真實動作（深蹲、伏地挺身等）打怪，所有訓練成果累積到「他的角色」身上，化為一個會成長、會預測未來的數位分身。

本輪是一次**完整重構**：把原本各自獨立的功能，重新組織成一條通暢的遊戲動線（選擇/創建使用者 → 訓練 → 結算 → 成長），而不是把功能拼貼在一起。

## 重構的核心精神（最重要）

1. **使用者是骨幹。** 所有數據（身高體重、BMI、歷史紀錄、數位分身）都掛在某一位使用者身上，不漂浮在外。遊戲第一個畫面就是選擇/創建使用者。
2. **數位分身是養成的具象化，不是獨立面板。** 它是使用者訓練成果的鏡子，在主頁就看得到、在結算時看得到它因這場訓練成長。
3. **用 Scene 狀態機組織流程。** 主迴圈不該是一坨 if-else，而是把輸入與畫面交給「當前 Scene」。新增畫面 = 新增一個 Scene。
4. **保留舊版的好資產。** 怪物、雷射、爆炸、動作判定、中文渲染都很紮實，重構是把它們接進新骨架，不是丟掉重寫。

## 鐵則（不可違反）

1. **核心技術棧固定為 Python + OpenCV**（課程硬性要求）。不可改寫成 Web 前端或其他引擎。
2. **本輪可更動任何東西，包含舊程式碼**——但要保留上面說的「好資產」的行為與美術。
3. **採小步重構，每完成一步程式都要能啟動並運作。** 不允許交出跑不起來的中間狀態。建議先搭 Scene 骨架讓流程能空跑，再逐步把邏輯接進去。
4. **依賴從簡、離線優先。** 能用標準庫（`sqlite3`）就不要引入重套件；每新增依賴同步更新 `requirements.txt` 與 `README.md`。
5. **全程使用繁體中文（台灣用語）**：程式碼註解、UI 文字、commit、對話一律繁中。

## 技術棧

- Python 3.10+ / OpenCV (`cv2`) / MediaPipe Tasks `PoseLandmarker`（33 點，VIDEO 模式）/ NumPy
- 中文渲染：Pillow（透過 `text_utils.py`，**絕不直接用 `cv2.putText` 畫中文**）
- 資料：`sqlite3`（標準庫）／圖表：Matplotlib／音效：`pygame.mixer` 或 `simpleaudio`

## 架構分層（重構後要遵守）

```
Scene 層（狀態機）  → 各畫面：UserSelect/Hub/PreGame/Playing/Result/Trends/Twin
領域邏輯層          → Exercise(Strategy)/GameState/DigitalTwin/CalorieCalculator
資料層              → storage(SQLite)/User・Profile 模型
基礎設施層          → PoseDetector/CameraSource/text_utils/sounds
```

- **Scene 用 State 模式**：每個 Scene 有 `handle_input` / `update` / `draw` 與切換到下一個 Scene 的方式。`main.py` 精簡成初始化 + 狀態機主迴圈。
- **領域邏輯層是純邏輯**，不直接碰畫面與按鍵，方便重用與測試。
- **資料存取集中在 `storage.py`**，其他層透過模型物件讀寫，SQL 不散落各處。
- **動作系統用 Strategy**：每個動作一個類別（角度定義 + 狀態機 + MET + 攻擊型態），新增動作不動核心。
- **攝影機來源用 `CameraSource` 抽象**：本機鏡頭 / Wi-Fi 串流 / USB 可切換。**不採用藍牙**（頻寬與缺視訊 profile，無法承載即時串流）。
- **取值與輸入方式解耦**：BMI 本輪只做鍵盤，但留好接口讓語音/手寫日後可接同一位置。
- **可調參數集中為常數**（判定門檻、冷卻幀數、MET 值、分身成長係數等）。

## 既有資產（重構時要保留行為）

> 函式名／行號整理自舊 `FEATURES`，**動工前務必實際讀過檔案確認真實介面**，不可照舊行號盲改。

- `pose_detector.py`：`process()`、`get_pixel()`、`body_center_pixel()`、`angle()` 等——姿態偵測與角度計算，直接沿用。
- `game_objects.py`：怪物三型、`Monster`、`Laser`、`Explosion`、`GameState.fire_laser()`、`update()`、HUD——打怪核心，接進 `PLAYING` Scene。
- `exercise_counter.py`：深蹲／伏地挺身判定邏輯——搬進 `exercises.py` 的 `Squat`/`Pushup` 類別，門檻與行為不變。
- `text_utils.py`：中文渲染——所有玩家文字都走它。

## 開發工作流

1. 動工前 `git status` / 讀現有程式碼，建立對真實介面的理解（見 DEVELOPMENT_PLAN 任務零）。
2. 依 `DEVELOPMENT_PLAN.md` 順序，一次做一個任務。
3. 每個任務完成後：實際啟動、確認流程能走、保留的功能未壞、本任務驗收達成。
4. 用「舉手」測試動作快速驗證流程與新功能，**避免每次都要真的做深蹲**。
5. commit 訊息用繁中，簡述改動。

## 不要做的事

- 不要把流程寫回成一坨 if-else——要用 Scene 狀態機。
- 不要讓數位分身淪為一個孤立按鍵面板——它要綁在使用者與訓練循環上。
- 不要丟掉舊版的怪物／雷射／特效美術與動作判定行為。
- 不要把中文塞進 `cv2.putText`。
- 不要照舊 `FEATURES` 行號盲改——以實際 codebase 為準。
- 不要引入需要 GPU／雲端的重依賴，也不要嘗試用藍牙傳畫面。
- 不要交出無法啟動的版本。
