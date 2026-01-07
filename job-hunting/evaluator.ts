import { GoogleGenAI } from "@google/genai";
import fs from "fs";
import path from "path";
import { z, ZodError } from "zod";

const CONFIG = {
  MODEL: "gemini-flash-latest",
  MAX_RETRIES: 3,
  JOBS_DIR: "jobs",
  DATA_DIR: "data",
  RECOMMENDED_FILE: "data/recommended.md",
  JOBS_OUTPUT_DIR: "data/jobs",
  TRASH_DIR: "data/trash",
} as const;

const evaluationSchema = z.object({
  recommend: z.boolean().describe("是否推薦投遞此職缺"),
  keyPoints: z.array(z.string()).describe("職缺關鍵資訊摘要列表"),
});
type EvaluationResult = z.infer<typeof evaluationSchema>;

const ai = new GoogleGenAI({});
const resume = fs.readFileSync("prompts/resume.md", "utf-8");
const criteria = fs.readFileSync("prompts/criteria.md", "utf-8");

function getJobFiles() {
  if (!fs.existsSync(CONFIG.JOBS_DIR)) return [];

  return fs
    .readdirSync(CONFIG.JOBS_DIR)
    .filter((f) => f.endsWith(".md"))
    .map((file) => ({
      jobId: path.basename(file, ".md"),
      filePath: path.join(CONFIG.JOBS_DIR, file),
      content: fs.readFileSync(path.join(CONFIG.JOBS_DIR, file), "utf-8"),
    }));
}

function buildEvaluationPrompt(jobContent: string): string {
  return `
現在時間：${new Date().toLocaleString()}

你是職缺評估專家，現在要分析台灣 104 人力銀行的職缺。請依據以下履歷與職缺內容，按照評估標準進行分析。

必須輸出純 JSON 格式：{ "recommend": boolean, "keyPoints": string[] }

<resume>
${resume}
</resume>

<job>
${jobContent}
</job>

<criteria>
${criteria}
</criteria>

必須輸出純 JSON 格式：{ "recommend": boolean, "keyPoints": string[] }
`;
}

async function evaluateJob(job: {
  jobId: string;
  content: string;
}): Promise<EvaluationResult> {
  let attempt = 0;

  while (attempt <= CONFIG.MAX_RETRIES) {
    let response;
    try {
      response = await ai.models.generateContent({
        model: CONFIG.MODEL,
        contents: buildEvaluationPrompt(job.content),
        config: {
          responseMimeType: "application/json",
          responseJsonSchema: z.toJSONSchema(evaluationSchema),
        },
      });

      const result = evaluationSchema.parse(JSON.parse(response.text!));

      console.log(
        `\n${result.recommend ? "✅ 推薦" : "❌ 不推薦"}：${job.jobId}`,
      );
      result.keyPoints.forEach((r, i) => console.log(`  ${i + 1}. ${r}`));

      return result;
    } catch (error: any) {
      attempt++;

      const isApiError = [500, 503].includes(error.status);
      const isParseError =
        error instanceof SyntaxError || error instanceof ZodError;

      if (isParseError) console.log(`[DEBUG] response.text: ${response?.text}`);

      if ((isApiError || isParseError) && attempt <= CONFIG.MAX_RETRIES) {
        const waitTime = attempt * 2;
        const errorType = isApiError ? `API ${error.status}` : "JSON 解析";
        console.log(
          `⚠️  [${job.jobId}] ${errorType}錯誤，${waitTime}秒後重試 (${attempt}/${CONFIG.MAX_RETRIES})...`,
        );
        await new Promise((resolve) => setTimeout(resolve, waitTime * 1000));
        continue;
      }

      throw error;
    }
  }

  throw new Error(`${job.jobId} 重試 ${CONFIG.MAX_RETRIES} 次後仍失敗`);
}

function moveJobFile(jobPath: string, jobId: string, recommend: boolean) {
  const targetDir = recommend ? CONFIG.JOBS_OUTPUT_DIR : CONFIG.TRASH_DIR;
  fs.mkdirSync(targetDir, { recursive: true });
  fs.renameSync(jobPath, path.join(targetDir, `${jobId}.md`));
}

function updateRecommended(
  job: { jobId: string; content: string },
  result: EvaluationResult,
) {
  fs.mkdirSync(CONFIG.DATA_DIR, { recursive: true });

  const title = job.content.match(/^#\s*(.+)/)?.[1] || job.jobId;
  const jobLink = `./jobs/${job.jobId}.md`;
  const entry =
    `## [${job.jobId}: ${title}](${jobLink})\n\n` +
    result.keyPoints.map((r) => `- ${r}`).join("\n") +
    "\n\n";

  const existing = fs.existsSync(CONFIG.RECOMMENDED_FILE)
    ? fs.readFileSync(CONFIG.RECOMMENDED_FILE, "utf-8")
    : "";
  fs.writeFileSync(CONFIG.RECOMMENDED_FILE, entry + existing, "utf-8");
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
    `\n✅ 完成！共分析 ${jobs.length} 個職缺，推薦 ${recommendedCount} 個`,
  );
}

main();
