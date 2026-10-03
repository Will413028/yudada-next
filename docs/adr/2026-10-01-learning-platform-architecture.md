---
title: yudada-next — 學習型完整 Web 重做的架構選擇
date: 2026-10-01
status: active
tags: [personal, decision, nextjs, fastapi]
---

# 學習型完整 Web 重做的架構選擇

## Context

Will 要以 Next.js + FastAPI 完整重做答題 Web 產品並分階段學習；原 Java 專案作行為參考，不作技術限制。以下是 Will 於 2026-10-01 已確認的選擇，不代表產品已實作或部署。

- `external`：完整使用者端／管理端、私有答案隔離、可追溯版本與分階段學習，來源為本次需求。
- `external`：沒有舊部署或資料，無搬移／相容窗口；目前先本機，真模型與部署授權另定。
- `inherited`：Next.js/FastAPI 已選定且仍符合這次全端學習目標；Java 套件、Redis/COS/sharding 不繼承。
- 未授權外部帳號／費用是當前執行限制，不作永遠排除 OIDC、queue 或 object storage 的理由。

## Options Considered

### 身份來源與 session

- **基準**：同源 Web 使用成熟安全機制的 server-side session，參考 [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)。
- 本地密碼＋Cookie session：可練身份生命週期，自負 hashing、節流、CSRF、輪替與撤銷。
- OIDC＋本地 session：減少密碼維運、支援 SSO，增加外部配置与帳號連結。
- JWT：有多 client 的傳遞用途，但本案未有需求；立即撤銷仍需額外狀態。OIDC 是身份來源，不與 Cookie session 互斥。

### 發布與答案版本

- **基準**：草稿與已發布 revision 分開、核准後切換，參考 [Wagtail revisions](https://docs.wagtail.org/en/stable/reference/models.html)。
- 不可變內容 version＋獨立審核＋active pointer：審核、答案、cache 共用內容身分，需更多保留資料与狀態。
- 可變內容＋答案完整 snapshot：結果可保存，仍須另外隔離待審与已核准內容。
- 送審期間可保留舊版或立即隱藏；前者持續可用、狀態較多，後者較簡單但會中斷公開使用。

### AI 執行與 cache

- **基準**：需要跨程序持久工作時採 queue/worker；[FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) 區分 process-local 與多程序背景工作。
- request-scoped 出題＋API-owned bounded scoring tasks／DB claim：元件較少，自建 scheduler、lease、fencing、shutdown 与恢復。
- durable queue/worker：獨立擴容、恢復更強，增加 broker／worker 與部署驗收。
- 全同步：實作直接，請求時間與使用體驗受模型延遲限制。
- cache 可不做、限同 owner、或跨 owner；同 owner 易驗隔離、節費較有限，跨 owner 須證明產物無私有資訊。

### 圖片與刪除

- **基準**：隔離儲存、內容驗證、受控讀取，參考 [OWASP File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)。
- 本機 persistent volume：符合本機驗收，需自行保存／備份；[Docker volume](https://docs.docker.com/engine/storage/volumes/) 獨立於容器生命週期。
- object storage：適合多 instance／ephemeral host，增加外部帳號、費用與搬移。
- 可恢復下架／停用／答案隱藏：保存歷史，需 restore 與可見性規則；永久刪除：減少留存，需另做擦除、引用與稽核流程。

## Decision

- D1：本地帳號＋密碼＋opaque Cookie session；採成熟 hashing/security library，不從零自製安全演算法。
- D2/D8：不可變發布版本，修改重新審核，舊答案對應舊版；送審期間舊核准版公開，新版核准後原子切換。
- D3：出題 request-scoped async SSE、可取消；評分持久化 DB jobs/claim；成功 cache 只限同 owner/version/input。
- D4：本機 volume；upload bytes 不可變，保留版本／答案引用的 blob 不得覆寫／物理刪除。
- D7/D9：聚焦完整答題產品，省略未使用社交模板／公開測試／示範入口；已作答內容不可編輯。第一版採可恢復下架／停用／答案隱藏，永久刪除另立流程。

## Rationale

本地身份而非 OIDC 是為了實作完整 auth；代價是安全維運責任，不能以學習為由忽略成熟機制。版本而非只存結果快照，是要讓審核、題目、規則和回放對齊；圖片保留也屬此承諾。舊版持續公開避免送審中斷，代價是同時管理 draft／published。

API-owned DB claim 相較 queue 少一組 infra，却承擔實際調度与恢復成本；若這個成本超出需求再換 worker。出題取消只保證關閉 upstream transport，不保證停止計費；評分 crash 窗口也不承諾 provider exactly-once。同 owner cache 不選跨 owner 是要讓隔離可直接驗證，並在量測時檢查節費效益。

本機 volume 而非立即外部 storage 配合当前交付；不是正式備援承諾。可恢復刪除保留學習與回放資料，代價是沒有永久擦除能力；公開正式服務前須另確認保存政策。

## Expected Outcome

- owner／admin 權限与 session 撤銷可測；未核准內容不公開，舊答案與圖片仍可回放。
- 同 owner/input 的不同答案共享有效 AI job，但 answer identity 私有；錯誤／取消不假成功，crash 有可重試 failed 狀態。
- 圖片跨容器替換仍可讀；本機功能驗收、真模型品質与正式部署分開蓋章，不互相代稱。

## Followup

- 執行 repo 階段計畫，驗 immutable、cross-owner、兩 process claim、upstream 中斷、referenced image 保留与 restore 的反例。
- 真 provider 的樣本／品質／費用／延遲門檻与 hosting、保存／備份政策依量測後再拍板；進度以 repo 計畫為準，不複製進度。

## Revocation Triggers

- SSO、多 client 身份需求或密碼維運超出能力：重評身份來源与 session。
- 放棄完整版本回放、保留成本超出預算：重評 version／blob retention，不能靜默刪既有引用。
- 頻繁部署中斷、DB 調度瓶頸或獨立 AI 擴容需求：重評 queue/worker；cache 沒有節費收益時重評是否保留。
- 多主機或 ephemeral filesystem、明確 RPO/RTO：重評 storage／backup；需要永久刪除時另設資料生命週期。

## Review Notes

兩份獨立草稿的有效論點已納入身份/session 分離、自建 scheduler 成本、圖片引用保留、shutdown 与回復條件。沒有以獨立草稿同意現有選擇代稱設計已驗證。

## Related

- 本 ADR 即本次使用者与 agent 討論的原始決策紀錄，無另一份外部來源文件。
- 功能參考固定於 [yudada e5eb265](https://github.com/liyupi/yudada/tree/e5eb265817f13481a543c8a5da4e409d716363e7)，原碼只作本機閱讀，新實作獨立撰寫。
- 執行計畫位於 `docs/plans/2026-10-01-full-rebuild.md`。
- 本 ADR 無新增 Lessons Rules；局部驗收不代表 AI 或部署完成。
