# Portfolio

> 「把複雜的事情變簡單，才是真正的本事。」

我是張瑞元，資訊管理系畢業，專注於用程式解決實際問題。這個倉庫展示我從大學到現在的技術成長軌跡。

## 關於這個倉庫

這裡的專案都源自真實需求：

- 求職時每天要篩選上百個職缺 → 做了 AI 自動化工具
- 短線交易需要快速計算風險 → 開發了固定風險管理工具（並用它通過 FTMO 評估）
- 想分析交易影片裡的進出場時機 → 用 OCR 自動提取數據
- 解壓縮檔案檔名變亂碼 → 用字頻分析做編碼檢測工具
- 每次重裝系統要手動配置環境 → 改用聲明式配置管理

我的專案展示了從「能跑」到「好維護」的技術成長，以及從單純寫代碼到系統化思考的轉變。

## 專案列表

### [Collection Website](./collection) - 個人收藏展示網站 (2025/12 - 2026/01)

用現代前端技術打造的展示網站，重點在於流暢的動畫體驗和優雅的視覺呈現。純 Markdown 清單看起來無聊，想做一個有互動感的呈現方式。

**技術亮點**：

- React 19 + TypeScript + Tailwind CSS 4 + Framer Motion
- 動畫設計：stagger animations、hover propagation、視差效果
- CSS native `light-dark()` 深色模式，完全跟隨系統設定
- Feature-Sliced Design 分層架構 + PWA 離線支援

