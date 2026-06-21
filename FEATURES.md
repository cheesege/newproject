# FEATURES — 技術、公式、原理、概念與功能

> 本檔是「體感硬核健身房」的**技術參考文件**：記錄遊戲用到的技術棧、數學公式、
> 運作原理、設計概念與完整功能。安裝與操作請見 [README.md](README.md)。

---

## 一、技術棧

| 領域 | 技術 | 用途 |
|------|------|------|
| 語言 | Python 3.10+ | 全專案 |
| 影像 | OpenCV (`cv2`) | 攝影機擷取、所有畫面繪製、特效、趨勢圖渲染 |
| 姿態偵測 | MediaPipe Tasks `PoseLandmarker`（**lite** 模型、VIDEO 模式、33 點） | 即時全身骨架 |
| 數值運算 | NumPy | 角度向量運算、線性回歸 `polyfit`、背景漸層 |
| 中文渲染 | Pillow (PIL) | 在 BGR 畫面上繪製 CJK 文字（`cv2.putText` 不支援中文） |
| 資料儲存 | `sqlite3`（標準庫） | 使用者、BMI、場次、數位分身持久化，離線零依賴 |
| 音效 | `pygame.mixer` | 動作未達標警訊音，失敗降級系統嗶聲 |
| 並行 | `threading` | 攝影機背景抓幀，與偵測/繪製平行以提升 FPS |

> **趨勢圖不使用 Matplotlib**：改用 OpenCV 直接繪製，與遊戲視覺一致且少一個依賴。
> （`requirements.txt` 已不含 matplotlib。）

設計模式：**Strategy**（動作系統）、**State Machine**（Scene 流程）、**抽象介面/多型**
（攝影機來源、數值輸入）、**Repository/Model**（資料層 `User` 模型）。

---

## 二、公式與演算法

### 2.1 三點關節夾角（動作判定的核心數學）
以 B 為頂點，求 A-B-C 夾角。取兩向量 **BA**、**BC**，用內積反餘弦：

```
BA = A − B,  BC = C − B
cosθ = (BA · BC) / (‖BA‖ · ‖BC‖)
θ(度) = degrees(arccos(clip(cosθ, −1, 1)))
```

實作於 [pose_detector.py](pose_detector.py) `angle()` / `_angle_deg()`，用 `clip` 防止浮點誤差超出 arccos 定義域。

### 2.2 體位自動判定（站立 vs 水平）
比較髖部與腳踝的正規化 y 座標差距：

```
diff = | avg(腳踝.y) − avg(髖.y) |
diff < 0.12 → horizontal（伏地挺身）；否則 vertical（深蹲／舉手）
```

### 2.3 動作門檻（一上一下狀態機）

| 動作 | 量測 | 達標下界 | 回復上界 |
|------|------|----------|----------|
| 深蹲 | 膝角（髖-膝-踝） | < 110° | > 160° |
| 伏地挺身 | 肘角（肩-肘-腕） | < 90° | > 155° |
| 舉手（測試） | 腕.y − 肩.y | < −0.03（舉起） | > 0.05（放下） |

左右兩側各算一次後取平均，任一側偵測失敗仍可運作。

### 2.4 BMI

```
BMI = 體重(kg) / 身高(m)²
本月變化 = 最新BMI − （距今約 30 天最接近的那筆紀錄）
```

### 2.5 卡路里

```
運動時數 = 動作次數 × 每次估計秒數 / 3600
卡路里  = MET × 體重(kg) × 運動時數
整場卡路里 = Σ（各動作分別計算後加總）
```

MET 值掛在各動作類別：深蹲 5.0、伏地挺身 3.8、舉手 2.0。以「次數×秒數」推算而非整場時長，
故發呆不累積卡路里。實作於 [calories.py](calories.py)。

### 2.6 數位分身屬性（成長角色）
由某使用者的累計 `sessions` 推導，皆上限 100：

```
力量 strength = min(100, 累計伏地挺身 × 2.0)
耐力 stamina  = min(100, 累計深蹲 × 1.5 + 場次 × 5.0)
體態 physique = min(100, max(0, 100 − |BMI − 22| × 8))
等級 level    = 1 + ⌊累計總卡路里 / 30⌋
```

健康 BMI 基準取 22；體態越接近 22 分數越高。實作於 [digital_twin.py](digital_twin.py) `compute_stats()`。

### 2.7 BMI 趨勢預測（數據孿生）
對 `bmi_history` 做一次線性最小平方擬合並外推 30 天：

