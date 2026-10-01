# yudada-next

以 Next.js + FastAPI 重做 AI 答題平台，分階段學習全端產品、評分策略、AI 串流與可靠性設計。

最終範圍：建立應用、題目與評分編輯、發布審核、搜尋分享、線上答題、結果與歷史、AI 出題／評分、管理與統計。小程序延後。

已加入帳號/session、個人資料、草稿、題目與規則編輯、不可變版本、規則答題與歷史；正式發布審核、管理、圖片、搜尋及分享已接上並持續驗收。AI與統計依重做計畫接續實作，最新驗收證據只記計畫進度。

## 快速開始

需要 Docker、Node.js 24–26、pnpm（版本由 `package.json` 固定）、uv；Python 3.13 由 uv 管理。本機 gates 支援 macOS/Linux。以下命令在 repo 根目錄執行。

```bash
pnpm install --frozen-lockfile
uv sync --project apps/api --python 3.13 --frozen
pnpm exec playwright install chromium
docker pull postgres:17-alpine
make dev
```

開啟 <http://127.0.0.1:3300>；同源 Swagger 在 <http://127.0.0.1:3300/api/v1/docs>。

`make dev` 啟動 Compose DB、執行 migration 和明確 fixture seed，再啟動 API/Web。DB 綁定 `127.0.0.1:55433`，使用 `yudada-next-postgres` volume 保留資料；本機範例 DB 使用 trust authentication。健康檢查執行目標 database 的 `SELECT 1`。API/Web 使用 8300/3300，可用 `DEV_DB_PORT`／`DEV_API_PORT`／`DEV_WEB_PORT` 改 ports，無需停用其他專案。Ctrl-C 停止 API/Web；`make db-stop` 停止 DB、保留 volume。seed 只更新固定範例應用，不清空其他資料。

帳號入口 `/account`，我的應用與题目／規則編輯 `/studio`，公開探索從首頁卡片進入，作答紀錄 `/history`。API 的 `PUBLIC_ORIGIN` 必須與 Web origin 完整一致；runner 自動帶入本次 port。正式 `APP_ENV=production` 必須搭配 HTTPS origin，session cookie 為 HttpOnly/SameSite=Lax，HTTPS 自動 Secure。私有 mutation 使用 `X-CSRF-Token`，由登入或 `/api/v1/auth/me` 取得；不存 session token 於 localStorage。

發布內容與答案 pin immutable version；改名fixture會建立新核准版本並切pointer，舊答案仍可回放。draft不公開；先儲存再送審，管理者在 `/admin` 核准後切換新版，待審與退回不影響舊核准版。下架／軟刪除停止新作答；`/studio?deleted=1` 恢復為未公開，須明確再發布核准版本。答題需 `Idempotency-Key`：同使用者／key／payload回原answer，改payload則409。規則分數與測評結果由server計算；公開題目不包含評分屬性。隱藏紀錄保留資料。

圖片資料由 `UPLOAD_ROOT` 指向本機持久目錄或掛載的 volume；未指定時為 `$XDG_DATA_HOME/yudada-next/uploads`（預設 `~/.local/share/yudada-next/uploads`），不寫進 repo。PNG/JPEG/WebP 最大1MiB並驗內容與尺寸；每次上傳新ID，soft-delete不刪除歷史引用。備份時須同時保存DB與這個目錄；驗收使用自有TemporaryDirectory。

建立第一個 admin 時，在 API 目錄執行 `uv run --no-sync python -m scripts.create_admin`，並由環境提供本機 `DATABASE_URL`。命令互動輸入帳號、名稱與 password，既有帳號不會被自動升權；不預置帳密。

## 資料流與邊界

```text
SSR: browser → Next.js page → server-only client（轉送 Cookie）→ FastAPI → PostgreSQL
更新列表: browser → /api/v1/apps → Next.js rewrite → FastAPI → PostgreSQL
```

