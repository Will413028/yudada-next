# yudada-next：完整 Web 重做計畫

**Goal：** 完成建立、審核、分享、答題、結果與管理統計；規則／AI 評分可追溯，AI 出題逐題呈現且能正確取消。功能完整性以固定來源盤點及驗收矩陣證明。

**上層：** 暫代主計畫。本檔為 repo 執行進度 SSOT。

**附件：** [需求與盤點摘要](2026-10-01-full-rebuild/inventory.md)、[逐列來源盤點](2026-10-01-full-rebuild/source-inventory.md)、[新契約](2026-10-01-full-rebuild/contracts.md)。步驟 0 已完成靜態盤點、契約決定與兩輪獨立審查，接續 1 建立可執行產品基線。

## 全域約束與完成定義

Will 最新指示：目標為完成全部功能，途中不再逐項要求權限；本次連續執行剩餘步驟，不以 phase-plan 的 session 步驟邊界停止。既有設計需求保持；重要知識與決策以 recording/design-review 留存。完成宣稱須逐項核對全部 scope，不能以骨架或單一階段代替完整產品。

- 已確認 Next.js/FastAPI、完整 Web 使用者端／管理端、小程序延後、分階段學習、全新資料、本地帳號密碼與 Cookie session、不可變發布版本。
- 依 Will 最新指示，必要本機實作、依賴與驗收直接推進，不逐項要求權限；保留完整產品scope。沒有付費額度或真模型證據時不得虛構，實際上線仍依D6範圍。
- 每步交付可驗收切片，附資料流、取捨與反例，並連續推進剩餘步驟；不以session步驟邊界停止。過大步驟拆成有驗收的子步驟。
- 不逐個翻譯 Java 套件；複用程式、素材或題庫前核對 license。
- 完成定義：全部盤點有去向；每個保留功能有 UI/API/integration 證據；權限、版本、冪等、AI 錯誤／取消測試通過；OpenAPI client 無 drift；獨立 design/code review finding 全處置；真模型與部署未驗證時分別標示。

## 前提（2026-10-01）

- 會改到或取代的既有部署是否在線：無既有部署，Will 已確認；無舊資料搬移或相容窗口。
- 範圍、學習方式、身份、repo 名稱、登入與版本由本次對話確認；暫不掛季度目標。
- 已固定來源 revision `e5eb265817f13481a543c8a5da4e409d716363e7`，183 個經核對 Git blob hash 的 source 檔；64 REST／7 SQL tables／20 Web route declarations。configs/seed/tests/manifests 排除，原程式未執行；来源與命令見附件。
- 工具鏈預設（可推翻）：monorepo `apps/web`、`apps/api`，TypeScript/App Router、Python/SQLAlchemy/Alembic/PostgreSQL、pnpm/uv/pytest/Playwright。1 查官方相容性後固定版本／lockfiles。
- 邊界建議：FastAPI 唯一業務／權限 SSOT，Next.js 呈現；同源 `/api` 與 SSR cookie forwarding 於 1 spike 實測。

**驗收基線：** 原系統固定上述 revision，未執行（依賴／設定未納入授權），只作靜態行為盤點。新 repo 初始只有文件；步驟 1 建立 Git、build/test 與產品基線，證據記進度表。source 盤點与 mutation gates 已通過。

## 不變量

| 不變量 | 預計依賴模組；實作後補路徑 |
|---|---|
| API 驗證權限與公開可見性 | auth/apps/admin/questions/answers/ai/statistics/uploads |
| 舊答案引用其發布版本與評分規則 | publication/answers/scoring/cache |
| 同一提交 key 只建立一次答案 | DB unique constraint/answers API/UI retry |
| 模型輸出驗證後才能保存／發布 | adapter/generation/scoring/SSE UI |
| error／cancel 不可呈現成功 | upstream transport/status/terminal event/result persistence |
| 憑證不進 log/browser bundle，私有答案不進跨 owner 可重用 cache | auth/SSR/observability/scoring cache；D3 明定可共享評分產物與私有答案邊界 |

## 範圍

