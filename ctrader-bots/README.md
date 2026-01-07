# cTrader Trading Bots

cTrader 交易工具：固定風險的手動交易助手 + 實驗性自動化策略。

**技術棧**: C#, cTrader API, WPF

## ⭐ 實戰成果

用 **Quick Trade Manager** 通過 FTMO 兩階段評估：

- [Challenge 階段證書](https://trader.ftmo.com/certificates/share/b3f8fa7ba9ec65a23379)
- [Verification 階段證書](https://trader.ftmo.com/certificates/share/4e056898f0ab4ca9b67a)

這不是「能跑的玩具」，而是實際幫我通過專業考核的工具。

## Quick Trade Manager - 固定風險交易助手

### 為什麼做這個工具

**問題**：傳統交易平台用**固定手數**下單，但專業交易需要的是**固定風險**。

舉例來說：

- 止損 10 點 vs 止損 50 點，用相同手數，風險差 5 倍
- 短線交易每筆風險應該固定（例如 1% 帳戶），但手動計算太慢

**解決方案**：視覺化風險管理工具。在圖表上拖曳進場/止損/止盈的線條，工具自動計算應該下多少手數來達到固定風險。

**為什麼這麼重要**：
短線交易需要快速準確執行，沒時間讓你手動算。而且錯一個小數點，風險就差很多。

### 主要功能

#### 1. 視覺化風險管理

- 三條可拖曳的水平線：進場價（藍）、止損（紅）、止盈（綠）
- 拖動線條時即時計算手數和風險收益比
- 雙擊確認下單（防止誤觸）

#### 2. 智能訂單執行

自動判斷 Limit/Stop 訂單類型：

- 買入 + 進場價 < 市價 = Limit Order（等待回調）
- 買入 + 進場價 > 市價 = Stop Order（突破進場）

#### 3. 快速操作

- 兩個快捷按鈕預設風險金額
- 市價/掛單模式一鍵切換
- 追蹤止損選項

### 核心技術

**固定風險計算公式**：

```csharp
volume = cashRisk / (stopLossPips * pipValue)
```

這確保每筆交易風險固定，無論商品波動率或止損大小。

**價格計算器**（雙向轉換）：

- `OrderToPrice()`: 風險金額 + 止損點數 → 計算絕對價格
- `PriceToOrder()`: 絕對價格 → 反推風險參數

**安全機制**：

- 風險上限（預設 1.5% 帳戶餘額）
- 雙擊確認（500ms 時間窗口）
- 下單後 1 秒冷卻時間

### 設計模式

**Strategy Pattern** - 訂單類型選擇

```csharp
if (orderMode == OrderMode.Market)
    await MarketOrder(setup);
else
    await PendingOrder(setup);
```

**Observer Pattern** - 圖表線條變化監聽

```csharp
chartLine.LineChanged += (line) => UpdateOrderDetails();
```

**Record Pattern** - 不可變資料傳遞

```csharp
public record OrderSetup(
    double CashRisk,
    TradeType Direction,
    double EntryPrice,
    double StopLoss,
    double RewardRatio,
    DateTime? Expiry = null
);
```

## Range Breakout Bot - 區間突破策略（實驗性）

### 策略邏輯

在特定時間區間（例如亞洲盤 3:05-6:05）統計價格高低點，收盤後掛單等待突破。

**時間線**：

```text
03:05 ────► 06:05 ────► 18:55
  │           │           │
統計高低點   掛單突破   平倉所有部位
```

**區間過濾**：

```csharp
span = (highPrice - lowPrice) / closePrice

// 拒絕過窄的區間（盤整）
if (span < MinRangePct/100) return;

// 拒絕過寬的區間（已經移動太多）
if (span > MaxRangePct/100) return;
```

**預設配置系統** - 不同商品的最佳化參數：

```csharp
private static readonly Dictionary<Preset, Params> Presets = new()
{
    [Preset.XAUUSD] = new(0305, 0605, 1855, 1, 0.15, 0.85),
    [Preset.USDJPY] = new(0300, 0430, 1800, 0.5, 0.2, 0.4),
    // ...
};
```

## 技術亮點

### 現代 C# 特性

**Record Types** - 不可變資料

```csharp
public record OrderSetup(...);
```

**Pattern Matching** - 簡潔的條件判斷

```csharp
if ((isBuyOrder && entryPrice < bid) || (!isBuyOrder && entryPrice > ask))
    await PlaceLimitOrderAsync(...);
```

**Extension Methods** - 優雅的 API 擴展

```csharp
public static void CancelOrders(this Robot robot)
{
    foreach (var order in robot.PendingOrders)
        robot.CancelPendingOrderAsync(order);
}
```

### SOLID 原則

**Single Responsibility** - 每個類別單一職責

- `ChartLine`: 管理視覺元素
- `TradeExecution`: 下單邏輯
- `PriceCalculator`: 價格轉換

**Open/Closed** - 易於擴展

- `ExpiryManager` 支援自訂時區
- `Presets` 字典可新增商品配置

**Dependency Injection** - 解耦

```csharp
public class TradingPanel
{
    private readonly Robot robot;
    public TradingPanel(Robot robot) => this.robot = robot;
}
```

## 功能對比

| 功能         | Quick Trade Manager | Range Breakout Bot |
| ------------ | ------------------- | ------------------ |
| **類型**     | 手動執行輔助        | 全自動化           |
| **風險模型** | 固定現金風險        | 固定百分比風險     |
| **訂單類型** | 市價 + 掛單         | 掛單（Limit/Stop） |
| **進場訊號** | 手動（拖曳線條）    | 區間突破           |
| **獲利驗證** | ✅ FTMO 通過        | ⚠️ 實驗性質        |

## 成果與反思

**Quick Trade Manager** 是我最滿意的專案之一：

- 解決了真實需求（快速準確下單）
- 實戰驗證（通過 FTMO 評估）
- 代碼品質高（設計模式、現代 C# 特性）

**學到什麼**：

- 好的工具不只是「能用」，更要「好用」、「不出錯」
- UI/UX 設計很重要：拖曳線條比輸入數字更直觀
- 安全機制必須做好：雙擊確認、風險上限、冷卻時間

**Range Breakout Bot** 是探索性專案，策略邏輯正確但未實戰驗證。保留它是為了展示「系統化的策略開發流程」（時區處理、參數配置、區間過濾）。

## 代碼文件

- [QuickTradeManager.cs](./QuickTradeManager.cs) - 手動交易助手（803 行）
- [RangeBreakoutBot.cs](./RangeBreakoutBot.cs) - 自動化突破策略（267 行）
