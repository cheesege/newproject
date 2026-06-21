# DEVELOPMENT_PLAN.md — 重構開發任務規格

> 本檔列出把遊戲重構成「以使用者養成為核心的完整體驗」的所有任務，**請依序進行**。先讀 `CLAUDE.md`（鐵則與架構）與 `FEATURES.md`（完整流程願景）。
>
> 核心目標不是加功能，而是把流程重組為一條通暢動線：**選擇/創建使用者 → 訓練 → 結算（看見分身成長）→ 回主頁 → 再訓練**。時程不設限，以完整且可運作為優先。

---

## 任務零：盤點現有資產、規劃重構（前置）

**目標**：在動工前，搞清楚哪些舊程式碼要保留、怎麼接進新骨架。

**做法**：
- 讀完 `main.py`、`pose_detector.py`、`exercise_counter.py`、`game_objects.py`、`text_utils.py`。
- 確認三條真實資料流：
  1. 舊 `main.py` 的主迴圈如何讀幀→偵測→判定→更新→繪製（這會被拆進各 Scene）。
  2. `exercise_counter` 目前如何被呼叫、計數怎麼讀出（這要搬進 Strategy）。
  3. `GameState.fire_laser()` 與 `update()` 的參數與職責（這會被 `PLAYING` Scene 驅動）。
- 寫一段短筆記：哪些是「保留資產」、哪些是「要拆解重組」。

**驗收**：能說明舊版「一次深蹲 → 發射雷射」的完整資料流，以及它將被接到新架構的哪個位置。

---

## 任務一：Scene 狀態機骨架

**目標**：先把流程骨架搭起來，讓畫面之間能空跑切換，後續再把邏輯填進去。

**設計**：
- 新增 `scenes/base.py` 定義抽象基底：

```python
class Scene:
    def handle_input(self, key) -> None: ...   # 處理按鍵
    def update(self, dt) -> None: ...          # 更新狀態
    def draw(self, frame): ...                 # 畫到畫面上
    next_scene: str | None                     # 要切到哪個 Scene（None = 不切）
```

- 在 `main.py` 建立狀態機：持有「當前 Scene」，主迴圈每幀讀幀 → 交給當前 Scene 的 handle_input/update/draw → 若有 `next_scene` 就切換。
- 先建空殼 Scene：`USER_SELECT`、`HUB`、`PRE_GAME`、`PLAYING`、`PAUSED`、`RESULT`、`TRENDS`、`TWIN`，各畫個標題與「按某鍵前往下一個」的暫時導覽，能彼此跳轉即可。

**驗收**：程式啟動後能依按鍵在所有空殼畫面間流轉，流程骨架成立。

---

## 任務二：資料層 + 使用者系統（USER_SELECT）

**目標**：建立資料骨幹，實作使用者的選擇與創建。

**設計**：
- 新增 `storage.py` 集中 SQLite 存取，自動建表（資料庫如 `gym.db`）：

```
users(id, name, height_cm, weight_kg, sex, age, created_at)   -- sex/age 可空，保留
bmi_history(id, user_id, date, height_cm, weight_kg, bmi)
sessions(id, user_id, started_at, ended_at, reps_json, score, level, calories)
twin_state(user_id, strength, stamina, physique, level, updated_at)
```

- 提供 `User`/`Profile` 模型物件，封裝讀寫；其他層只透過模型操作，不直接寫 SQL。
- 充實 `USER_SELECT` Scene：
  - 列出 `users`（名稱、等級、上次訓練）。
  - 「創建新使用者」：鍵盤輸入名稱、身高、體重 → 算 BMI 寫入 `bmi_history`、初始化 `twin_state`。
  - 鍵盤輸入要自己管緩衝（逐字元 `waitKey`、Enter 確認、Backspace 刪除）。
  - **取值與輸入解耦**：抽出 `read_value(prompt) -> float/str`，鍵盤是其一實作，之後語音/手寫接同介面。
  - 選定使用者 → 載入其狀態 → 切到 `HUB`。

**驗收**：能創建使用者、重開後資料仍在、選定後帶著該使用者的資料進入主頁。

---

## 任務三：動作系統重構（Strategy）+ 舉手測試動作