- 做：附件 R01–R13 的 Web 流程，依 0 盤點補齊。
- 不做：Java 套件相容；R16 實作機制以需求與量測決定。
- 延後：小程序（Web 完成且 Will 要求跨端）；商業化（另授權需求）；實際上線待 D6，不阻擋本機驗收。
- 已准省略 R15 模板 Post/social、公開 SSE test、/hide alias 與答案修改；consumer 查詢在附件。D8 舊核准版本持續公開、D9 可恢復刪除已決，具體狀態與回放見契約。

## 驗收入口與消費端

以下入口已在 1 實作；實際執行結果以進度表為準，環境與目前 coverage 見 README。

- `make check`：API lint/type/unit、Web lint/type/build/unit、OpenAPI client generation diff。
- `make test-integration`：實際 PostgreSQL、migration、HTTP API，不以 SQLite 代替交易語意。
- `make test-e2e`：Playwright 經真 Web/API/DB；1 驗 fixture SSR/更新與反例，後續步驟逐步加入使用者與管理流程。
- `make test-faults`：1 已建立真 HTTP transport 的 non-2xx/cookie/SSE flush/cancel/read timeout 與 buffering mutation；5a–5c 再接 fake AI provider／兩個 API process 協調，不能將 transport 當 AI 證據。

目前 consumer：`apps/web/src/app/page.tsx` → server-only `listAppsForRequest` → typed `listApps`；`refresh-apps.tsx` → 同源 rewrite → API；`Makefile`／CI → `scripts/verify.py` → migrations、HTTP tests、Playwright。以下命令在 repo 根目錄可重跑，含尚未 commit 的 scaffold，排除 ignored source／依賴：

```bash
YUDADA_REPO="$(git rev-parse --show-toplevel)"
git -C "$YUDADA_REPO" ls-files --cached --others --exclude-standard
rg -n 'listApps|API_ORIGIN|/api/v1/apps|verify.py' "$YUDADA_REPO/apps" "$YUDADA_REPO/tests" "$YUDADA_REPO/scripts" "$YUDADA_REPO/Makefile" "$YUDADA_REPO/.github"
```

## 步驟

- [x] **0. 固定來源与行為規格**（被擋於：無；靜態盤點完成，原 runtime 未驗證的限制保留）
  - 範圍：完整 REST/schema/Web/策略/upload/admin/SSE 盤點；補去向与測試；依已決 auth/version 寫資料、API 与事件契約。查 license、D3/D4 与刪除／停用語意。D3 必須定義可重用評分產物與私有答案各自的 key、資料欄位與權限，未批准前不可跨 owner 重用。
  - 消費端：附件原來源搜尋；新 repo 無 scaffold。不能動：原來源與 credentials。
  - 驗收：`audit-source.py` 验全部 blob／產生清單；`check-inventory.py --mutation` 檢驗去向与需求映射，去向／coverage mutation 都拒絕。契約決定與 review ledger 全處置。原程式未跑的限制必須留下。
  - 停止條件：SSOT 衝突、來源不可固定、授權限制複用。原程式跑不了須記錄原因，不聲稱原 baseline 通過。

- [x] **1. Walking skeleton**（完成；驗收證據見進度表）
  - 範圍：初始化獨立 Git、Web/API/DB/遷移、CI、OpenAPI client、四個入口；fixture 應用「DB → API → Web 顯示名稱」。固定相容版本。
  - 消費端：page/server fetch/HTTP client/CI/E2E。不能動：業務與權限集中 API。
  - 驗收：check/integration/E2E、乾淨 DB migration；停止 API 或改 fixture 名稱使 E2E 失敗；同源 spike 實測 non-2xx、cookie forwarding 與 SSE flush。
  - 停止條件：工具或 routing 不支援必要能力，附證據提替代案。

- [x] **2. 身分與應用建立**（完成；含真DB、owner mutation、production Chromium）
  - 範圍：register/login/logout/profile、草稿建立／編輯／我的應用、admin role 的受控建立。
  - 消費端關鍵字：`session|login|owner|role`，含 SSR cookie、UI、API。不能動：不依賴 UI 驗權；密碼/session 不進 DTO/localStorage/log。
  - 驗收：check/integration/E2E；匿名拒絕、owner 成功、他人拒絕、logout 失效、CSRF／Origin；移除 owner/admin guard 時測試失敗。
  - 停止條件：需要未授權外部身份／憑證。

