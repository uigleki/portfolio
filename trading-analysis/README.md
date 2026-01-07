<!-- markdownlint-disable MD024 MD036 -->

# Trading Analysis Tools

交易數據分析工具集：從影片自動提取交易記錄、可視化 tick 數據、探索進場訊號的微觀結構特徵。

**技術棧**: Python, OpenCV, Tesseract OCR, pandas, plotly, ipywidgets, scikit-learn

## 為什麼做這個專案

想從交易影片中提取數據進行分析，看能不能發現一些有趣的規律或模式。但影片裡的交易記錄都是視覺形式（螢幕錄影），需要自動化提取成結構化數據。

所以我做了四個工具：

1. **OCR Extractor**：自動從影片提取交易記錄
2. **Tick Visualizer**：單品種 tick 級別分析
3. **Tick Multi-Symbol**：多品種聯動觀察
4. **Feature Engineering**：機器學習特徵工程（實驗性）

## 1. Video OCR Extractor

### 問題

影片包含完整的開平倉記錄，但是視覺形式。需要：

- 偵測畫面變化（滾動、新增/關閉訂單）
- 用 OCR 識別文字（訂單 ID、時間、價格）
- 追蹤訂單生命週期（開倉 → 平倉）

### 核心技術

**場景檢測**：判斷畫面是否改變

```python
class Shot:
    def is_similar(self, other: Shot) -> bool:
        # 比對滾動條位置
        if self.bar != other.bar:
            return False
        # 逐行比對訂單 ID 圖片
        return all(
            self._compare_images(self.id_img[y1:y2], other.id_img[y1:y2])
            for y1, y2 in reversed(self.ID_ROW_RANGES[:self.bar])
        )
```

**OCR 精準度優化**：不同欄位用不同字元白名單

```python
CHARS = {
    "int": "0123456789",           # 訂單 ID
    "dt": "0123456789.:",          # 日期時間
    "type": "buysell",             # 交易方向
    "dec": "0123456789.",          # 價格
}
```

**交易追蹤邏輯**：

```python
# 檢測平倉：訂單 ID 消失
for idx in [i for i in prev if i not in curr]:
    self.df.loc[idx, ["End Time", "End Price"]] = [timestamp, price]

# 檢測開倉：新訂單 ID 出現
for idx in [i for i in curr if i not in prev]:
    self.df.loc[idx] = self.proc.get_row_data(...)
```

**智能時間修正**：OCR 只能識別 HH:MM:SS，需要推斷完整日期

```python
# 處理跨日情況
corrected_end_time = datetime.combine(next_time.date(), end_time)
if corrected_end_time > next_time:
    corrected_end_time -= timedelta(days=1)
```

**斷點續傳**：支援中斷後從上次位置繼續

```python
if resume_data and self.RAW_PATH.is_file():
    df = pd.read_csv(self.RAW_PATH, dtype=str)
    frame_pos = int(df["frame_pos"].iloc[-1])
```

## 2. Tick Visualizer（單品種版）

### 問題

想要人工分析 tick 數據，尋找進場前的價格型態規律。

### 核心功能

**雙模式切換**：

- **Time 模式**：以時間軸顯示，觀察特定時段的 tick 行為
- **Tick 模式**：以 tick 序號顯示，觀察進場前 100 個 tick 的微觀結構

**精確進場點匹配**：處理多種邊界情況

```python
def get_pretrade_ticks(trade, ticks, lookback=100):
    # 找到最接近成交價的 tick
    tick_slice = ticks[trade_time:next_second]
    closest_idx = (tick_slice[price_col] - trade["End Price"]).abs().idxmin()

    # 處理 tick 間隔過大（> 0.2 秒）
    if is_far(closest_idx, ref_time):
        tick = ticks[:closest_idx].iloc[-1]

    return ticks[:tick.name].tail(lookback)
```

**互動控制**：

- 方向鍵快速切換交易
- 節流機制（0.2 秒）避免頻繁更新造成卡頓
- Plotly hover 顯示精確 tick 資訊

## 3. Tick Multi-Symbol（多品種版）

### 問題

想觀察多個交易品種的相關性，尋找跨品種訊號。

### 功能

**多品種聯動分析**：

```python
symbols = ["usdjpy", "eurjpy", "xauusd"]
# 同時顯示多個品種的 tick 變化
# 觀察 USDJPY/EURJPY 的關聯性
# 分析黃金與匯率的反向關係
```

**子圖佈局**：