**目標**：把寫死的動作改成可擴充結構，並加坐姿可觸發的測試動作。

**設計**：
- 新增 `exercises.py`，定義抽象基底：

```python
class Exercise:
    name: str            # 「深蹲」
    met: float           # 卡路里用
    game_action: str     # "single" / "triple"
    def update(self, detector) -> bool: ...    # 完成一次回傳 True
    def current_angle(self) -> float | None: ...
    @property
    def form_feedback(self) -> str: ...
    def form_error(self) -> str | None: ...     # 供音效用，無錯回 None
    def reset(self) -> None: ...
```

- 把舊深蹲、伏地挺身邏輯搬進 `Squat`、`Pushup`，門檻與行為不變（深蹲=single、伏地挺身=triple）。
- 新增 `RaiseHand`：用 Pose 手腕（15/16）與肩膀（11/12）的 y 比較，舉起=up、放下=down，一上一下記一次；`game_action="single"`；**標註為開發測試動作**，不引入 MediaPipe Hands。
- 保留體位自動偵測來決定當下啟用哪個動作。

**驗收**：深蹲/伏地挺身行為與舊版一致；舉手能在坐姿下穩定計數；之後新增動作只需新增類別。

---

## 任務四：訓練核心接入（PRE_GAME + PLAYING）

**目標**：把舊的打怪核心接進 Scene 流程，成為核心玩法。

**設計**：
- `PRE_GAME` Scene：選挑戰模式（沿用舊四種）、選本場動作組合，顯示對應攻擊方式，確認後進 `PLAYING`。
- `PLAYING` Scene：把舊 `main.py` 主迴圈的遊戲段落搬進來——讀幀→鏡像→`PoseDetector.process`→當前動作 `update`→達標呼叫 `GameState.fire_laser`→`GameState.update`→繪製骨架/怪物/雷射/HUD。
- 保留：怪物三型、四模式、追蹤、雷射齊射、爆炸、生命、計分、升級、雷射冷卻、HUD、半透明骨架、角度量表、瞄準準星、無人物警告、FPS。
- HUD 增加：即時卡路里、各動作次數（接任務五）。
- `PAUSED` Scene：暫停、可續玩或放棄返回 `HUB`。

**驗收**：能從主頁進入訓練、正常打怪、與舊版玩法一致，並可暫停/結束。

---

## 任務五：結算 + 數據寫回 + 卡路里（RESULT）

**目標**：把「這場訓練」與「長期養成」用因果串起來。

**設計**：
- 卡路里：`卡路里 ≈ MET × 體重(kg) × 運動時數`，MET 取自各動作、體重取自當前使用者；運動時數由次數×每次估秒或本場時長推算（擇一註明假設）。訓練中即時估、結算定版。
- 一場結束時，`RESULT` Scene：
  - 顯示本場各動作次數、分數、到達等級、消耗卡路里。
  - 寫入該使用者 `sessions`。
  - 依本場數據更新 `twin_state`（力量/耐力/體態/等級），並**視覺化分身的成長量**（例如「力量 +3、升到 Lv.5」）。
  - 返回 `HUB`，主頁數據同步刷新。

**驗收**：玩完一場後資料庫多一筆 session、分身屬性有變、畫面明確顯示這場帶來的成長，且體重不同卡路里不同。

---

## 任務六：使用者主頁 + 趨勢與預測（HUB + TRENDS）

**目標**：把所有資訊匯流到主頁，並提供長期視覺化。

**設計**：
- `HUB` Scene：中央顯示數位分身與體能等級；顯示 BMI 現值與本月變化、累計訓練摘要；提供入口（開始訓練/趨勢/更新身體數據/分身詳情/切換使用者）。
- `TRENDS` Scene：用 Matplotlib 畫次數/卡路里/BMI 隨時間折線，疊上線性外推的**預測虛線**（NumPy `polyfit`）。中文標籤需正確顯示（設定中文字型，或標籤用英文，二擇一註明）。
- 更新身體數據：可再次輸入身高體重，寫入 `bmi_history`，重算本月變化。

**驗收**：主頁能總覽該使用者狀態；能看到隨時間變化＋未來一個月預測的趨勢圖。

---

## 任務七：數位分身（TWIN，b + c 結合）

