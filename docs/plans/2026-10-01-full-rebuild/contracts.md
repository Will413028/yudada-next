# 產品、資料與介面契約草稿

來源 revision `e5eb265817f13481a543c8a5da4e409d716363e7`，2026-10-01 核對。D1/D2/D3/D4/D7/D8/D9 已由 Will 確認。下列路由是重做契約，不承諾 Java endpoint 或 DTO 相容。具體 OpenAPI schema 由步驟 1/2 落地，不能手寫第二份 TS 資料模型。

## 角色與權限

- guest：公開應用清單、已發布詳情與題目；作答需登入，規則與私有答案不公开。
- user：自己的 profile/apps/draft/answers/uploads；已發布應用答題。所有 owner guard 在 API。
- admin：使用者、應用、題目、規則、答案管理與統計、版本審核；管理答案只讀／隱藏，不竄改既有評分。修改題目／規則一律產生新版本。
- 不公開 raw user entity、password_hash、session token 或 admin-only 欄位；傳輸使用受控 DTO。

## 資料模型

| 預計模型 | 欄位／不變量 | 舊資料去向 |
|---|---|---|
| users | UUID、unique account、password_hash、display_name/avatar、role、active、created_at | user；不搬資料 |
| sessions | token_hash、user_id、expires_at、last_seen_at、revoked_at；cookie 原始 token 不存 plaintext | 取代 servlet session |
| apps | UUID、owner_id、active_version_id、deleted_at、created_at | app 身分與公開 pointer |
| app_drafts | app_id unique、revision、title/description/cover、type/strategy、題目與規則 document | app/question/scoring_result 的可編輯內容 |
| app_versions | app_id、version sequence、immutable content、content_hash、strategy_version；提交後不改內容 | 不可變題目／規則／應用 metadata |
| publication_reviews | version_id、pending/approved/rejected、reviewer/reason/reviewed_at | app review 欄位；與不可變內容分開 |
| answers | UUID、owner_id、app/version_id、choices、payload_hash、idempotency_key、ai_job_id、pending/succeeded/failed、result_snapshot、hidden_at；unique(owner_id,key) | user_answer 與兩張分表合併 |
| ai_jobs | UUID、owner_id、input_hash、provider/model/prompt/schema versions、claim owner/fence/lease、attempt/status/error、deadline、result artifact；partial unique(owner_id,input_hash) where pending/running；結果只服務同一 owner | 同 owner/input 可共享工作，答案 identity 不共享 |
| uploads | UUID、owner、business purpose、content type/hash/size、storage path、deleted_at | file endpoint；不接原 COS |

UUID 為 Python 標準 UUID4 預設；沒有舊 ID 相容性、分散式 Snowflake 或 DB sharding 要求。JSON document 保留題目／選項嵌套；Pydantic 驗形與版本內容 hash。查詢、答案及 owner 用 relational keys，不把整個平台塞單一 JSON。

Draft 更新需 expected revision，並行更新衝突 409。送審時 transaction 複製到不可變 version＋pending review；publish atomically 更新 pointer。重複／舊版本審核不能使 active pointer 倒退，對不合法 state transition 回 409。D8：舊核准版本持續公開，新版核准後切換，退回不改 active pointer；原公開 URL 不洩漏未核准內容。D9 的 read/restore 規則見下方。

## REST 契約與 UI consumers

統一 `/api/v1`。每個 JSON error 包含穩定 `code`、可讀 message、request_id；HTTP 401 未登入、403 無角色、404 不可公開／不存在、409 衝突、422 schema/choices、429 超額、503 provider unavailable。不用 HTTP 200 裝失敗。

| 功能 | 預計 endpoint | consumers／步驟 |
|---|---|---|
| 註冊登入與 session | POST auth/register, auth/login, auth/logout；GET auth/me | login/register/SSR/navbar；2 |
| 個人資料 | GET/PATCH me | profile/editor/avatar；2 |
| 公開探索 | GET apps；GET apps/{id}；GET versions/{id}/questions | home/search/detail/answer/share；3/4 |
| 我的應用與草稿 | GET me/apps；POST apps；GET/PATCH apps/{id}/draft | owner list/create/question/rule editor；2/3 |
| 發布與下架 | POST apps/{id}/submissions；POST apps/{id}/unpublish；DELETE apps/{id} | owner/editor/admin；4 |
| 審核 | GET admin/reviews；POST admin/reviews/{id}/approve 或 reject | admin app board；4 |
| 使用者管理 | GET/POST admin/users；GET/PATCH admin/users/{id} | admin user board；4 |
| 內容管理 | GET admin/apps, admin/questions, admin/scoring-rules, admin/answers | 五種管理頁，修改 draft 走同一 domain service；4 |
| 答題 | POST versions/{id}/answers，必須 Idempotency-Key | do-answer；3/5c |
| 結果歷史 | GET answers/{id}；GET me/answers；DELETE answers/{id} | result/history/管理讀取；3/4 |
| AI 評分重試 | POST answers/{id}/retry，只允許 failed＋owner，答案不改 | result retry；5c |
| AI 出題 | POST apps/{id}/question-generations，JSON 請求／SSE 回應 | editor AI drawer；5b |
| 圖片 | POST uploads；GET uploads/{id} | avatar/cover/result image；4 |
| 統計 | GET admin/statistics/top-apps；GET admin/statistics/apps/{id}/results | charts；6a |

