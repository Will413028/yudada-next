# yudada-next

以 Next.js + FastAPI 建立完整 AI 答題 Web 平台，包含使用者端與管理端。

- 範圍與驗收見 `docs/plans/2026-10-01-full-rebuild.md`；功能來源見其附件 `docs/plans/2026-10-01-full-rebuild/inventory.md`。
- 執行命令與本機環境見 `README.md`。驗收使用 `make check`、`make test-integration`、`make test-e2e`、`make test-faults`；同一 checkout 循序執行。
- API 位於 `apps/api`，Web 位於 `apps/web`；FastAPI 是業務與權限 SSOT。SSR 轉送 Cookie 的 adapter 必須 server-only，browser 使用同源 `/api`。
- DTO 由 `make generate-client` 生成；不得手改 `apps/api/openapi.json` 或 `apps/web/src/lib/api/schema.d.ts`。改 schema 後生成並通過 drift gate。
- Migration 與 fixture seed 分離；integration/E2E 使用真實 PostgreSQL。測試 backend 不得掛入產品 API。
- 採本地帳號、密碼與 Cookie session；發布版本不可變，修改須重新審核，舊答案對應原版本。
- 從零建立，無舊部署與資料相容需求；小程序延後。
- 標為預設或待決的工具、契約不能當成已獲准的產品行為。