```
以「距第一筆的天數」為 x、BMI 為 y
slope, intercept = polyfit(x, y, 1)
一個月後預測 = slope × (x_last + 30) + intercept
```

需至少兩筆不同日期的紀錄；趨勢圖上以**虛線**呈現（實線為實績）。實作於 `_linfit_forecast()`。

### 2.8 遊戲數值（隨等級遞增的難度）

```
怪物基礎速度 = 1.0 + 等級 × 0.12        （蝙蝠 ×1.2~1.9，其餘 ×0.8~1.6）
怪物血量     = max(1, rand(1,2) + (等級−1)//3)
生成間隔(幀) = max(30, 120 − 等級 × 8)   每次生成 min(等級, 3) 隻
擊殺得分     = 10 × 等級
升級         = 每滿 100 分升一級
雷射冷卻     = 18 幀；生命 = 3
```

---

## 三、運作原理

### 3.1 一次深蹲如何變成一發雷射（核心資料流）

```
攝影機幀 → 鏡像翻轉 → 縮小到 640px 寬 → MediaPipe 偵測 33 點
   → exercise_counter 依體位挑出該判定的動作
   → Exercise.update() 跑「一上一下」狀態機 → 完成回傳該 Exercise
   → 依其 game_action 決定 single（最近 1 隻）/ triple（最近 3 隻）
   → GameState.fire_laser() 選敵、扣血、爆炸、計分
```

### 3.2 防誤計狀態機
每個動作維持 `stage ∈ {up, down}`。只有「達到下界進入 down，再回到上界」才 `count += 1`，
避免姿勢抖動造成重複計數。

### 3.3 雷射選敵
玩家位置 = 左右髖部像素中心。`single` 取距玩家最近的一隻；`triple` 取最近三隻齊射。
命中後該怪 `hp−1`、白閃 6 幀，歸零則標記死亡並生成爆炸、加分。

### 3.4 效能優化（為了在 CPU 上跑得順）
| 手法 | 說明 | 位置 |
|------|------|------|
| lite 模型 | 用 `pose_landmarker_lite` 取代 full，CPU 推論更快，角度判定已足夠 | [pose_detector.py](pose_detector.py) |
| 輸入降採樣 | 偵測前把畫面縮到 640px 寬（顯示仍原解析度）；landmark 為正規化座標不受影響 | `process()` |
| 偵測節流 | 每 2 幀才偵測一次，其餘幀沿用上次骨架 | `PlayingScene.DETECT_EVERY` |
| 背景抓幀 | 用執行緒持續抓最新幀，讀取與偵測/繪製平行，避免阻塞砍半 FPS | [camera_source.py](camera_source.py) |
| 緩衝最小化 | `CAP_PROP_BUFFERSIZE=1` 盡量取最新幀，降低延遲 | `CameraSource.open()` |
| 字型快取 | 同大小字型只載入一次，避免逐幀重建 | [text_utils.py](text_utils.py) |

### 3.5 中文渲染原理
`cv2.putText` 只支援 ASCII。改以 Pillow 把文字畫到 RGBA 貼圖，再 alpha 混合回 BGR 畫面，
並處理邊界裁切。跨平台搜尋 CJK 字型路徑（Linux/macOS/Windows）。

### 3.6 攝影機來源容錯
來源優先序：啟動參數 > 環境變數 `GYM_CAMERA` > 設定檔 `camera.cfg` > 預設本機 0。
spec 字串自動判型（數字=本機、`usb:`=USB、`http/rtsp`=串流）。指定來源失敗自動退回本機鏡頭；
連本機都失敗時仍以空白畫面讓選單可操作。**不採用藍牙**（頻寬不足以承載即時視訊）。

---

## 四、設計概念

### 4.1 使用者是骨幹
一切數據（身高體重、BMI 軌跡、歷史場次、數位分身）都掛在某位 `User` 身上，
支援多使用者並存、切換、創建。沒有「漂浮在外」的全域資料。

### 4.2 數位分身＝養成的具象化
分身不是獨立面板，而是訓練成果的鏡子：練越多越強，並依數據預測未來的你。
每位使用者有各自獨立的分身（`twin_state`）。

### 4.3 Scene 狀態機
主迴圈不寫一坨 if-else，而是把「輸入／更新／繪製」交給當前 Scene。
新增畫面 = 新增一個 Scene 子類並註冊。八個場景：
`USER_SELECT → HUB → PRE_GAME → PLAYING ⇄ PAUSED → RESULT → (TRENDS / TWIN)`。

### 4.4 分層架構（高內聚、低耦合）

