# Collection Website

個人收藏展示網站 - 用流暢動畫和現代前端技術打造的互動式展示平台。

**技術棧**: React 19, TypeScript, Tailwind CSS 4, Framer Motion, Vite, VitePWA

**線上版本**: [spotless.pages.dev](https://spotless.pages.dev)

## 為什麼做這個專案

純 Markdown 清單看起來無聊，想要一個有互動感、動畫流暢的呈現方式。這個專案讓我能實踐現代前端技術，同時產出一個實用的展示網站。

## 核心功能

### 互動式卡片展開

點擊作品卡片展開詳細評論，使用 Framer Motion 的 `AnimatePresence` 實現平滑的高度動畫：

```tsx
<AnimatePresence mode="wait">
  {expanded && (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      {/* 內容 */}
    </motion.div>
  )}
</AnimatePresence>
```

### 視差效果首頁

首頁標題跟隨滑鼠移動產生微妙的視差效果，使用 `useMotionValue` 和 `useSpring` 實現平滑跟隨：

```tsx
const mouseX = useMotionValue(0);
const smoothX = useSpring(mouseX, { stiffness: 150, damping: 20 });
const x = useTransform(smoothX, (v) => v * 0.1);
```

### 深色模式

使用 CSS 原生 `light-dark()` 函數，搭配 Tailwind CSS 4 的 `@theme` 定義設計 token：

```css
@theme {
  --color-background: light-dark(var(--color-stone-50), var(--color-black));
  --color-foreground: light-dark(
    var(--color-neutral-950),
    var(--color-neutral-50)
  );
}
```

不需要 JavaScript 切換，完全跟隨系統設定。

## 技術亮點

### Feature-Sliced Design 架構

採用分層架構，職責清晰：

```text
src/
├── app/        # 入口、路由
├── features/   # 頁面級功能（各自有 components 子目錄）
├── shared/     # 共用元件和工具
├── data/       # 靜態資料和型別
└── styles/     # 全域 CSS 和設計 token
```

高層可以依賴低層，反過來不行。

### Framer Motion 動畫模式

**Stagger 動畫**：列表項目依序淡入

```tsx
variants={{
  visible: { transition: { staggerChildren: 0.08 } }
}}
```

**Hover Propagation**：父元件 hover 時子元件聯動

```tsx
<motion.div whileHover="hover">
  <motion.span variants={{ hover: { x: -6 } }}>
    <ChevronLeft />
  </motion.span>
</motion.div>
```

### PWA 離線支援

使用 VitePWA 實現：

- Service Worker 快取靜態資源
- 自動更新機制
- 可安裝到桌面

## 專案連結

- **線上版本**: [spotless.pages.dev](https://spotless.pages.dev)
- **原始碼**: [github.com/uigleki/collection](https://github.com/uigleki/collection)
