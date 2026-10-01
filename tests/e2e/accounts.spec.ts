import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("register, create a private draft, update profile and logout", async ({ page, context }) => {
  await page.goto("/studio");
  await expect(page).toHaveURL(/\/account$/);
  await page.getByRole("button", { name: "沒有帳號，建立帳號" }).click();
  await page.getByLabel("帳號", { exact: true }).fill(`browser_${randomUUID().replaceAll("-", "")}`);
  await page.getByLabel("顯示名稱").fill("瀏覽器使用者");
  await page.getByLabel("密碼", { exact: true }).fill("browser_fixture_password_123");
  const registration = page.waitForResponse((response) =>
    response.request().method() === "POST" &&
    new URL(response.url()).pathname === "/api/v1/auth/register",
  );
  await page.getByRole("button", { name: "註冊", exact: true }).click();
  expect((await registration).status()).toBe(201);
  await expect(page.getByRole("heading", { name: "我的帳號" })).toBeVisible();
  await page.getByLabel("顯示名稱").fill("新的顯示名稱");
  await page.getByRole("button", { name: "儲存個人資料" }).click();
  await expect(page.getByRole("status")).toHaveText("個人資料已更新。");
  await page.getByRole("link", { name: "我的應用", exact: true }).click();
  await page.getByLabel("名稱", { exact: true }).fill("我的私有應用");
  await page.getByLabel("介紹").fill("測試草稿");
  await page.getByRole("button", { name: "儲存草稿" }).click();
  await expect(page.getByRole("heading", { name: "我的私有應用", exact: true })).toBeVisible();
  await page.getByLabel("名稱", { exact: true }).fill("修改後的應用");
  await page.getByRole("button", { name: "儲存草稿" }).click();
  await expect(page.getByRole("heading", { name: "修改後的應用", exact: true })).toBeVisible();
  const guest = await context.browser()!.newContext();
  try {
    const response = await guest.request.get(`${process.env.WEB_ORIGIN}/api/v1/apps`);
    expect(response.status()).toBe(200);
    expect((await response.json()).some((item: { name: string }) => item.name === "修改後的應用")).toBe(false);
  } finally { await guest.close(); }
  await page.getByRole("link", { name: "新的顯示名稱", exact: true }).click();
  await page.getByRole("button", { name: "登出", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已登出。");
  await page.goto("/studio");
  await expect(page).toHaveURL(/\/account$/);
});

test("all drafts remain reachable after the first twenty", async ({ page }) => {
  const origin = process.env.WEB_ORIGIN!;
  const registered = await page.request.post(`${origin}/api/v1/auth/register`, {
    headers: { Origin: origin }, data: { account: `pages_${randomUUID().replaceAll("-", "")}`,
      password: "pagination_fixture_password_123", display_name: "分頁測試" },
  });
  expect(registered.status()).toBe(201);
  const identity = await registered.json();
  for (let index = 0; index < 21; index++) {
    const response = await page.request.post(`${origin}/api/v1/apps`, {
      headers: { Origin: origin, "X-CSRF-Token": identity.csrf_token },
      data: { title: `草稿 ${index}`, description: "分頁驗收" },
    });
    expect(response.status()).toBe(201);
  }
  await page.goto("/studio");
  await expect(page.getByRole("listitem")).toHaveCount(20);
  await page.getByRole("button", { name: "載入更多應用" }).click();
  await expect(page.getByRole("listitem")).toHaveCount(21);
  await expect(page.getByRole("button", { name: "載入更多應用" })).toHaveCount(0);
});