**線上版本**：[spotless.pages.dev](https://spotless.pages.dev)

### [zipnao](./zipnao) - CJK 編碼修復工具 (2025/11 - 2025/12)

解壓縮檔案時檔名變亂碼，是 CJK 用戶的日常痛點。傳統工具（如 Python chardet）對中日韓文字檢測準確率很低，因為這些編碼之間可以互相解碼而不報錯。我用「字符頻率分析」來解決：用真實語料庫的字頻數據，判斷哪個解碼結果最像真正的中日韓文字。

**為什麼從 Python 遷移到 Flutter**：原本用 Python + PyQt 實現，打包後超過 100MB。Flutter 桌面版只需要約 20MB，而且想藉機學習 Flutter。

**技術亮點**：

- 基於 Wordfreq 語料庫的字頻分析算法
- MVVM 架構 + Provider 狀態管理
- Isolate 並行計算避免 UI 卡頓
- Sealed Class 實現類型安全的 Result 類型

### [job-hunting](./job-hunting) - AI 求職自動化工具 (2025/10 - 2025/11)

每天手動篩選數百個職缺太耗時，而且容易漏掉適合的機會。我做了一個爬蟲 + AI 分析的工具，自動從 104 人力銀行抓取職缺，然後用 Google Gemini AI 根據我的履歷進行多維度評估（硬性門檻 + 匹配度分析）。

**技術亮點**：

- Playwright + stealth plugin 反偵測爬蟲
- Zod schema 強制 AI 輸出結構化 JSON（避免 AI 格式不穩定）
- 智能重試機制：自動處理 API 錯誤和 JSON 解析失敗
- 特地用 TypeScript 而非 Python，展現多語言能力

### [NixOS Dotfiles](./dotfiles) - 聲明式環境管理 (2025/07 - 2025/10)

從 Arch Linux 升級到 NixOS，實現「系統狀態即代碼」。就像 Docker 的 Dockerfile 可以重現容器環境，NixOS 可以讓整個作業系統的配置變成一份可追蹤、可回滾的程式碼。

**為什麼這麼做**：

- Arch 的安裝腳本只能在全新安裝時執行，系統更新後無法保證環境一致性
- 手動配置容易出錯，而且無法快速在多台機器間同步

**技術亮點**：

- Nix Flakes + home-manager 模組化架構
- Disko 聲明式磁碟分區，配合 nixos-anywhere 遠端一鍵部署
- 安全加固：kernel hardening、dnscrypt-proxy、fail2ban
- 多環境支援：WSL / 雲端伺服器 / 桌面 共用同一份配置

### [trading-analysis](./trading-analysis) - 交易數據分析工具集 (2024/07 - 2025/01)

想從交易影片中提取數據進行回測分析，但影片裡的交易記錄都是視覺形式。我開發了四個工具：OCR 自動提取、tick 級別可視化分析、多品種聯動觀察、以及實驗性的機器學習特徵工程。

**核心技術**：

- OpenCV 場景檢測 + Tesseract OCR（處理螢幕錄影）
- 智能時間修正：OCR 只能識別 HH:MM:SS，需要推斷完整日期
- Plotly 互動式圖表：雙模式切換（時間軸 vs tick 序號）

**技術深度**：涵蓋計算機視覺、時序數據處理、數據可視化、機器學習特徵工程。

### [ctrader-bots](./ctrader-bots) - cTrader 交易工具 (2022/10 - 2024/08)

傳統交易平台用固定手數下單，但專業交易需要的是固定風險（每筆交易承受相同金額損失）。我做了一個視覺化風險管理工具，可以拖曳圖表上的線條來設定進場/止損/止盈，工具會自動計算應該下多少手數。

**實戰成果**：用這個工具通過 FTMO 兩階段評估（[Challenge](https://trader.ftmo.com/certificates/share/b3f8fa7ba9ec65a23379) / [Verification](https://trader.ftmo.com/certificates/share/4e056898f0ab4ca9b67a)）

**為什麼這麼重要**：

- 止損 10 點 vs 50 點，相同手數風險差 5 倍
- 短線交易需要快速準確執行，沒時間手動計算

**技術設計**：

- 固定風險公式：`volume = cashRisk / (stopLossPips × pipValue)`
- 雙擊確認 + 冷卻時間，防止誤觸
- 現代 C# 特性：Record types、Pattern matching、LINQ

### [course-grabber](./course-grabber) - 大學選課自動化 (2022/03 - 2023/01)

大學選課系統開放時，熱門課程會在幾秒內額滿。我做了一個自動化腳本，精確控制時間：提前 5 分鐘登入 → 提前 1 分鐘進入頁面 → 開放瞬間點擊。

這是早期作品，保留於此展示技術成長軌跡。

**設計亮點**：

- 三階段時間控制（避免過早被登出、補償網路延遲）
- 競爭處理：第一志願重複點擊直到成功
- 測試模式：執行前先跑一遍完整流程

**如果現在重寫**：會用 Playwright 而非 Selenium（更現代）、配置檔案而非硬編碼、類型標註。但核心邏輯當時就是對的。

### [arch-installer](./arch-installer) - Arch Linux 自動安裝 (2020 - 2021)

720 行 Bash 腳本，從磁碟分割到系統加固一鍵完成。現已升級至 NixOS，保留於此展示從「命令式管理」到「聲明式配置」的思維轉變。

**功能**：

- 自動檢測硬體（CPU、GPU、UEFI/BIOS）
- TPM 2.0 全盤加密（綁定韌體，防止竄改）
- 整合多個安全專案的最佳實踐（Whonix、GrapheneOS）

**為什麼被取代**：Arch 安裝腳本只能在全新安裝時執行，後續系統更新無法保證環境一致性。這讓我意識到「命令式管理」的局限性，最終升級到 NixOS 的「聲明式配置」。

## 技術特點

### 多語言實戰經驗

每個專案都選擇最適合的語言：

- **TypeScript**：類型安全、Zod 驗證（job-hunting）
- **Python**：數據分析、計算機視覺、機器學習（trading-analysis）
- **C#**：高性能交易工具、現代語言特性（ctrader-bots）
- **Dart/Flutter**：跨平台桌面應用、小體積打包（zipnao）
- **Nix**：聲明式配置、函數式語言（dotfiles）
- **Bash**：系統管理、複雜狀態處理（arch-installer）

### 解決實際問題

不是為了寫代碼而寫代碼：

- 求職篩選太耗時 → AI 自動化
- 交易風險管理不佳 → 固定風險工具（並用它通過專業考核）
- 想分析交易模式 → OCR 自動提取
- 解壓縮檔名亂碼 → 字頻分析編碼檢測
- 選課競爭激烈 → 精確時間控制
- 系統配置不一致 → 聲明式管理

### 技術成長軌跡

**早期（2020-2022）**：

- 能跑就好（中文變數、硬編碼）
- 命令式思維（Bash 腳本、Selenium）

**中期（2022-2024）**：

- 注重代碼品質（類型標註、設計模式）
- 實戰驗證（FTMO 評估通過）

**現在（2024-2025）**：

- 系統化思考（聲明式配置、可重現環境）
- AI 工程應用（Prompt Engineering、結構化輸出）
- 跨平台開發（Flutter 桌面應用）

從基礎自動化 → Linux 系統管理 → 交易工具開發 → 數據分析 → 聲明式配置 → AI 工程 → 跨平台桌面開發的完整成長路徑。

## 關於我

資訊管理系畢業，專注於系統自動化和實用工具開發。我相信好的代碼不只是能跑，更要好維護、好擴展。熟悉 Python、C#、TypeScript、Dart、Nix、Bash 等多種語言，善於選擇合適的技術棧解決實際問題。

**核心能力**：

- 自主學習：從 Linux 系統到 AI 工程，都是靠自學累積
- 系統化思考：重視可重現性、可預測性、可控制性
- 解決問題的熱情：看到問題被解決、效率被提升，是我最大的成就感來源

## 聯絡方式

- Email: <jobs.chef098@aleeas.com>
- GitHub: [查看更多專案](https://github.com/uigleki)

## 授權資訊

此倉庫採用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 授權，歡迎查看和學習，禁止商業使用。