所有 lists 預設 page_size 20、最多 100、穩定 sort＋ID tiebreaker；搜尋 title/description，使用參數化查詢。所有 public fetch 的 DTO/cache key 與 private/admin 分離；metadata 取發布版本，不能取草稿。Swagger 與 health 使用 `/api/v1` 內明確路徑，Next.js routing 不攔截。

## 登入安全預設

採 Argon2id（最低 OWASP 設定見 inventory），server-side opaque session、至少 256-bit 隨機 token，資料庫只存 hash；HttpOnly/SameSite=Lax，正式 HTTPS Secure＋host-only cookie，Path=/。本機 HTTP 可關 Secure，正式啟動缺 HTTPS 設定不得默默降級。

idle timeout 預設 30 分鐘、absolute 24 小時（可調整，並非宣稱 OWASP 唯一數字）；login/role change 輪替，logout/停用撤銷。mutation endpoints 驗 Origin 並使用綁 session 的 CSRF token；不把 SameSite 當唯一防線。login 節流並用一致錯誤避免 account enumeration。admin 初次建立用本機明確命令，不預埋通用密碼；命令在步驟 2 實作後才加入 README。

SSR 將 incoming cookie 安全地轉送給內部 API，不把它放 query 或 browser JS；server-side private fetch 不進共用 cache。credentials 實際配置另需授權，文件不包含值。

## 規則評分與版本

- 第一版組合：得分類＋自訂、測評類＋自訂、測評類＋AI。原 scoring 沒有得分類＋AI，編輯器／API 禁止此組合；未授權擴充。
- 以題目 ordinal 對位 choices，長度必須一致、選項 key 必須存在且同題 unique；題目／規則不能空。score/result 屬性只供 owner/admin 編輯與 server score，公開題目不帶分數。
- 得分：加總各題所選 option score，依 threshold 降序取滿足的最大下界；發布時驗证最低門檻覆盖理論最低分，否則 422，避免原程式落到最高結果。
- 測評：只計算每題自己的選项 result property；每條結果取其 properties 計數總和，最高者勝；平手按 immutable rule order，規則按 UI 指定順序保存。
- 答案建立時 pin version/strategy，保存 result snapshot。舊答案不受後續版本、更名、圖片變更或規則移除影響；原結果內容可完整回放，沒有 answer edit endpoint。
- 冪等：key 唯一範圍 owner；同 key＋同 canonical payload 回原 answer，同 key＋不同 version/choices 回 409。DB unique constraint＋transaction 實現，先查不是保證。

## AI 出題與 SSE

API owner guard 在開始 provider request 前；question_count 預設 5、上限 20；每題 options 預設 4、上限 6。總 deadline 預設 90 秒，輸出／buffer 上限需 provider token settings 与 fixture 測試；超出回明確 error。

POST response Content-Type text/event-stream，Cache-Control 帶 no-cache, no-transform，避免 proxy gzip 緩衝小事件。用 Fetch ReadableStream（不是只有 GET 的 EventSource），parser 支援 CRLF/LF、跨 UTF-8 bytes、multi-line data、heartbeat；保留跨 chunk 狀態。步驟 1 transport spike 以收到第一事件才允許 backend 完成的 gate 驗 flush；移除 no-transform 的 mutation 必須失敗。

- `question`：generation_id、sequence、schema-valid question snapshot。只送完整題目；不能拿到 partial 就假装完成。
- `completed`：generation_id、question_count、usage（可取得時）；只有上游完成且全部驗證成功才送一次。
- `error`：generation_id、穩定 code、message、retryable；失敗終態一次，不再 completed。
- heartbeat：SSE comment，不当 question/event。連線在 completed/error 後結束。

取消在 client 使用 AbortController，API finalization 關閉 upstream HTTP stream／釋放 semaphore。server 可證明 upstream 已關閉，不能保證 provider 取消計費。斷線不自动重試；新生成由使用者明确點擊。preview 接受後以 draft expected revision 保存，已經在其他視窗更新時 409，不覆蓋。

## AI 評分、claim 與 cache

