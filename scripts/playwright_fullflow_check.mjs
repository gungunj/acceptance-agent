import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE_URL = "http://127.0.0.1:3000";
const API_BASE_URL = "http://127.0.0.1:8000";
const ROOT = "/Users/zhuhaihua/Desktop/acceptance-agent";
const ARTIFACT_DIR = path.join(ROOT, "artifacts", "playwright");
fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

const nowTag = new Date().toISOString().replaceAll(":", "-");
const reportPath = path.join(ARTIFACT_DIR, `fullflow-report-${nowTag}.json`);
const screenshotPath = path.join(ARTIFACT_DIR, `fullflow-final-${nowTag}.png`);

const uploadFile1 = path.join(ROOT, "apps", "api", "uploads", "104b19bb-7a1a-4314-94f5-b766bddbfc29.docx");
const uploadFile2 = path.join(ROOT, "apps", "api", "uploads", "0c68f384-0a5b-49ec-ac16-7322603f1de9.docx");

const steps = [];
let taskId = "";

async function runStep(name, fn) {
  const startedAt = new Date().toISOString();
  const started = Date.now();
  try {
    await fn();
    steps.push({
      name,
      status: "passed",
      started_at: startedAt,
      duration_ms: Date.now() - started,
    });
  } catch (error) {
    steps.push({
      name,
      status: "failed",
      started_at: startedAt,
      duration_ms: Date.now() - started,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

async function waitButtonEnabled(button, timeout = 60000) {
  await button.waitFor({ state: "visible", timeout });
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await button.isEnabled()) {
      return;
    }
    await page.waitForTimeout(150);
  }
  throw new Error("Button did not become enabled in time");
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
const page = await context.newPage();

try {
  await runStep("Open home page", async () => {
    await page.goto(BASE_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.getByRole("heading", { name: "创建任务并进入详情页" }).waitFor({ timeout: 15000 });
  });

  await runStep("Create task", async () => {
    const title = `PW-E2E-${Date.now()}`;
    await page.locator('input[id="title"], input[name="title"], input').first().fill(title);
    await page.locator('textarea[id="description"], textarea[name="description"], textarea').first().fill(
      "Playwright fullflow automation test",
    );
    await page.getByRole("button", { name: "创建任务" }).click();
    await page.waitForURL(/\/tasks\/.+/, { timeout: 60000 });
    const currentUrl = page.url();
    const match = currentUrl.match(/\/tasks\/([^/?#]+)/);
    if (!match) {
      throw new Error(`Could not parse task id from URL: ${currentUrl}`);
    }
    taskId = match[1];
  });

  await runStep("Upload two files", async () => {
    await page.locator('input[type="file"]').setInputFiles([uploadFile1, uploadFile2]);
    await page.getByRole("button", { name: "上传选中文件" }).click();
    await page.getByText("104b19bb-7a1a-4314-94f5-b766bddbfc29.docx").waitFor({ timeout: 60000 });
    await page.getByText("0c68f384-0a5b-49ec-ac16-7322603f1de9.docx").waitFor({ timeout: 60000 });
  });

  await runStep("Set template and asset roles", async () => {
    const templateCard = page
      .locator("article")
      .filter({ hasText: "104b19bb-7a1a-4314-94f5-b766bddbfc29.docx" })
      .first();
    const assetCard = page
      .locator("article")
      .filter({ hasText: "0c68f384-0a5b-49ec-ac16-7322603f1de9.docx" })
      .first();
    await templateCard.getByRole("button", { name: "设为模板" }).click();
    await assetCard.getByRole("button", { name: "设为素材" }).click();
  });

  await runStep("Parse template and confirm", async () => {
    const parseTemplateBtn = page.getByRole("button", { name: "解析模板(生成节点)" });
    await waitButtonEnabled(parseTemplateBtn);
    await parseTemplateBtn.click();
    await page.locator("text=nodes").first().waitFor({ timeout: 60000 });
    const confirmBtn = page.getByRole("button", { name: "确认模板" });
    await waitButtonEnabled(confirmBtn);
    await confirmBtn.click();
    await page.getByRole("button", { name: /已确认|确认模板/ }).waitFor({ timeout: 30000 });
  });

  await runStep("Parse materials", async () => {
    const btn = page.getByRole("button", { name: "1) 解析素材" });
    await waitButtonEnabled(btn);
    await btn.click();
    await page.getByText(/素材单元/).first().waitFor({ timeout: 60000 });
  });

  await runStep("Match fill nodes", async () => {
    const btn = page.getByRole("button", { name: "2) 匹配 fill 节点" });
    await waitButtonEnabled(btn);
    await btn.click();
    await page.getByText(/Fill 节点候选匹配/).first().waitFor({ timeout: 60000 });
    await waitButtonEnabled(page.getByRole("button", { name: "3) 解析 fill 结果" }), 60000);
  });

  await runStep("Resolve fill results", async () => {
    const btn = page.getByRole("button", { name: "3) 解析 fill 结果" });
    await waitButtonEnabled(btn);
    await btn.click();
    await page.getByText(/Fill Node Results/).first().waitFor({ timeout: 60000 });
    await waitButtonEnabled(page.getByRole("button", { name: "4) 生成缺口清单" }), 60000);
  });

  await runStep("Generate gaps", async () => {
    const btn = page.getByRole("button", { name: "4) 生成缺口清单" });
    await waitButtonEnabled(btn);
    await btn.click();
    await page.getByText(/Gap Items/).first().waitFor({ timeout: 60000 });
    await waitButtonEnabled(page.getByRole("button", { name: "5) 生成章节草稿" }), 60000);
  });

  await runStep("Generate section drafts", async () => {
    const btn = page.getByRole("button", { name: "5) 生成章节草稿" });
    await waitButtonEnabled(btn);
    await btn.click();
    await page.getByText(/Section Drafts/).first().waitFor({ timeout: 60000 });
    await waitButtonEnabled(page.getByRole("button", { name: "6) 构建 resolved template" }), 60000);
  });

  await runStep("Build resolved template", async () => {
    const btn = page.getByRole("button", { name: "6) 构建 resolved template" });
    await waitButtonEnabled(btn);
    await btn.click();
    await page.getByText(/Resolved Template/).first().waitFor({ timeout: 60000 });
  });

  await runStep("Export markdown and html", async () => {
    const exportMdBtn = page.getByRole("button", { name: "导出 Markdown" });
    await waitButtonEnabled(exportMdBtn);
    await exportMdBtn.click();
    await page.getByText(/Markdown 预览/).first().waitFor({ timeout: 60000 });
    const exportHtmlBtn = page.getByRole("button", { name: "导出 HTML" });
    await waitButtonEnabled(exportHtmlBtn);
    await exportHtmlBtn.click();
    await page.getByText(/HTML 导出/).first().waitFor({ timeout: 60000 });
  });

  await runStep("Verify key API endpoints", async () => {
    const check = async (url) => {
      const response = await page.request.get(url);
      if (!response.ok()) {
        throw new Error(`${url} returned ${response.status()}`);
      }
    };
    await check(`${API_BASE_URL}/api/tasks/${taskId}/resolved-template`);
    await check(`${API_BASE_URL}/api/tasks/${taskId}/export-markdown`);
    await check(`${API_BASE_URL}/api/tasks/${taskId}/export-html`);
  });

  await page.screenshot({ path: screenshotPath, fullPage: true });
} catch (error) {
  await page.screenshot({ path: screenshotPath, fullPage: true });
} finally {
  await browser.close();
}

const passed = steps.filter((step) => step.status === "passed").length;
const failed = steps.filter((step) => step.status === "failed").length;

const report = {
  generated_at: new Date().toISOString(),
  task_id: taskId || null,
  summary: {
    total_steps: steps.length,
    passed_steps: passed,
    failed_steps: failed,
    overall_status: failed === 0 ? "passed" : "failed",
  },
  artifacts: {
    screenshot: screenshotPath,
  },
  steps,
};

fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), "utf-8");
console.log(JSON.stringify({ report_path: reportPath, ...report.summary }, null, 2));