- [x] **3. 手動答題完整閉環**（check、HTTP8、四項owner/version mutations、Chromium6與fixture/API-stopped反例通過）
  - 範圍：題目／選項／得分與測評規則、答題結果／歷史、不可變發布版本模型、提交冪等 DB unique constraint。正式發布流程在 4；本步用測試 seed 建立帶核准狀態的固定版本供答題，不能讓草稿公開可答。
  - 消費端關鍵字：`question|choice|score|answer|version`。不能動：server score、私有結果、版本可追溯。
  - 驗收：check/integration/E2E；invalid choices、fixture 分數／分類、草稿公開答題拒絕、同 key同 payload 同結果、不同 payload 409、雙連線只一筆、草稿修改不改核准 fixture 的舊結果；移除 unique constraint／改用最新題目評舊答案／允許草稿公開答題使測試失敗。seed 只用於本機測試，不提供公開核准捷徑。
  - 停止條件：原評分規則歧義未解。

- [x] **4. 發布、探索、管理、上傳與分享**（被擋於：3；D4；0 的刪除／停用契約）
  - 範圍：送審／核准／退回／下架、公開搜尋／詳情、QR、封面、使用者／內容管理。
  - 消費端關鍵字：`published|review|visibility|upload|admin`，含 metadata。不能動：未審核修改不能由原分享 URL 洩漏。
  - 驗收：check/integration/E2E；建立→審核→分享→答題；未核准／下架在列表和直接 URL 都不可讀；upload owner/type/size；移除 visibility/upload guard 使測試失敗。
  - 停止條件：storage 或刪除語意未決。

- [ ] **5a. AI adapter 與契約 spike**（被擋於：4；D3；真候選 provider spike 另需有限預算及憑證使用授權，未依賴正式 D5）
  - 範圍：fake HTTP provider、async adapter、JSON/schema、generation 狀態；真品質／成本 spike 另回報。
  - 消費端關鍵字：`generation|provider|event|result`。不能動：fake 不作真模型證據、EOF 不自動成功。
  - 驗收：check/integration/faults；不合法 JSON、quoted braces/quotes/space/UTF-8 chunk、HTTP partial 中斷；切回括號計數／移除 schema 使測試失敗。真 spike 先交候選 provider、最大請求數與費用額度給 Will 批准，再產出固定樣本集、schema 正確率、評分品質、費用、延遲与取消量測。報告供 D5 選正式 provider 與批准通過門檻，不宣稱品質已合格。
  - 停止條件：provider 能力不足不得静默降級。

- [ ] **5b. AI 出題與逐題 SSE**（被擋於：5a fake 路徑；D3）
  - 範圍：POST generation stream、question/completed/error 事件、deadline、cancel、preview 確認才保存；斷線不自動重跑。
  - 消費端關鍵字：`question|completed|error|AbortController`，含 editor、browser parser、API streaming。不能動：完整 schema 驗證、生成不自動發布。
  - 驗收：四入口；任意 chunk/multi-event/heartbeat/non-2xx、取消關閉真 upstream connection、timeout 終態；移除 cancel/buffer 或 error 改 complete 時失敗。
  - 停止條件：真 routing 緩衝／取消不能驗證。

- [ ] **5c. AI 評分與恢復**（被擋於：5a fake 路徑；D3）
  - 範圍：pending/succeeded/failed、共享結果与 claim、版本 cache key、逾時恢复。先資料庫協調，Redis 依量測需要。
  - 消費端關鍵字：`pending|succeeded|failed|cache|claim`，含結果頁与統計。不能動：失敗不 cache 成功、不承諾 provider 不支援的外部 exactly-once 費用。
  - 驗收：四入口；兩 process 同輸入、慢於 15 秒、owner crash、retry、版本 cache miss、無空結果假成功；兩 owner 相同輸入各有獨立答案 identity/owner，不能讀對方私有答案；共享產物只含 D3 允許欄位。移除 claim/version key 或把他人私有答案作 cache response 時失敗。
  - 停止條件：外部 replay/idempotency 不能支援既定保證，回 D3/D5 修訂。

