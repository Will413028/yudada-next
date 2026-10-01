import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("published quiz keeps scoring private and records the immutable result", async ({ page }) => {
  const origin = process.env.WEB_ORIGIN!;
  const registered = await page.request.post(`${origin}/api/v1/auth/register`, {
    headers: { Origin: origin }, data: {
      account: `answers_${randomUUID().replaceAll("-", "")}`,
      password: "answers_fixture_password_123", display_name: "答題使用者",
    },
  });
  expect(registered.status()).toBe(201);
  await page.goto("/");
  await page.getByRole("link", { name: "開始探索" }).click();
  await expect(page.getByRole("heading", { name: "探索你的學習風格" })).toBeVisible();
  await page.getByLabel("先自己研究", { exact: true }).check();
  await page.getByLabel("安靜地思考", { exact: true }).check();
  await page.getByRole("button", { name: "提交答案", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("答案已提交。");
  await expect(page.getByRole("button", { name: "提交答案", exact: true })).toBeDisabled();
  await page.getByRole("link", { name: "查看結果", exact: true }).click();
  await expect(page.getByRole("heading", { name: "探索型", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "作答紀錄", exact: true }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByRole("listitem")).toContainText("探索型");
  await page.getByRole("button", { name: "隱藏紀錄" }).click();
  await expect(page.getByText("還沒有作答紀錄。", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "包含已隱藏紀錄", exact: true }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  const restore = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/restore"));
  await page.getByRole("button", { name: "恢復紀錄", exact: true }).click();
  expect((await restore).status()).toBe(204);
  await expect(page.getByRole("link", { name: "查看結果", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "查看結果", exact: true }).click();
  await expect(page.getByRole("heading", { name: "探索型", exact: true })).toBeVisible();
});

test("creator edits questions and ordered result rules without exposing the draft", async ({ page }) => {
  const origin = process.env.WEB_ORIGIN!;
  const registered = await page.request.post(`${origin}/api/v1/auth/register`, {
    headers: { Origin: origin }, data: { account: `editor_${randomUUID().replaceAll("-", "")}`,
      password: "editor_fixture_password_123", display_name: "出題作者" },
  });
  expect(registered.status()).toBe(201);
  await page.goto("/studio");
  await page.getByLabel("名稱", { exact: true }).fill("完整題目草稿");
  await page.getByRole("button", { name: "新增題目", exact: true }).click();
  await page.getByLabel("題目 1 內容", { exact: true }).fill("你如何學習？");
  await page.getByLabel("題目 1 選項 1 文字", { exact: true }).fill("自己讀書");
  await page.getByRole("button", { name: "新增結果", exact: true }).click();
  await page.getByLabel("結果 1 名稱", { exact: true }).fill("獨立型");
  await page.getByRole("button", { name: "儲存草稿", exact: true }).click();
  await expect(page.getByRole("status", { name: "草稿儲存狀態" })).toHaveText("草稿已儲存。");
  await page.reload();
  await page.getByRole("button", { name: "編輯", exact: true }).click();
  await expect(page.getByLabel("題目 1 內容", { exact: true })).toHaveValue("你如何學習？");
  await expect(page.getByLabel("題目 1 選項 1 文字", { exact: true })).toHaveValue("自己讀書");
  await expect(page.getByLabel("結果 1 名稱", { exact: true })).toHaveValue("獨立型");
  await page.getByRole("combobox", { name: "評分方式", exact: true }).selectOption("ai");
  await page.getByRole("combobox", { name: "應用類型", exact: true }).selectOption("score");
  await expect(page.getByRole("combobox", { name: "評分方式", exact: true })).toHaveValue("rules");
  await expect(page.getByRole("option", { name: "AI 評分（限測評）" })).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: ".artifacts/editor-mobile.png", fullPage: true });
});

test("saving locks the editor so another draft cannot overwrite its content", async ({ page }) => {
  const origin = process.env.WEB_ORIGIN!;
  const registered = await page.request.post(`${origin}/api/v1/auth/register`, {
    headers: { Origin: origin }, data: { account: `race_${randomUUID().replaceAll("-", "")}`,
      password: "race_fixture_password_123", display_name: "競爭驗收" },
  });
  expect(registered.status()).toBe(201);
  const identity = await registered.json();
  const ids: string[] = [];
  for (const title of ["草稿 A", "草稿 B"]) {
    const created = await page.request.post(`${origin}/api/v1/apps`, {
      headers: { Origin: origin, "X-CSRF-Token": identity.csrf_token }, data: {
        title, content: { questions: [{ title: `${title} 的題目`, options: [
          { key: "A", text: "第一選項", property: "I" }, { key: "B", text: "第二選項", property: "E" },
        ] }], rules: [{ name: title, properties: ["I"] }] },
      },
    });
    expect(created.status()).toBe(201); ids.push((await created.json()).app_id);
  }
  await page.goto("/studio");
  await page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "草稿 A", exact: true }) }).getByRole("button", { name: "編輯" }).click();
  let release!: () => void;
  let received!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const requestStarted = new Promise<void>((resolve) => { received = resolve; });
  await page.route(`**/api/v1/apps/${ids[0]}/draft`, async (route) => {
    if (route.request().method() === "PATCH") { received(); await gate; }
    await route.continue();
  });
  try {
    await page.getByRole("button", { name: "儲存草稿", exact: true }).click();
    await requestStarted;
    await expect(page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "草稿 B", exact: true }) }).getByRole("button", { name: "編輯" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "建立另一個應用" })).toBeDisabled();
    await expect(page.getByLabel("題目 1 內容", { exact: true })).toBeDisabled();
  } finally { release(); }
  await expect(page.getByRole("status", { name: "草稿儲存狀態" })).toHaveText("草稿已儲存。");
  const persisted = await page.request.get(`${origin}/api/v1/apps/${ids[0]}/draft`);
  expect((await persisted.json()).content.questions[0].title).toBe("草稿 A 的題目");
});
