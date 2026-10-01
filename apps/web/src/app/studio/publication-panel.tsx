"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createApiClient } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";

type Review = components["schemas"]["ReviewView"];
type Draft = components["schemas"]["DraftView"];

export function PublicationPanel({ draft, csrf, busy, onBusy }: {
  draft: Draft; csrf: string; busy: boolean; onBusy: (value: boolean) => void;
}) {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [message, setMessage] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [page, setPage] = useState(1);
  useEffect(() => {
    const controller = new AbortController();
    createApiClient().GET("/api/v1/apps/{app_id}/submissions", {
      params: { path: { app_id: draft.app_id }, query: { page, page_size: 20 } },
      signal: controller.signal,
    }).then((result) => {
      if (!controller.signal.aborted) {
        if (result.data) setReviews(result.data);
        else setMessage("無法載入審核紀錄。");
      }
    }).catch(() => { if (!controller.signal.aborted) setMessage("無法載入審核紀錄。"); });
    return () => controller.abort();
  }, [draft.app_id, page, refresh]);
  async function act(action: "submit" | "unpublish" | "delete" | "publish", versionId?: string) {
    if (busy) return;
    onBusy(true); setMessage("");
    const options = { params: { path: { app_id: draft.app_id } }, headers: { "X-CSRF-Token": csrf } };
    try {
      const api = createApiClient();
      const result = action === "submit"
        ? await api.POST("/api/v1/apps/{app_id}/submissions", { ...options, body: { expected_revision: draft.revision } })
        : action === "unpublish" ? await api.POST("/api/v1/apps/{app_id}/unpublish", options)
        : action === "delete" ? await api.DELETE("/api/v1/apps/{app_id}", options)
        : await api.POST("/api/v1/apps/{app_id}/publish", { ...options, body: { version_id: versionId! } });
      if (!result.response.ok) {
        setMessage(result.response.status === 422 ? "請補齊題目與有效的評分規則。"
          : result.response.status === 409 ? "狀態已變更或正在審核，請重新載入。" : "操作失敗，請稍後重試。");
        return;
      }
      if (action === "delete") { window.location.assign(new URL("/studio?deleted=1", window.location.origin).href); return; }
      setMessage(action === "submit" ? "已送出審核，現有公開版本持續可用。"
        : action === "unpublish" ? "已下架。" : "已公開核准版本。");
      setRefresh((value) => value + 1);
    } catch { setMessage("操作失敗，請稍後重試。"); }
    finally { onBusy(false); }
  }
  const names = { pending: "待審核", approved: "已核准", rejected: "已退回" };
  return <section aria-label="發布管理"><h2>發布與審核</h2>
    <p>先儲存草稿，再送出審核。核准後分享頁才會顯示新版。</p>
    <div className="editor-actions"><button disabled={busy} onClick={() => act("submit")}>送出審核</button>
      <button disabled={busy} onClick={() => act("unpublish")}>下架應用</button>
      <button disabled={busy} onClick={() => act("delete")}>移至已刪除</button>
      <Link href={`/apps/${draft.app_id}`}>查看分享頁</Link></div>
    <ul>{reviews.map((review) => <li key={review.version_id}><h3>版本 {review.sequence}：{review.title}</h3>
      <p>{names[review.status as keyof typeof names] ?? review.status}{review.reason && ` · ${review.reason}`}</p>
      {review.status === "approved" && <button disabled={busy} onClick={() => act("publish", review.version_id)}>公開此核准版本</button>}
    </li>)}</ul>
    <div className="editor-actions">{page > 1 && <button disabled={busy} onClick={() => setPage((value) => value - 1)}>上一頁審核紀錄</button>}
      {reviews.length === 20 && <button disabled={busy} onClick={() => setPage((value) => value + 1)}>下一頁審核紀錄</button>}</div>
    <p role="status" aria-label="發布狀態">{message}</p>
  </section>;
}
