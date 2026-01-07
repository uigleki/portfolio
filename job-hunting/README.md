# Job Hunting Automation

AI 驅動的求職自動化工具：爬取 104 人力銀行職缺，使用 Gemini AI 根據履歷自動篩選推薦職位。

**技術棧**: TypeScript, Playwright, Google Gemini AI, SQLite, Zod

## 為什麼做這個專案

求職時每天手動瀏覽數百個職缺太耗時，而且容易漏掉合適的機會。這個工具將篩選流程完全自動化，讓我專注在真正值得申請的職位上。

## 架構設計

```text
104 職缺清單
    ↓
Playwright 爬蟲（反偵測）
    ↓
SQLite（去重）
    ↓
Markdown 格式化
    ↓
Gemini 2.5 Flash 評估
    ↓
推薦清單 / 垃圾桶
```

## 核心功能

### 1. 職缺爬蟲

**解決的問題**: 104 使用 Vue 動態渲染內容，傳統爬蟲無法正常抓取

**技術實現**:

- Playwright + stealth plugin 避免被反爬蟲偵測
- SQLite 去重機制，避免重複處理相同職缺
- 完整提取職缺詳情、工作內容、公司介紹等信息
- 輸出 Markdown 格式，便於 AI 分析和人工閱讀

**關鍵代碼**:

```typescript
// 處理 Vue 動態渲染的職缺列表
const locator = page.locator(
  '.vue-recycle-scroller__item-wrapper a[href*="/job/"]',
);
await locator.first().waitFor();

// 自動解析總頁數並遍歷
async function getTotalPages(page: Page): Promise<number> {
  const text = await getText(page, ".multiselect__option");
  return parseInt(text.split("/")[1]);
}
```

### 2. AI 職缺評估

**解決的問題**: 判斷職缺是否適合需要考慮多個維度，單純關鍵字匹配不夠準確

**評估邏輯**:

1. **硬性門檻**（任一不符直接拒絕）
   - 英文能力要求過高（無法流利口語溝通）
   - 必備技能要求不符（強硬要求多年經驗且完全沒接觸過）

2. **匹配度分析**
   - 新人友善度（明確歡迎應屆生 / 提供培訓導師）
   - 技術棧現代化程度（Go/Rust/雲端原生優先）
   - 公司品質與職缺描述清晰度

**技術實現**:

```typescript
// 使用 Zod schema 強制 AI 輸出結構化 JSON
const evaluationSchema = z.object({
  recommend: z.boolean(),
  reasons: z.array(z.string()),
});

const response = await ai.models.generateContent({
  model: "gemini-2.5-flash",
  contents: buildEvaluationPrompt(job.content),
  config: {
    responseMimeType: "application/json",
    responseJsonSchema: zodToJsonSchema(evaluationSchema),
    temperature: 0.1, // 低溫度確保穩定輸出
  },
});
```

**Prompt 工程**:

- 明確禁止冗餘表述（❌ "求職者技術能力與職缺要求高度匹配"）
- 要求精簡陳述實際理由（✅ "明確歡迎應屆生，提供導師制度"）
- 多層嵌套 JSON 的容錯解析

## 使用方式

```bash
npm install

# 1. 爬取職缺
npm run scrape

# 2. AI 評估
npm run evaluate
```

**輸出範例**:

```text
找到 50 個職缺，開始分析...

✅ 推薦：abc123
  1. 明確歡迎應屆生，提供導師制度
  2. 技術棧 Go/K8s/微服務，環境先進
  3. 大公司，薪資福利完善

❌ 不推薦：def456
  1. 要求流利英文口語
  2. 需 3 年以上經驗

✅ 完成！共分析 50 個職缺，推薦 12 個
```

## 技術亮點

### TypeScript 工程化

- Zod schema 驗證 AI 輸出，確保類型安全
- 模組化設計，函數職責清晰
- 類型標註完整，避免運行時錯誤

### AI Prompt Engineering

- 結構化評估標準，確保判斷邏輯一致
- 使用 JSON Schema 強制輸出格式
- 理由質量控制，避免 AI 輸出廢話

### 錯誤處理與重試機制

- 自動處理 API 錯誤（500/503）和 JSON 解析失敗
- 指數退避策略（2秒 → 4秒 → 6秒）
- 最多重試 3 次，並記錄詳細錯誤信息

### 實用性

- 解決實際求職痛點（海量職缺篩選）
- 完全自動化，節省大量時間
- 評估標準可根據需求調整
- 自動重試機制確保運行穩定性

## 代碼文件

- [scraper.ts](./scraper.ts) - 爬蟲邏輯
- [evaluator.ts](./evaluator.ts) - AI 評估邏輯