**目標**：完成由真實數據驅動、與使用者綁定的數位分身。

**設計**：
- 新增 `digital_twin.py`，只吃資料層數據，不碰 3D。
- 成長角色（c）：屬性由累積 `sessions` 推導（力量隨累計伏地挺身、耐力隨深蹲與時長、等級隨總卡路里等，係數集中為常數）。用 OpenCV 畫角色狀態面板（屬性條 + 等級）。
- 數據孿生與預測（b）：用 `bmi_history`/`sessions` 線性外推，呈現「照此趨勢，未來一個月的你/分身」。
- `TWIN` Scene：完整屬性面板 + 數據來源說明 + 預測，與當前使用者綁定。

**驗收**：不同使用者有不同分身；累積資料後屬性與等級反映訓練量；能顯示未來預測。

---

## 任務八：動作錯誤警訊音

**目標**：動作不標準時提示，提升運動防護價值。

**設計**：
- 新增 `sounds.py`，用 `pygame.mixer` 或 `simpleaudio` 播短音效；音效檔放 `assets/sounds/`，缺檔降級為系統嗶聲、不崩潰。
- 基本版（必做）：`PLAYING` 中當 `Exercise.form_error()` 回傳訊息時播提示音，做節流（同提示間隔一段時間才響），避免洗版。
- 進階版（時間允許）：在各動作類別新增明確錯誤姿勢偵測（如深蹲膝蓋內扣、伏地挺身塌腰），對應不同音效與文字。

**驗收**：動作不標準時聽到提示音且不洗版；缺音效檔仍能正常運作。

---

## 任務九：攝影機來源抽象（CameraSource）

**目標**：讓畫面來源可切換，方便把鏡頭架遠拍全身。

**設計**：
- 新增 `camera_source.py` 抽象畫面來源：
  - 本機鏡頭（預設，`cv2.VideoCapture(0)`）。
  - Wi-Fi 串流：手機 IP 攝影機 App（IP Webcam / DroidCam）的 HTTP/RTSP URL（`cv2.VideoCapture(url)`）。
  - USB 有線：DroidCam/iVCam USB 模式（裝置索引）。
- 來源由設定檔/環境變數/啟動參數指定；連線失敗給清楚錯誤並退回本機鏡頭。
- **不實作藍牙**：藍牙頻寬（約 1–3 Mbps）與缺視訊 profile，無法承載即時串流；如有人問，於文件說明採 Wi-Fi/USB 替代。

**驗收**：能用本機鏡頭或手機 Wi-Fi 串流啟動，切換來源不需改程式碼。

---

## 任務十：文件與整合收尾

**目標**：確保組員能裝能玩，文件與程式一致。

**做法**：
- `requirements.txt` 含所有依賴（mediapipe, opencv-python, numpy, pillow, matplotlib, pygame 等）。
- 更新 `README.md`（已提供新版）：把新流程（選擇使用者 → 主頁 → 訓練 → 結算）與實際按鍵同步，手機串流步驟對齊 `CameraSource` 的設定方式。
- 完整走一遍：創建使用者 → 訓練 → 結算看分身成長 → 主頁看趨勢預測，確認動線通暢。

**驗收**：沒碰過專案的組員照 `README.md` 就能裝起來、走完整條動線。

---

## 建議的最終檔案結構（供參考，可依實際調整）

```
.
├── main.py                  # 精簡：初始化 + Scene 狀態機主迴圈
├── scenes/
│   ├── base.py
│   ├── user_select.py
│   ├── hub.py
│   ├── pre_game.py
│   ├── playing.py
│   ├── result.py
│   ├── trends.py
│   └── twin.py
├── exercises.py             # Strategy 動作
├── game_objects.py          # 保留：打怪核心
├── pose_detector.py         # 保留
├── camera_source.py         # 新增
├── digital_twin.py          # 新增
├── calories.py              # 新增（或併入 exercises/storage）
├── storage.py               # 新增：SQLite + User/Profile 模型
├── sounds.py                # 新增
├── text_utils.py            # 保留
├── assets/{sounds,fonts}/
├── gym.db                   # 自動產生
├── requirements.txt
├── README.md / CLAUDE.md / FEATURES.md / DEVELOPMENT_PLAN.md
```
