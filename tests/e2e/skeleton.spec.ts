import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

test("database fixture reaches SSR and same-origin browser client", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "探索你的學習風格", exact: true })).toBeVisible();
  const response = page.waitForResponse((res) => res.url().endsWith("/api/v1/apps"));
  await page.getByRole("button", { name: "更新列表" }).click();
  expect((await response).status()).toBe(200);
  await expect(page.getByRole("status")).toHaveText("已更新：探索你的學習風格");
  const api = resolve(process.cwd(), "apps/api");
  function seed(name: string) {
    execFileSync("uv", ["run", "--no-sync", "--project", api, "python", "-m", "scripts.seed", "--name", name], { cwd: api });
  }
  try {
    seed("資料更新後的應用");
    await page.getByRole("button", { name: "更新列表" }).click();
    await expect(page.getByRole("heading", { name: "資料更新後的應用", exact: true })).toBeVisible();
  } finally {
    seed("探索你的學習風格");
  }
  await page.getByRole("button", { name: "更新列表" }).click();
  await expect(page.getByRole("heading", { name: "探索你的學習風格", exact: true })).toBeVisible();
  await page.screenshot({ path: ".artifacts/skeleton-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "探索你的學習風格", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: ".artifacts/skeleton-mobile.png", fullPage: true });
  const docs = await page.request.get("/api/v1/docs");
  expect(docs.status()).toBe(200);
  expect(await docs.text()).toContain("/api/v1/openapi.json");
  const schema = await page.request.get("/api/v1/openapi.json");
  expect(schema.status()).toBe(200);
  expect((await schema.json()).paths).toHaveProperty("/api/v1/apps");
});