- [ ] **6a. 統計與功能對帳**（被擋於：4；5b/5c fake 路徑）
  - 範圍：原核心指標、管理 dashboard、補齊盤點未完成功能。
  - 消費端關鍵字：`statistic|aggregate|result`。不能動：pending/failed 不混入完成答案、不放寬聚合權限。
  - 驗收：check/integration/E2E；fixture 指標、paging/filter、多角色；納入 failed／跨 owner 資料使測試失敗。
  - 停止條件：盤點仍有無去向項目。

- [ ] **6b. 可靠性與量測**（被擋於：6a；D3；真 model 負載另擋費用授權）
  - 範圍：限流、bounded concurrency、indexes/query plans、observability、故障與負載報告；依需求決定 Redis／worker。
  - 消費端關鍵字：`limit|timeout|query|trace|generation`。不能動：敏感 log、未量測就加 sharding/VIP pools。
  - 驗收：四入口；fake provider admission/resource bounds/crash/restart、權限隔離；移除 admission guard 時失敗；p95／吞吐附條件，未定門檻只報量測。
  - 停止條件：需求與成本門檻未定，不宣稱 production capacity 通過。

- [ ] **6c. 部署與真模型驗收**（被擋於：6b；D5/D6；外部登入／secrets／費用授權）
  - 範圍：hosting/TLS/routing、backup/restore、migration rollout/rollback、真模型品質。
  - 消費端關鍵字：`deploy|proxy|migration|provider`。不能動：其他專案部署或未授權帳號。
  - 驗收：實際 URL 全流程、SSE flush/cancel、restore、部署回滾；真模型以 D5 批准的固定樣本、schema／品質／費用／延遲門檻判定，缺門檻或未達標只報量測、不得宣稱通過。buffering proxy mutation 使串流 smoke 失敗。
  - 停止條件：部署未准；本機完成可獨立驗收，上線仍標未完成。

- [ ] **7. 收尾**（被擋於：0–6b；宣稱上線另需 6c）
  - 完成定義逐項核對、獨立 design/code review、指令檔對帳、長期 gates 接 CI、延後項附條件回主清單。
  - 驗收：四入口、盤點 script、final diff、finding ledger；全部命令与文件對得上現況。部署与真 AI 分別列未驗證限制。

## 決定

| 題目 | 業界選項與取捨 | 結論／建議 | 狀態與相依 |
|---|---|---|---|
| D1 登入 | 本地 session：完整學 auth、負責安全；OIDC：少管密碼、外部設定 | 本地帳號密碼＋Cookie session | 已決 2026-10-01 Will；2 |
| D2 題目變更 | 發布版本：可追溯、模型較多；直接改＋快照：簡單、審核複雜 | 不可變發布版本，修改重新審核 | 已決 2026-10-01 Will；3–5 |
| D3 AI 執行／契約 | request async＋DB claim：元件少需上限；durable queue：恢復強、更多 infra；同步：簡單但慢 | 出題 request-scoped、評分持久化 claim、完整題目與 error/complete；第一版 cache 限同 owner/version/input | 已決 2026-10-01 Will；5–6b |
| D4 storage | volume：本機容易、單機保存；S3-compatible：跨 instance、帳號費用 | 本機 volume＋實際圖片驗證；上線另選 | 已決 2026-10-01 Will；4 |
| D5 真 AI | 單 provider：品質成本易驗；多 provider：彈性、測試多 | 建議一個 provider＋fake adapter；須同時核准固定評估樣本、品質方法、schema/品質/費用/延遲通過門檻 | 未決；5a 有限額候選 spike 後，擋正式真 AI 驗收，不擋候選 spike |
| D6 hosting | 單 VM：同源串流直接、需維運；託管：少維運、需驗 timeout/cookies/費用 | 先本機，依量測選上線 | 未決；6c |
| D7 原行為取捨 | 所有 template API 全移植：忠於接口但多無 UI 業務；完整答題產品＋修缺陷：聚焦真功能，接口不相容 | 省略 template/social/public test/隱藏示範；答案不可編輯，逐題對位、非法選項拒絕、固定規則順序平手 | 已決 2026-10-01 Will；0/3/4 |
| D8 新版送審可見性 | 保留已核准版本：持續可用、雙版本狀態；立即隱藏：簡單但送審期間不可用 | 保留已核准版本，新版核准後切換 | 已決 2026-10-01 Will；4 |
| D9 刪除與停用 | 可恢復：保留歷史、需管理狀態；永久刪除：更少留存、需恢復／稽核／擦除設計 | 下架/soft-delete、停用撤session、答案隱藏，永久刪除另立流程 | 已決 2026-10-01 Will；4 |