- `apps/api/app`：業務與資料 SSOT；async SQLAlchemy engine 由 lifespan 建立及釋放。
- `apps/api/migrations`：Alembic schema；seed 獨立於 migration。
- `apps/api/openapi.json` → `apps/web/src/lib/api/schema.d.ts`：生成型別；client 使用 `openapi-fetch`，不手寫第二份 DTO。
- `apps/web/src/lib/api/server.ts`：server-only SSR adapter；Cookie 只在 HTTP header，不進 URL 或頁面。
- `next.config.ts` 的 `API_ORIGIN` 是 server 設定；production rewrite 在 build 時固定，變更 origin 須重建。browser 不需要 `NEXT_PUBLIC_API_*` 或 CORS。
- `tests/transport_service.py`：隔離的 HTTP 測試 backend；產品 API 不掛載 probe。

版本由 `pnpm-lock.yaml`、`apps/api/uv.lock` 固定。pnpm 11 的 `allowBuilds` 只允許列出的 native build scripts；Next.js 16 的 build 不包含 lint，因此 gate 個別跑 lint/typecheck。

## 驗收

命令循序執行；runner 用 checkout lock 避免 build 與不同 API origin 相互覆寫。

| 命令 | 實際工作 |
|---|---|
| `make check` | API Ruff／mypy／unit；OpenAPI snapshot 與 generated client drift；Web ESLint／TypeScript／Vitest／production build |
| `make test-integration` | 臨時真 PostgreSQL；migration drift/roundtrip；HTTP auth／owner／versions／answers／publication／admin／uploads／pagination；owner、最新版草稿、未核准可見性、移除冪等unique、私有圖片與停用登入race的隔離mutations |
| `make test-e2e` | 真 DB/API + production Next.js + Chromium；同源 docs/schema、SSR、browser refresh、桌面/手機；fixture 改名及 API 停止必須使相同 UI assertion 失敗 |
| `make test-faults` | production Next.js + 隔離 HTTP backend；non-2xx/headers、Set-Cookie、同源 HTTP client/SSR Cookie、SSE 即時 flush、斷線釋放、read timeout；移除 `no-transform` 的 buffering mutation 必須失敗 |
| `make generate-client` | 從 FastAPI 重建 OpenAPI snapshot 與 TypeScript client types |

測試 DB image 須預先下載，runner 使用 `--pull=never`，臨時資料放 tmpfs；不連既有資料庫。每次結束清理本次 container/API/Web。證據、截圖與服務 log 在忽略的 `.artifacts/`；Playwright trace 在 `test-results/`。CI 使用相同四入口，安裝 Chromium 系統依賴後循序執行。

本機若 Docker 被其他工作暫停或回收，可用 `TEST_POSTGRES_BIN=/path/to/postgres/bin make test-integration`（E2E 同樣支援）。runner 以該目錄的 initdb/postgres/psql/createdb 建自己的臨時 cluster，localhost/random port，不連既有 DB；退出時停止自身程序並清除臨時資料。本機現有 PostgreSQL16.15 已驗證 migration與auth HTTP；CI Docker為17，兩者結果分開記錄。

目前 faults 驗證 HTTP transport，不代表已驗 AI provider、評分 claim 或雙 API process 協調；這些測試在步驟 5 增加。GitHub Actions 尚需 repo 發布後才有遠端 run 證據。

## 功能來源

- [重做計畫](docs/plans/2026-10-01-full-rebuild.md)
- [功能盤點](docs/plans/2026-10-01-full-rebuild/inventory.md)
- [逐列來源盤點](docs/plans/2026-10-01-full-rebuild/source-inventory.md)
- [產品與 API 契約](docs/plans/2026-10-01-full-rebuild/contracts.md)
- [參考專案](https://github.com/liyupi/yudada)

原專案 source 僅供本機閱讀，忽略於 Git；新程式獨立撰寫。複用程式、素材或題庫前須核對授權。
