# 功能盤點與需求附件

核對日期：2026-10-01。已固定 commit `e5eb265817f13481a543c8a5da4e409d716363e7`，下載經授權的 183 個 source 檔並逐一驗 Git blob hash。排除 configs、credential payload、seed data、tests與 build manifests，故不宣稱執行原系統或核對部署設定。核心 REST/schema/Web consumers 已形成 [逐列盤點](source-inventory.md) 與 `source-inventory.json`。

## 需求來源

- S1：Will 要完整重做，改 Next.js + FastAPI；接受 Web 使用者端與管理端、小程序延後、分階段學習實作。
- S2：Will 確認無舊部署／資料、名稱 yudada-next、放個人 projects、建立專案頁、暫不掛季度目標。
- S3：Will 確認本地帳號＋密碼＋Cookie session，以及不可變發布版本、修改後重新審核、舊答案對應舊版本。
- S4：[README](https://github.com/liyupi/yudada/blob/master/README.md)。
- S5：[controller 清單](https://github.com/liyupi/yudada/tree/master/yudada-backend/src/main/java/com/yupi/yudada/controller)。
- S6：[scoring 清單](https://github.com/liyupi/yudada/tree/master/yudada-backend/src/main/java/com/yupi/yudada/scoring)。
- S7：[AI 評分](https://github.com/liyupi/yudada/blob/master/yudada-backend/src/main/java/com/yupi/yudada/scoring/AiTestScoringStrategy.java)。
- S8：[出題與 SSE](https://github.com/liyupi/yudada/blob/master/yudada-backend/src/main/java/com/yupi/yudada/controller/QuestionController.java)。

## 初步功能去向

本表是業務群組，不是完整 endpoint 計數；所有保留行為於步驟 0 核對後填入契約。

| ID | 畫面／流程與資料 | 來源 | 去向 | 步驟 |
|---|---|---|---|---|
| R01 | 註冊／登入／登出／profile，User | S4/S5 | 保留流程，改 Cookie session | 2 |
| R02 | 建立／編輯／我的應用，App | S4/S5 | 重寫 owner 權限與草稿 | 2 |
| R03 | 題目／選項編輯，Question | S4/S8 | 保留動態編輯，重寫驗證 | 3 |
| R04 | 得分／測評規則，ScoringResult | S4/S6 | 保留兩種自訂評分策略 | 3 |
| R05 | 答題／結果／歷史，UserAnswer | S4/S5 | 重寫版本引用與冪等 | 3 |
| R06 | 送審／審核／下架／搜尋／詳情 | S4/S5 | 保留業務，發布版本不可變 | 4 |
| R07 | 分享 URL 與 QR code | S4 | 保留 Web 分享 | 4 |
| R08 | 使用者／內容管理 | S4/S5 | 保留；刪除／停用語意待 0 核對 | 4 |
| R09 | AI 出題、預覽與确认 | S4/S8 | schema 驗證後逐題 SSE | 5a/5b |
| R10 | AI 測評 | S4/S7 | adapter、結構驗證與結果狀態 | 5a/5c |
| R11 | 應用／結果統計 | S4/S5、UserAnswerMapper.java:17–27 | 保留 top 10 回答數與某應用結果分布，API 加 admin guard | 6a |
| R12 | 上傳與封面 | S5 FileController、Web upload consumers 見 JSON | 本機 volume＋內容驗證；D4 已決 | 4 |
| R13 | 快取／冪等／資源隔離 | S4/S7/S8 | 重新設計 | 3/5/6b |
| R14 | MBTI 小程序 | S4 | 延後；Web 完成且 Will 要求跨端時啟動 | 延後 |
| R15 | Post／收藏／按讚模板 | S5、source-inventory.json | D7 已准省略；掃 44 個非生成 Web/mini source，沒有實際 UI reference，生成 client 本身不算 consumer | 0 |
| R16 | RxJava／Redisson／分庫分表／Snowflake | S4 | async＋DB claim／版本 key；分表合併、server UUID＋冪等 key，sharding 等量測需求 | 0/6b |

## 缺陷處置建議

| ID | 證據 | 新設計／失敗測試 | 狀態 |
|---|---|---|---|
| B1 | S8 括號計數與移除 whitespace | 真 JSON parser；quoted braces、escaped quotes、空白與 UTF-8 跨 chunk | D3 已准修正；5a/5b |
| B2 | S8 無限 timeout、error 僅 log、未保留取消 handle | timeout／終態／取消 upstream；HTTP partial 後中斷不可呈現成功 | D3 已准修正；5b |
| B3 | S7 本地 cache＋分散式鎖，持鎖後不重查 | 共享結果與 claim；兩 API process 同輸入不能同時評分 | D3 已准修正；5c |
| B4 | S7 key 僅 appId＋choices | 包含 owner／內容／策略／Prompt／model 版本；版本更新 cache miss | D3 已准修正；5c |
| B5 | S7 固定 15 秒 lease、搶不到鎖回 null | pending／failed／恢復；慢於 lease 仍無空結果假成功 | D3 已准修正；5c |
| B6 | CustomTestScoringStrategy.java:61–83 每題遍歷全部 answers | 逐題對位；contracts.md 的兩題 I/E fixture 在舊算法選錯結果 | D7 已准修正；3 |
| B7 | CustomScoreScoringStrategy.java:63–76 invalid key 以 0 分、未命中範圍仍取第一最高結果 | 非法選項 422、發布時驗最低門檻覆蓋理論最小分；反例 fixtures 見 contracts | D7 已准修正；3 |
| B8 | AppStatisticController.java:48–62 沒有 API admin guard | 新統計 API 驗 admin；user/guest 403/401 fixture | 新實作驗權不變量；6a |

## 非功能需求與外部介面

- 使用者：Will，目標是完整重做與學習；未驗證商業需求，市場驗證不作學習專案前置條件，商業化另立需求。
- 安全：API 驗權、owner 私有結果、未核准不可公開、密碼／session 不進 DTO/log/browser bundle；安全參數依 OWASP，於步驟 0 附來源。
- 安全預設（可推翻）：Argon2id 至少 19 MiB／iterations 2／parallelism 1，隨 library 管理 salt；session 採不可猜測 opaque ID、HttpOnly/Secure/SameSite Cookie、登入輪替與登出 server-side 撤銷；CSRF 防禦不只依賴 SameSite。2026-10-01 核讀 [Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)、[Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)、[CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)。0 補 timeout 與具體 token 儲存契約。
- 一致性：伺服器評分、答案版本可回溯、同一提交 key 的 DB 唯一性。
- AI：真 provider、費用與延遲門檻未決。fake provider 通過不能證明真模型品質或成本。
- 可觀測性：request/generation ID、duration、status/error class，避免敏感 payload。
- 效能與可用性：併發、p95、RPO/RTO 待部署與 spike 量測，不捏造 production SLO。
- 保存：無舊資料；使用者刪除、應用下架與結果保留語意於 0 定案。
- 外部系統：真模型 API、圖片儲存、hosting 未指定；未批准前不登入、使用憑證或建立付費資源。
- [Next.js Server/Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)、[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)：2026-10-01 Web 核讀，只證明可參考的框架邊界，不證明專案已執行。

## 可重跑盤點與限制

Will 已授權本次 source 下載。附件不是 Git checkout，採 GitHub commit/tree metadata＋Git blob hash；不使用原 `.git` 或讀取設定。真正執行命令：

```sh
python3 /Users/will/second-brain/.projects/personal/yudada-next/docs/plans/2026-10-01-full-rebuild/audit-source.py
python3 /Users/will/second-brain/.projects/personal/yudada-next/docs/plans/2026-10-01-full-rebuild/check-inventory.py --mutation
```

結果：64 REST／10 controllers、7 SQL tables、20 Web route declarations；含 layout 和 `/hide` alias，不誤稱 20 獨立功能頁。8 個 Java entities 中另有 Post/PostFavour/PostThumb，tracked create_table.sql 沒有其 CREATE TABLE；省略原因為已決產品 scope，不用 schema 不全推論無使用者。

source-tree.json 的完整未截斷 path 清單未找到 LICENSE/COPYING 檔；這不能證明可自由複用。下載原碼只作本機閱讀、置於 .gitignore；新實作獨立撰寫。原 Java/Vue baseline 未跑，無依賴下載授權，不能把靜態盤點當 runtime 通過。

Post consumer 負面查詢由 audit-source.py 搜所有非生成 Web source 的 API symbol references；另外以 `postController|postFavourController|postThumbController|/post(?:[/_]|\b)|doPost|listPost|favourPost|thumbPost` 掃 44 個 Web/mini source，結果 0。Generated `api/index.ts` 的匯出保留在證據，不計作 UI 呼叫。