- 共用 X 軸時間線
- 垂直排列多個品種
- 同步顯示進出場點

**使用場景**：

- 尋找跨品種套利機會
- 觀察品種間的領先滯後關係
- 驗證多品種對沖策略

## 4. Feature Engineering（實驗性）

### 專案定位

這是**探索性研究**，最終準確率未達預期。保留它是為了展示**系統化的研究方法**，而非結果。

### 研究目標

使用機器學習預測進場時機。

### 特徵設計

從 tick 微觀結構提取特徵：

**1. 時間特徵**

- `time_diff`: 最新 tick 間隔
- `time_ratio`: 間隔相對於平均值的比例
- `time_acceleration`: tick 到達速度變化

**2. 價格特徵**

- `price_change`: 中間價變動（基點）
- `relative_change`: 相對於近期平均變動
- `breakthrough`: 價格突破強度

**3. 市場壓力**

- `buy_pressure`: Ask 變動 / 總變動
- `sell_pressure`: Bid 變動 / 總變動

**4. Tick 密度**

- `tick_density_{3,5,10}`: 不同窗口的 tick 密度
- 市場活躍度指標

**多位置特徵**：因為不確定真正的決策點，計算多個位置的特徵

```python
def cal_features(df, n=5):
    # 計算 pos_1 到 pos_5 的所有特徵
    for i in range(1, n + 1):
        current_df = df.iloc[:-i+1] if i > 1 else df
        features.update(cal_pos(current_df, f"pos_{i}_"))
```

**樣本構造**：利用滑動窗口構造正負樣本

```python
pos.append(tick_window[10:])   # 正例：真實進場前 100 tick
neg.append(tick_window[:-10])  # 負例：真實進場前 110~10 tick
```

**模型訓練**：

- Random Forest 分類器
- 貝葉斯優化搜索超參數（50 次迭代，5-fold CV）
- 輸出特徵重要性分析

### 為什麼沒效果

可能的原因：

- 進場決策不完全基於 tick 數據
- 需要更多上下文（訂單簿、成交量）
- 標籤定義需要改進（「進場前 100 tick」可能不是真正的決策點）

但這個過程展示了系統化的研究方法：特徵設計 → 樣本構造 → 模型訓練 → 結果分析。

## 技術亮點

### 計算機視覺

- OpenCV 場景檢測：像素級比對 + 閾值判斷
- Tesseract OCR 優化：字元白名單 + 後處理修正
- 智能錯誤修正字典（常見 OCR 誤識）

### 時序數據處理

- pandas 時間序列操作：datetime 推斷、跨日處理
- 精確 tick 匹配：處理時間間隔、價格對齊等邊界情況
- 斷點續傳機制

### 數據可視化

- Plotly 互動式圖表：hover、zoom、雙模式切換
- ipywidgets 控件：按鈕、滑桿、文字輸入
- 節流優化：避免頻繁更新造成 UI 卡頓

### 機器學習

- 系統化特徵工程：時間、價格、壓力、波動、密度
- 貝葉斯超參數優化
- 特徵重要性分析

### 代碼品質

```python
# Python 3.10+ 類型標註
def unwrap(x: T | None) -> T:
    assert x is not None
    return x

# 裝飾器優化性能
@cached_property
def timestamp(self) -> str:
    return OCR.read(gray_region(self.frame, self.TIME_RANGE), "time")
```

## 成果與反思

這個專案最大的價值不是「做出能賺錢的模型」，而是：

- 展示完整的數據分析流程（提取 → 清洗 → 可視化 → 建模）
- 展示多種技術的整合（CV、時序分析、ML、可視化）
- 展示誠實面對失敗的態度（承認 ML 部分沒效果）

**學到什麼**：

- OCR 不只是呼叫 API，需要很多前處理和後處理
- 時序數據的邊界情況很多（跨日、間隔、對齊）
- 機器學習不是萬能的，特徵工程比模型選擇更重要
- 有些問題可能根本不適合用 ML 解決

## 代碼文件

- [ocr_extractor.py](./ocr_extractor.py) - 螢幕錄影 OCR 提取（場景檢測、OCR、追蹤邏輯）
- [tick_visualizer.py](./tick_visualizer.py) - 單品種互動式分析（雙模式、精確匹配）
- [tick_multi_symbol.py](./tick_multi_symbol.py) - 多品種聯動分析（子圖同步）
- [feature_engineer.py](./feature_engineer.py) - ML 特徵工程實驗（特徵設計、模型訓練）