D1/D2/D3/D4/D7/D8/D9 已確認，已記錄於專案架構 ADR，持久知識入口見本機個人脈絡檔。D5/D6 有 spike/成本資料才拍板。未回覆不能自動採建議。

## 進度

| 步驟 | 狀態 | 已跑驗收 | 未跑與原因 | commit |
|---|---|---|---|---|
| 計畫準備 | 完成 | 目標碰撞檢查、來源 Web 核讀、D1/D2、獨立 review 4 項修正、文件/link gates | 無產品 build/test，尚無 scaffold | 無 |
| 0 | 完成 | 固定 commit、183 blob hash、64 REST/7 tables/20 routes、R01–R16 映射、五項 mutation、两輪 review 全處置、D8/D9 | 原 runtime 未跑；原依賴／設定不在授權範圍 | 無 |
| 1 | 完成 | 四入口通過；最新 check、production Chromium DB 改名／還原、fixture-name/API-stopped mutations、migration roundtrip/drift；transport 4 tests 與 buffering mutation；dev 啟動與 shutdown；設計兩輪 0 findings，C1/C2/U1/U2 修正並複核 | 遠端 CI 未發布；本步不驗 auth、正式 AI/provider 或部署 | 無 |
| 2 | 完成 | 完整check；nativePG16.15 migration/drift/HTTP5 tests；owner mutation；production Chromium3 tests及fixture/API-stopped mutations；admin安全unit；design/code reviews；後續3的Docker17 HTTP涵蓋本步schema | CI未發布；B1已於3移除 | 無 |
| 3 | 完成 | check；規則6unit（全API9）；Docker17與native16.15 migration/drift/HTTP8；native owner/latest-draft/pending-version/missing-unique mutations；production Chromium6與fixture/API-stopped反例；design review0、code P1/P2修正及runtime複核 | CI未發布；正式publication/admin/AI在後續步驟 | 無 |
| 4 | 完成 | 既定 publication/delete/upload 契約仍成立；無新架構選擇 | check；nativePG16.15 migration0004/drift/roundtrip、HTTP13及6項owner/version/upload/session反例；Chromium8＋2項故障反例；transport4＋buffering mutation均通過 | design無finding；correctness四項closed |
| 5–7 | 未開始 | 無 | 依相依順序；完整scope不縮減 | 無 |

## 計畫審查處置

- F1（高）D5/spike 循環：已修，5a 的有限額候選實驗先單獨授權，D5 消費量測後批准正式 provider 與門檻。
- F2（中）步驟 3 無合法發布版本：已修，3 建版本模型與核准 fixture；4 接正式審核，草稿公開答題拒絕。
- F3（中）共享 cache 與私有答案邊界：已修，0 的 D3 明定欄位／key／權限，5c 增兩 owner 與錯誤重用 mutation。
- F4（中）真 AI 無品質判準：已修，D5 產出可判定門檻；6c 未核准／未達標只報量測。
- F5（中）盤點 gate 只驗 REST 數量：已修，與 source REST 身分、SQL table、Web route declaration 的實際集合比對；五項 mutation 全拒絕。
- 獨立 ADR 草稿補強：OIDC 身份來源與 session 分開比較、DB claim 的自建 scheduler 成本、referenced image 不可覆寫／刪除、shutdown 和同 owner 不同答案 key 的共享工作均補入契約。此為既有不可變／協調要求的落實，未增加产品功能。
- Skeleton review：C1 將 Swagger/schema 移至同源 `/api/v1`；C2 先驗 fixture UI 再驗 docs，保留 API-stopped mutation 的辨識。U1 加 `router.refresh()` 與 DB 改名／還原卡片 regression；U2 改本機 ports 3300/8300/55433 並支援 overrides。最新複核無新 findings。