submit 儲存 pending answer/job 後回 202，UI 輪詢 owner result；規則評分可同步回 201。API lifespan 管理有上限的 in-process task，pending jobs 掃描與 claim 在 DB transaction；沒有外部 queue 第一版，程序啟動恢復持久化狀態。

claim 用 conditional update／row locking、lease＋fencing token；只有有效 fence 可寫 result。建立工作前 transaction 重查成功 cache，partial unique constraint 保證同 owner/input 只能有一個 pending/running job；不同 answer key 也 attach 同一 active job，不能各自重打模型。job 成功後將 artifact 複製為各 answer 的獨立 snapshot；已完成 snapshot 不再被後續 cache refresh 改動。

deadline 90 秒、lease 預設 30 秒、heartbeat 10 秒（實作時 fake slow/crash 驗證）；DB transaction 不跨外部 AI request。程序消失後過期的 running job 標 failed/interrupted，不能靜默重打付費模型；owner 可明確 retry，attempt 加一但同 answer identity。shutdown 停止新 claim，短暫 grace 後取消未完成 upstream；有效 fence 記 failed，無法寫回時交 lease 過期恢復，不留永遠 pending。

cache 僅同 owner＋version/content_hash＋canonical choices＋strategy/prompt/schema/provider/model version；成功產物才可重用，私有 answer identity 絕不共用。cache 用受權限保護 DB 結果，預設有效期 5 分鐘，以絕對 TTL 避免熱門 key 永不失效；Redis 延後至量測需要。兩 process 同 key 用共同 claim 協調，claim 後重查成功結果。

provider 不支援 idempotency 時，crash 在付費完成但 DB 未保存的窗口會產生費用不確定性，透過 failed 狀態與明確重試呈現；不宣稱 external exactly-once。品質、費用與 latency 通過門檻待 D5 spike 後批准。

## 上傳、統計與刪除

本機 volume，owner/用途路徑以 server ID 建立，不能信任原始 filename；不寫入 repo 或 public 可執行目錄。先支援 PNG/JPEG/WebP，最大 1 MiB，驗內容／尺寸上限／解碼，不僅看 extension；SVG 不進未清理的公開輸出。DTO 引用 upload ID，API 驗 owner 或已公開版本的使用關係，防任意 path traversal。

upload bytes 與 ID 不可變；更換圖片建立新 upload。只要任一保留的發布版本／答案 snapshot 仍引用 blob，不能物理刪除或覆寫；舊版本回放以受權限保護的原 blob 服務。soft-delete upload 只阻止新引用，不破壞既有回放；物理 garbage collection 必須證明沒有任何保留引用，第一版不實作 GC。

統計保留原 mapper 的熱門應用 top 10 與某應用結果分布，新增明確 admin API guard；只計 succeeded、未隱藏答案，穩定 tiebreaker。題目/評分變更採 version filter，預設 app 全部核准版本並可篩 version，結果以 snapshot resultName 分組。

D9 已核准：apps 軟刪除＋清 active pointer、停止新作答，owner 可看舊答案；帳號停用撤销全部 sessions，管理者可恢复；答案 DELETE 只隱藏，管理列表可明確指定 included_hidden。Restore 由 owner/admin 執行：應用先恢復為未公開，再由明確 publish 操作重設核准版本 pointer；帳號恢復不復活舊 sessions，需重新登入；答案取消 hidden_at 不改 choices/result。不宣稱隱藏是個資永久刪除；永久刪除若需要，另立明確流程與保留期限。

## 能區分原缺陷的 fixtures

- 測評：Q1 A=I/B=E、Q2 A=E/B=I，choices=[A,B]；E 規則在 I 前。正確 I=2/E=0→I，原 cross join 變 I=2/E=2→E，測試必紅。
- 得分：choices invalid key→422；最低 threshold 未覆蓋最小分→不能發布，不能默默取最高結果。
- auth：相同輸入的兩 owner 結果 identity 不共用；另一 owner GET answer→404，admin 只讀管理 API例外。
- immutable：version1 已核准；draft revision2 改分數，version1 答案重送仍原分數，新 key 對 version1也同分數。
- 圖片：version1 引用 image1，draft 替換 image2 並刪除 image1的新引用入口，舊答案回放仍可讀 image1；覆寫 bytes／刪除 referenced blob 的 mutation 必須失敗。
- SSE：真 HTTP fake provider 送 partial bytes 後中斷，API 不得 completed 或保存成功；全 event 在每個 byte split 測 browser parser。
- claim：兩 process 同 owner/輸入但不同 idempotency keys 仍只一個 active job，產生不同 answer IDs；owner process 終止、lease 過期後 failed，user retry 能恢复、舊 fence 回寫被拒。