```
Scene 層（狀態機）  scenes/*.py
   ↓
領域邏輯層          exercises / game_objects / digital_twin / calories
   ↓
資料層              storage（SQLite + User 模型，集中所有 SQL）
   ↓
基礎設施層          pose_detector / camera_source / text_utils / sounds / ui_widgets
```

### 4.5 用抽象介面預留擴充
- **動作（Strategy）**：新增動作 = 新增一個 `Exercise` 子類，主迴圈與遊戲邏輯不動。
- **數值輸入**：`ValueReader` 抽象「取得一個數值」，本輪只做鍵盤，之後語音／手寫可接同一介面。
- **攝影機來源**：`CameraSource` 抽象「畫面從哪來」，本機/Wi-Fi/USB 共用同介面。

---

## 五、功能與對應模組

| 功能 | 說明 | 主要模組 |
|------|------|----------|
| 即時姿態偵測 | MediaPipe 33 點骨架、三點夾角、身體中心 | [pose_detector.py](pose_detector.py) |
| 三種動作判定 | 深蹲／伏地挺身／舉手測試（Strategy + 防誤計狀態機 + 即時回饋） | [exercises.py](exercises.py) |
| 動作協調 | 體位自動偵測、依本場選定動作挑判定對象 | [exercise_counter.py](exercise_counter.py) |
| 體感打怪核心 | 三種怪物、四模式、追蹤、雷射、爆炸、計分、升級、生命、冷卻 | [game_objects.py](game_objects.py) |
| 怪物圖鑑 | 記錄本場出現/擊敗數與擊敗率 | [ui_widgets.py](ui_widgets.py) |
| 多使用者系統 | 創建/切換、身體數據、BMI 歷史、場次、分身狀態 | [storage.py](storage.py) |
| BMI 與本月變化 | 計算、歷史、約一個月變化量 | [storage.py](storage.py) |
| 卡路里估算 | 依體重與動作 MET 估算，即時顯示並存檔 | [calories.py](calories.py) |
| 數值/文字輸入 | OpenCV 視窗鍵盤輸入（數值＋名稱），抽象介面 | [value_input.py](value_input.py) |
| 長期趨勢圖 | OpenCV 繪製次數/卡路里/BMI 折線 + 預測虛線 | [trends.py](trends.py) |
| 數位分身 | 成長角色屬性 + BMI 線性外推預測，綁定使用者 | [digital_twin.py](digital_twin.py) |
| 動作警訊音 | 未達標提示音、節流、降級容錯 | [sounds.py](sounds.py) |
| 攝影機來源 | 本機/Wi-Fi 串流/USB，背景抓幀、自動退回 | [camera_source.py](camera_source.py) |
| 中文渲染 | Pillow CJK 繪字 + alpha 合成 + 字型快取 | [text_utils.py](text_utils.py) |
| 流程框架 | Scene 狀態機與共用資源 | [main.py](main.py) + [scenes/](scenes/) |

---

## 六、資料模型（SQLite）

| 資料表 | 內容 |
|--------|------|
| `users` | 使用者：name / 身高 / 體重 / 性別 / 年齡 / 建立時間 |
| `bmi_history` | 每次更新身體數據的 BMI 紀錄（user_id、日期、身高、體重、bmi） |
| `sessions` | 每場結果（user_id、起訖時間、reps_json、分數、等級、卡路里） |
| `twin_state` | 每位使用者的分身快照（力量/耐力/體態/等級） |

`reps_json` 以 JSON 存各動作次數，如 `{"squat":12,"pushup":8}`。資料庫路徑可用環境變數
`GYM_DB` 覆寫（測試時指向暫存檔，不動到玩家存檔）。

---

## 七、可調參數一覽（集中為常數，方便依場地調校）

| 參數 | 位置 | 預設 |
|------|------|------|
| 動作角度門檻 | `exercises.py` 各類別 | 見 §2.3 |
| 體位門檻 | `exercise_counter.py` `HORIZONTAL_THRESHOLD` | 0.12 |
| 偵測輸入寬度 | `pose_detector.py` `DETECT_WIDTH` | 640 |
| 偵測節流幀數 | `scenes/playing.py` `DETECT_EVERY` | 2 |
| 各動作 MET / 每次秒數 | `exercises.py` 各類別 | 見 §2.5 |
| 分身成長係數 | `digital_twin.py` | 見 §2.6 |
| 預測天數 | `digital_twin.py` `FORECAST_DAYS` | 30 |
| 生命/冷卻/生成/計分 | `game_objects.py` | 見 §2.8 |
| 音效節流秒數 | `sounds.py` `throttle_sec` | 1.5 |
