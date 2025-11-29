import { GoogleGenAI } from "@google/genai";
import fs from "fs";
import path from "path";
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";

const evaluationSchema = z.object({
  recommend: z.boolean().describe("是否建議投遞此職缺"),
  reasons: z
    .array(z.string())
    .describe("判斷理由列表，每條一句話說清楚一個關鍵點"),
});
type EvaluationResult = z.infer<typeof evaluationSchema>;

const ai = new GoogleGenAI({});
const resume = fs.readFileSync("prompts/resume.md", "utf-8");

// Gemini API returns double-encoded JSON string
const parseGeminiJSON = (text: string) => JSON.parse(JSON.parse(text));

function getJobFiles() {
  const jobsDir = "jobs";
  if (!fs.existsSync(jobsDir)) return [];

  return fs
    .readdirSync(jobsDir)
    .filter((f) => f.endsWith(".md"))
    .map((file) => ({
      jobId: path.basename(file, ".md"),
      filePath: path.join(jobsDir, file),
      content: fs.readFileSync(path.join(jobsDir, file), "utf-8"),
    }));
}

function buildEvaluationPrompt(jobContent: string): string {
  return `
你是職缺評估專家。仔細分析以下履歷與職缺內容，綜合評估是否值得投遞。

必須輸出 JSON 格式：{ "recommend": boolean, "reasons": string[] }

<resume>
${resume}
</resume>

<job>
${jobContent}
</job>

<evaluation_criteria>
## 硬性門檻（任一不符就不推薦）
- **英文要求**：英文為中等水平，能閱讀技術文檔，但無法流利進行全英文口語溝通。
- **硬性技能**：若要求「必須XX年經驗」、「精通YY」且態度強硬，而完全沒接觸過該技術，則不適合。「熟悉優先」或「願意學習」可接受。
- **注意**：目前可隨時上班。不要判斷「可上班時間衝突」。

## 匹配度分析
- **新人友善**：明確「歡迎應屆生」、「提供培訓/導師」、「成長空間」最佳。
- **技術環境**：偏好現代技術（Go/Rust/雲端原生/微服務），代表公司先進、少包袱、好維護。成熟技術棧若公司優質也可。
- **公司品質**：大公司/知名公司優先，更可靠。小公司需謹慎評估。

## 工作條件權衡
- **薪資與強度**：高薪可接受高強度。普通薪資但壓力大則扣分。
- **公司文化**：「扁平化」、「技術分享」、「鼓勵學習」等，知名公司較可信，小公司可能話術但也是正面信號。
- **福利**：基本勞健保必備。團保/三節/年終/彈性工時加分。
- **職缺描述清晰度**：若非常模糊（「協助專案」、「支援團隊」）可能是打雜或外包，需扣分。
</evaluation_criteria>

根據以上標準進行多維度思考，給出判斷。

**理由撰寫規則**：
- 每條最多 50 字
- 禁止使用「應徵者」「求職者」「履歷顯示」等冗詞
- 直接陳述關鍵事實，不過度解釋
- 範例：
  ✅ "明確歡迎應屆生，提供導師制度"
  ✅ "技術棧 Go/K8s/微服務，環境先進"
  ❌ "求職者在履歷中展現的技術能力與職缺要求高度匹配"

必須輸出 JSON 格式：{ "recommend": boolean, "reasons": string[] }
`;
}

async function evaluateJob(job: {
  jobId: string;
  content: string;
}): Promise<EvaluationResult> {
  const response = await ai.models.generateContent({
    model: "gemini-2.5-flash",
    contents: buildEvaluationPrompt(job.content),
    config: {
      responseMimeType: "application/json",
      responseJsonSchema: zodToJsonSchema(evaluationSchema),
      temperature: 0.1,
    },
  });

  const result = evaluationSchema.parse(parseGeminiJSON(response.text!));

  console.log(`\n${result.recommend ? "✅ 推薦" : "❌ 不推薦"}：${job.jobId}`);
  result.reasons.forEach((r, i) => console.log(`  ${i + 1}. ${r}`));

  return result;
}

function moveJobFile(jobPath: string, jobId: string, recommend: boolean) {
  const targetDir = recommend ? "data/jobs" : "data/trash";
  fs.mkdirSync(targetDir, { recursive: true });
  fs.renameSync(jobPath, path.join(targetDir, `${jobId}.md`));
}

function updateRecommended(
  job: { jobId: string; content: string },
  evaluation: EvaluationResult
) {
  fs.mkdirSync("data", { recursive: true });
  const target = "data/recommended.md";

  const title = job.content.split("\n")[0].replace(/^#\s*/, "") || job.jobId;
  const entry =
    `## ${job.jobId}: ${title}\n` +
    evaluation.reasons.map((r) => `- ${r}`).join("\n") +
    "\n\n";

  const existing = fs.existsSync(target)
    ? fs.readFileSync(target, "utf-8")
    : "";
  fs.writeFileSync(target, entry + existing, "utf-8");
}

async function main() {
  const jobs = getJobFiles();
  if (!jobs.length) {
    console.log("⚠️  沒有待評估職缺");
    return;
  }

  console.log(`找到 ${jobs.length} 個職缺，開始分析...\n`);

  let recommendedCount = 0;

  for (const job of jobs) {
    const result = await evaluateJob(job);
    moveJobFile(job.filePath, job.jobId, result.recommend);

    if (result.recommend) {
      updateRecommended(job, result);
      recommendedCount++;
    }
  }

  console.log(
    `\n✅ 完成！共分析 ${jobs.length} 個職缺，推薦 ${recommendedCount} 個`
  );
}

main();
