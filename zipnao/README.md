# zipnao

修復 CJK（中日韓）字符編碼問題的桌面工具 - 基於字符頻率分析的智能編碼檢測。

**技術棧**: Flutter, Dart, Provider (MVVM), Isolate 並行計算

## 為什麼做這個專案

解壓縮檔案時檔名變成亂碼，是 CJK 用戶的日常痛點。問題根源是 ZIP 格式不儲存編碼資訊，Windows 用 GBK、macOS 用 UTF-8，跨平台傳輸就炸了。

傳統工具（如 Python chardet）對 CJK 文字的檢測準確率很低，經常返回 0.01 的信心度然後猜 windows-1252。因為 CJK 編碼之間可以互相解碼而不報錯，靠錯誤檢測行不通。

所以我用「字符頻率分析」來解決：用真實語料庫的字頻數據，判斷哪個解碼結果最像真正的中文/日文/韓文。

### 為什麼從 Python 遷移到 Flutter

原本用 Python + PyQt 實現，功能完整但打包後超過 100MB。對一個簡單的編碼修復工具來說太臃腫了。

Flutter 桌面版只需要約 20MB，而且：

- 原生編譯，啟動速度快
- 跨平台一套代碼（雖然目前只發布 Windows）
- 想藉機學習 Flutter 桌面開發

## 核心功能

### 1. 字符頻率分析檢測

**為什麼傳統方法失敗**：

```text
傳統 chardet 的問題：
- GBK 編碼的「測試」可以被 Big5 解碼成其他字（不報錯）
- 沒有錯誤 ≠ 正確編碼
- chardet 對 CJK 經常返回 confidence: 0.01
```

**我的方法**：

```dart
// 1. 用所有支援的編碼解碼
for (final encoding in SourceEncoding.values) {
  final decoded = decodeBytes(bytes, encoding);

  // 2. 計算解碼結果的「像真話程度」
  final score = calculateFrequencyScore(decoded, encoding.language);

  results.add(EncodingResult(encoding, score, decoded));
}

// 3. 分數最高的最可能正確
results.sort((a, b) => b.score.compareTo(a.score));
```

**字頻數據來源**：[Wordfreq](https://github.com/rspeer/wordfreq) 語料庫，包含真實的中日韓文字使用頻率。

### 2. 支援 ZIP 和純文字

**ZIP 檔案**：提取所有檔名的原始字節，檢測編碼後解壓縮到正確的檔名。

**純文字**：讀取文件內容，轉換成 UTF-8 存檔。

```dart
// ZIP：從檔頭直接讀取原始檔名字節
final nameBytes = bytes.sublist(nameStart, nameEnd);

// TXT：讀取前 10KB 做檢測（避免大文件卡頓）
final bytesToRead = min(length, 10000);
```

### 3. 視覺化信心度

不只告訴你「最可能是 GBK」，還顯示所有編碼的分數排名和預覽。讓用戶能自己判斷哪個解碼結果正確。

## 技術亮點

### MVVM 架構 + Provider

清晰的分層設計：

```text
lib/
├── ui/                 # View 層
│   └── home/
│       ├── home_screen.dart      # View
│       ├── home_viewmodel.dart   # ViewModel
│       └── widgets/              # 子元件
├── domain/             # Domain 層（模型）
├── data/               # Data 層
│   ├── repositories/   # 資料存取
│   └── services/       # 業務邏輯
└── di/                 # 依賴注入
```

**ViewModel 負責狀態管理**：

```dart
class HomeViewModel extends ChangeNotifier {
  // 狀態
  FileInfo? _fileInfo;
  List<EncodingResult> _results = [];
  bool _isLoading = false;

  // 命令
  Future<void> selectFile(String path) async {
    _fileInfo = FileInfo(path: path);
    _isLoading = true;
    notifyListeners();

    await _detectEncoding();

    _isLoading = false;
    notifyListeners();
  }
}
```

### Isolate 並行計算

編碼檢測是 CPU 密集型操作，放在主線程會卡 UI。用 `compute` 把計算丟到獨立 Isolate：

```dart
Future<List<EncodingResult>> detect(Uint8List bytes) {
  final params = _DetectionParams(bytes: bytes, frequencyData: _frequencyData);
  return compute(_detectInIsolate, params);  // 在獨立線程執行
}
```

**注意**：傳給 Isolate 的資料必須可序列化，所以 `FrequencyData` 設計成純數據類。

### Result 類型

用 Sealed Class 實現類型安全的錯誤處理：

```dart
sealed class Result<T, E> {
  R when<R>({
    required R Function(T value) success,
    required R Function(E error) failure,
  });
}

// 使用
final result = await _zipExtractor.extract(...);
result.when(
  success: (count) => _successMessage = 'Extracted $count files',
  failure: (error) => _error = error,
);
```

比起 try-catch 到處飛，這樣更明確地處理成功/失敗兩種情況。

### 現代 Dart 特性

**Pattern Matching**：

```dart
String? decodeBytes(Uint8List bytes, SourceEncoding encoding) {
  return switch (encoding) {
    SourceEncoding.utf8 => utf8.decode(bytes, allowMalformed: true),
    SourceEncoding.gbk => gbk.decode(bytes),
    SourceEncoding.big5 => _big5Decoder.convert(bytes),
    // ...
  };
}
```

**Record + Destructuring**：

```dart
(IconData, String) get _content {
  if (isLoading) return (Icons.hourglass_empty, 'Detecting...');
  if (hasFile) return (Icons.warning_amber, 'No results');
  return (Icons.table_chart_outlined, 'Select a file');
}

final (icon, message) = _content;
```

## 測試覆蓋

為核心邏輯寫了單元測試：

```dart
test('GBK encoded text scores high for GBK', () async {
  // "测试" in GBK
  final bytes = Uint8List.fromList([0xB2, 0xE2, 0xCA, 0xD4]);
  final results = await detector.detect(bytes);

  final gbkResult = results.firstWhere((r) => r.encoding == SourceEncoding.gbk);
  expect(gbkResult.score, greaterThan(0));
});
```

測試範圍：編碼檢測、檔案類型判斷、字頻查詢、Result 類型。

## 專案連結

- **原始碼**: [github.com/uigleki/zipnao](https://github.com/uigleki/zipnao)
- **下載**: [Releases](https://github.com/uigleki/zipnao/releases/latest)

## 反思

### 學到什麼

**Flutter 桌面開發**：

- 生態系還在發展中，有些套件對桌面支援不完整
- 但基本功能都能實現，打包體積確實比 Python 小很多
- `window_manager` 套件讓視窗管理變得簡單

**編碼檢測算法**：

- 傳統的「錯誤檢測」對 CJK 無效
- 統計方法（字頻分析）雖然不完美，但準確率高很多
- 讓用戶看到預覽結果很重要，機器判斷不一定對

**架構設計**：

- MVVM 在 Flutter 中用 Provider 實現很自然
- Isolate 的限制（只能傳純數據）會影響類的設計
- Sealed Class 讓錯誤處理更明確

### 可以改進的地方

- 目前只支援 Windows，可以加 macOS/Linux
- 字頻數據用 MessagePack 打包，啟動時需要載入，可以考慮懶加載
- UI 比較基礎，沒有花時間做動畫和視覺優化
