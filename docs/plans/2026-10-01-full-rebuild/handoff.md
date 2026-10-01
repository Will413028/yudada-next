# yudada-next session 交接

## To resume

```text
繼續 personal/yudada-next 完整產品重做。
Repo：/Users/will/second-brain/.projects/personal/yudada-next；branch：main。
先讀 AGENTS.md、AGENTS.local.md、docs/plans/2026-10-01-full-rebuild.md 及附件 contracts.md、review-ledger.md。
Will 因關閉 session 要求先 commit 並 recording/decision-log；本次沒有取消完整產品目標。
Done：步驟0–3完成；步驟4發布審核／不可變圖片／搜尋分享／管理與可恢復隱藏已完成；四個gate全exit0，最終驗收詳review-ledger.md。
Next：接5a fake HTTP provider／async adapter／schema spike，再5b/5c AI出題與評分、6a/6b統計與可靠性、7完整對帳。
Premises：Next.js＋FastAPI、無舊部署資料、本地帳密Cookie session、immutable versions、送審舊版持續公開、DB claim評分、same-owner cache、本機volume、可恢復刪除；2026-10-01 Will決定，仍成立。
真provider／品質與成本門檻／部署保存方案未定；不能用fake或transport證據聲稱真模型或上線完成。
```

## Worth knowing

- 本機完整 gate 使用 `TEST_POSTGRES_BIN=/opt/homebrew/bin`，建立自有 native PostgreSQL16.15 temporary cluster；預設 CI 為 Docker17。舊 Docker17 runtime 證據只含 migration0003／HTTP8／owner mutation，不代表0004完整驗收。
- 同一 checkout 的 check/integration/E2E/faults 序列跑，runner 有 flock；不並行 production builds。API_ORIGIN 是 build-time rewrite，PUBLIC_ORIGIN 必須精確對應 Web origin。
- dev Web3300／API8300／DB55433；upload 預設 XDG_DATA_HOME/yudada-next/uploads 或 ~/.local/share/yudada-next/uploads，UPLOAD_ROOT 可指本機 volume；驗收使用独立 temporary storage。
- User session creation 與停用共用 User row lock；新作答與下架共用 LearningApp row lock。回歸以 pg_blocking_pids barrier 證明請求已等待，不用固定 sleep 猜 race。
- 保存期間鎖完整編輯器與切換，Promise gate 保護跨草稿回應；已隱藏答案可由 owner 或 admin 恢復，answer內容仍不可修改。下架／恢復不自動公開，必須明確再發布核准版本。
- 6a 功能對帳須補核原版 userProfile/bio 欄位，目前新 profile 僅 display name/avatar；未批准省略，不可漏掉。
- AI 評分目前回503，正式 generation／jobs/cache 尚未實作；統計、負載量測、真provider與部署未完成。
- Reference source固定 e5eb265817f13481a543c8a5da4e409d716363e7 並ignored；不提交參考原碼。查詢入口與host參數在ignored AGENTS.local.md。
- 第二腦共享工作區有其他 session dirty/staged，保留；本次只提交 yudada-next 專案、3份自身daily與2份tech案例及對應frontend衍生索引。

## Persistence

- 原架構 ADR 保留，不新增 bug／implementation ADR。跨專案知識已落 SSE Case7 與 React Case10，專案頁含 backlink。
- 完整產品尚未完成；daily保留 in-flight。最後 commit hash 與檢查結論由本 session 工作紀錄與 git log 核對。
