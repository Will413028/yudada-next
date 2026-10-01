import { expect, test, type Browser, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { randomUUID } from "node:crypto";

const password = "browser_product_fixture_password_123";
const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAJCAIAAACAMfp5AAAAFElEQVR4nGNkYPjPgA0wYRUdehIA5ewBEaLAl18AAAAASUVORK5CYII=", "base64");
const content = { questions: [{ title: "喜歡哪種學習方式？", options: [
  { key: "A", text: "獨立探索", property: "I", score: 0 }, { key: "B", text: "一起交流", property: "E", score: 1 },
] }], rules: [{ name: "探索型", properties: ["I"] }, { name: "交流型", properties: ["E"] }] };

async function administrator(browser: Browser) {
  const account = `browser_admin_${randomUUID().replaceAll("-", "")}`;
  const api = resolve(process.cwd(), "apps/api");
  execFileSync("uv", ["run", "--no-sync", "--project", api, "python", "tests/create_browser_admin.py", account], { cwd: api });
  const context = await browser.newContext();
  const page = await context.newPage();
  const origin = process.env.WEB_ORIGIN!;
  const login = await page.request.post(`${origin}/api/v1/auth/login`, {
    headers: { Origin: origin }, data: { account, password: "browser_admin_fixture_password_123" },
  });
  expect(login.status()).toBe(200);
  const identity = await login.json();
  return { context, page, csrf: identity.csrf_token as string };
}

async function owner(page: Page) {
  const origin = process.env.WEB_ORIGIN!;
  const account = `browser_product_${randomUUID().replaceAll("-", "")}`;
  const registered = await page.request.post(`${origin}/api/v1/auth/register`, {
    headers: { Origin: origin }, data: { account, password, display_name: "產品驗收使用者" },
  });
  expect(registered.status()).toBe(201);
  const identity = await registered.json();
  const headers = { Origin: origin, "X-CSRF-Token": identity.csrf_token as string };
  const title = `分享應用_${randomUUID().slice(0, 8)}`;
  const created = await page.request.post(`${origin}/api/v1/apps`, { headers, data: { title, content } });
  expect(created.status()).toBe(201);
  return { account, headers, title, appId: (await created.json()).app_id as string };
}

test("creator uploads a cover, publishes through admin review, shares and restores the app", async ({ page, browser }) => {
  const origin = process.env.WEB_ORIGIN!;
  const fixture = await owner(page);
  const admin = await administrator(browser);
  try {
    await page.goto(`/studio?app=${fixture.appId}`);
    const upload = page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/uploads");
    await page.getByLabel("應用封面", { exact: true }).setInputFiles({ name: "cover.png", mimeType: "image/png", buffer: png });
    expect((await upload).status()).toBe(201);
    await expect(page.getByAltText("應用封面", { exact: true })).toBeVisible();
    const save = page.waitForResponse((response) => response.request().method() === "PATCH" && response.url().endsWith("/draft"));
    await page.getByRole("button", { name: "儲存草稿", exact: true }).click();
    expect((await save).status()).toBe(200);
    await expect(page.getByRole("status", { name: "草稿儲存狀態" })).toHaveText("草稿已儲存。");
    const submission = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/submissions"));
    await page.getByRole("button", { name: "送出審核", exact: true }).click();
    expect((await submission).status()).toBe(201);
    await expect(page.getByRole("status", { name: "發布狀態" })).toContainText("已送出審核");
    expect((await page.request.get(`${origin}/api/v1/apps/${fixture.appId}`)).status()).toBe(404);
    await admin.page.goto("/admin");
    const review = admin.page.getByRole("listitem").filter({ has: admin.page.getByRole("heading", { name: `${fixture.title} · 版本 1`, exact: true }) });
    await expect.poll(() => review.getByAltText(`${fixture.title}審核封面`).evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    const approval = admin.page.waitForResponse((response) => response.request().method() === "POST" && new URL(response.url()).pathname.startsWith("/api/v1/admin/reviews/"));
    await review.getByRole("button", { name: "確認審核" }).click();
    expect((await approval).status()).toBe(200);
    await page.goto(`/apps/${fixture.appId}`);
    await expect(page.getByRole("heading", { name: fixture.title, exact: true })).toBeVisible();
    const cover = page.getByAltText(`${fixture.title}封面`);
    await expect.poll(() => cover.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    await page.getByRole("button", { name: "分享應用", exact: true }).click();
    await expect(page.getByLabel("分享連結")).toHaveValue(`${origin}/apps/${fixture.appId}`);
    const qr = page.getByAltText("應用分享 QR Code");
    await expect.poll(() => qr.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    await page.getByLabel("獨立探索", { exact: true }).check();
    const answer = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/answers"));
    await page.getByRole("button", { name: "提交答案" }).click();
    expect((await answer).status()).toBe(201);
    await page.getByRole("link", { name: "查看結果" }).click();
    await expect(page.getByRole("heading", { name: "探索型" })).toBeVisible();
    await page.goto("/");
    await page.getByLabel("搜尋應用").fill(fixture.title);
    await page.getByRole("button", { name: "搜尋", exact: true }).click();
    await expect(page.getByRole("heading", { name: fixture.title, exact: true })).toBeVisible();
    await page.goto(`/studio?app=${fixture.appId}`);
    const deletion = page.waitForResponse((response) => response.request().method() === "DELETE" && response.url().endsWith(fixture.appId));
    await page.getByRole("button", { name: "移至已刪除", exact: true }).click();
    expect((await deletion).status()).toBe(204);
    await expect(page).toHaveURL(/\/studio\?deleted=1$/);
    await expect(page.getByRole("heading", { name: fixture.title, exact: true })).toBeVisible();
    const restoration = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/restore"));
    await page.getByRole("button", { name: "恢復為未公開", exact: true }).click();
    expect((await restoration).status()).toBe(204);
    expect((await page.request.get(`${origin}/api/v1/apps/${fixture.appId}`)).status()).toBe(404);
    await page.goto(`/studio?app=${fixture.appId}`);
    const republish = page.waitForResponse((response) => response.request().method() === "POST" && response.url().endsWith("/publish"));
    await page.getByRole("button", { name: "公開此核准版本", exact: true }).click();
    expect((await republish).status()).toBe(204);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/apps/${fixture.appId}`);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: ".artifacts/publication-mobile.png", fullPage: true });
  } finally {
    await page.request.delete(`${origin}/api/v1/apps/${fixture.appId}`, { headers: fixture.headers });
    await admin.context.close();
  }
});

test("admin manages draft content and revokes sessions when disabling an account", async ({ page, browser }) => {
  const origin = process.env.WEB_ORIGIN!;
  const fixture = await owner(page);
  const admin = await administrator(browser);
  try {
    expect((await page.goto("/admin"))!.status()).toBe(404);
    await admin.page.goto(`/admin?tab=apps&q=${fixture.title}`);
    await admin.page.getByRole("link", { name: "編輯內容草稿" }).click();
    await expect(admin.page.getByLabel("名稱", { exact: true })).toHaveValue(fixture.title);
    await admin.page.getByLabel("介紹").fill("管理者修改草稿");
    const save = admin.page.waitForResponse((response) => response.request().method() === "PATCH" && response.url().endsWith("/draft"));
    await admin.page.getByRole("button", { name: "儲存草稿", exact: true }).click();
    expect((await save).status()).toBe(200);
    await admin.page.goto("/admin?tab=questions");
    await expect(admin.page.getByRole("heading", { name: "題目管理", exact: true })).toBeVisible();
    await admin.page.goto("/admin?tab=rules");
    await expect(admin.page.getByRole("heading", { name: "評分規則管理", exact: true })).toBeVisible();
    await admin.page.goto(`/admin?tab=users&q=${fixture.account}`);
    await admin.page.getByLabel("帳號啟用").uncheck();
    const disable = admin.page.waitForResponse((response) => response.request().method() === "PATCH" && new URL(response.url()).pathname.startsWith("/api/v1/admin/users/"));
    await admin.page.getByRole("button", { name: "儲存使用者", exact: true }).click();
    expect((await disable).status()).toBe(200);
    expect((await page.request.get(`${origin}/api/v1/auth/me`)).status()).toBe(401);
    await expect(admin.page.getByLabel("帳號啟用")).not.toBeChecked();
    await admin.page.getByLabel("帳號啟用").check();
    const restore = admin.page.waitForResponse((response) => response.request().method() === "PATCH" && new URL(response.url()).pathname.startsWith("/api/v1/admin/users/"));
    await admin.page.getByRole("button", { name: "儲存使用者", exact: true }).click();
    expect((await restore).status()).toBe(200);
    expect((await page.request.get(`${origin}/api/v1/auth/me`)).status()).toBe(401);
    const login = await page.request.post(`${origin}/api/v1/auth/login`, { headers: { Origin: origin }, data: { account: fixture.account, password } });
    expect(login.status()).toBe(200);
    fixture.headers["X-CSRF-Token"] = (await login.json()).csrf_token;
  } finally {
    await admin.page.request.delete(`${origin}/api/v1/apps/${fixture.appId}`, { headers: { Origin: origin, "X-CSRF-Token": admin.csrf } });
    await admin.context.close();
  }
});
