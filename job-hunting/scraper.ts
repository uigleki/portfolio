import Database from "better-sqlite3";
import { mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { Page } from "playwright";
import { chromium } from "playwright-extra";
import stealth from "puppeteer-extra-plugin-stealth";

chromium.use(stealth());

const SEARCH_URL_TEMPLATE =
  "https://www.104.com.tw/jobs/search/?page=1&jobcat=2007001004&jobsource=joblist_search&mode=l&searchJobs=1&sctp=M&scmin=35000&scstrict=1&scneg=1&indcat=1001000000&searchTempExclude=2&edu=4&jobexp=1&ro=1&order=15";

interface JobData {
  title: string;
  companyName: string;
  companyLink: string;
  description: string;
  requirement: string;
  benefits: string;
}

interface CompanyData {
  intro: string;
  serve: string;
  history: string;
}

// Extract job ID from URL like "/job/abc123?query"
const extractJobId = (jobLink: string) => jobLink.match(/\/job\/([^/?]+)/)![1];

const buildSearchUrl = (pageNum: number): string =>
  SEARCH_URL_TEMPLATE.replace(/page=\d+/, `page=${pageNum}`);

async function getText(page: Page, selector: string): Promise<string> {
  return (await page.locator(selector).first().textContent())!.trim();
}

async function getOptionalText(page: Page, selector: string): Promise<string> {
  const locator = page.locator(selector);
  const count = await locator.count();
  if (count === 0) return "";
  return (await locator.first().textContent())!.trim();
}

class JobDatabase {
  private db: Database.Database;

  constructor() {
    this.db = new Database("jobs.db");
    this.db.exec(
      `CREATE TABLE IF NOT EXISTS processed_jobs (job_id TEXT PRIMARY KEY)`
    );
  }

  isProcessed(jobId: string): boolean {
    return !!this.db
      .prepare("SELECT 1 FROM processed_jobs WHERE job_id = ?")
      .get(jobId);
  }

  markProcessed(jobId: string) {
    this.db
      .prepare("INSERT OR IGNORE INTO processed_jobs (job_id) VALUES (?)")
      .run(jobId);
  }

  close() {
    this.db.close();
  }
}

async function getJobLinks(page: Page, pageNum: number): Promise<string[]> {
  await page.goto(buildSearchUrl(pageNum));

  const locator = page.locator(
    '.vue-recycle-scroller__item-wrapper a[href*="/job/"]'
  );
  await locator.first().waitFor();
  return await locator.evaluateAll((els) => els.map((el) => el.href));
}

async function getTotalPages(page: Page): Promise<number> {
  const text = await getText(
    page,
    ".multiselect__option.d-flex.align-items-center"
  );
  return parseInt(text.split("/")[1]);
}

async function getJobData(page: Page, jobLink: string): Promise<JobData> {
  await page.goto(jobLink);

  return {
    title: await getText(page, ".d-inline"),
    companyName: await getText(page, ".btn-link.t3"),
    companyLink: (await page
      .locator(".btn-link.t3")
      .first()
      .getAttribute("href"))!,
    description: await getText(page, ".job-description-table"),
    requirement: await getText(page, ".job-requirement"),
    benefits: await getOptionalText(page, ".benefits"),
  };
}

async function getCompanyData(
  page: Page,
  companyLink: string
): Promise<CompanyData> {
  await page.goto(companyLink);

  return {
    intro: await getText(page, ".intro"),
    serve: await getOptionalText(page, ".serve"),
    history: await getOptionalText(page, ".histroy"),
  };
}

async function saveJobAsMarkdown(
  jobId: string,
  jobLink: string,
  jobData: JobData,
  companyData: CompanyData
): Promise<void> {
  const markdown = `# ${jobData.title}

職缺編號: ${jobId}
公司名稱: ${jobData.companyName}

## 工作內容

${jobData.description}

## 條件要求

${jobData.requirement}

## 福利制度

${jobData.benefits || "無資料"}

## 公司資訊

### 公司介紹

${companyData.intro}

### 主要服務

${companyData.serve || "無資料"}

### 公司發展歷程

${companyData.history || "無資料"}

---

抓取時間: ${new Date().toLocaleString("zh-TW")}
工作連結: ${jobLink}
公司連結: ${jobData.companyLink}
`;

  const outputDir = join(process.cwd(), "jobs");
  await mkdir(outputDir, { recursive: true });
  await writeFile(join(outputDir, `${jobId}.md`), markdown, "utf-8");
  console.log(`    ✅ 已儲存: ${jobId}.md`);
}

async function main() {
  const MAX_JOBS = 1000;
  const db = new JobDatabase();

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  let pageNum = 1;
  let totalPages = 1;
  let createdCount = 0;

  // Use labeled statement to break outer loop when reaching MAX_JOBS
  outer: do {
    console.log(
      `\n正在抓取第 ${pageNum}${totalPages > 1 ? `/${totalPages}` : ""} 頁...`
    );

    const jobLinks = await getJobLinks(page, pageNum);
    console.log(`找到 ${jobLinks.length} 個職缺`);

    if (pageNum === 1) {
      totalPages = await getTotalPages(page);
      console.log(`總共 ${totalPages} 頁`);
    }

    for (const jobLink of jobLinks) {
      const jobId = extractJobId(jobLink);

      if (db.isProcessed(jobId)) {
        console.log(`  [${jobId}] 已處理，跳過`);
        continue;
      }

      console.log(`  [${jobId}] 處理中...`);

      const jobData = await getJobData(page, jobLink);
      const companyData = await getCompanyData(page, jobData.companyLink);
      await saveJobAsMarkdown(jobId, jobLink, jobData, companyData);

      db.markProcessed(jobId);
      createdCount++;

      if (createdCount >= MAX_JOBS) {
        console.log(`\n已創建 ${createdCount} 個職缺檔案，達到上限，停止抓取`);
        break outer;
      }
    }

    pageNum++;
  } while (pageNum <= totalPages);

  db.close();
  await context.close();
  await browser.close();
  console.log(`\n✅ 完成！共創建 ${createdCount} 個職缺檔案`);
}

main();
