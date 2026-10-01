"use client";
import { useState } from "react";
import type { components } from "../../lib/api/schema";
import { createApiClient } from "../../lib/api/client";

export function HistoryList({ initialAnswers, csrf, includedHidden = false }: { initialAnswers: components["schemas"]["AnswerView"][]; csrf: string; includedHidden?: boolean }) {
  const [answers, setAnswers] = useState(initialAnswers);
  const [page, setPage] = useState(2);
  const [more, setMore] = useState(initialAnswers.length === 20);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function loadMore() {
    setBusy(true);
    try {
      const result = await createApiClient().GET("/api/v1/me/answers", { params: { query: { page, page_size: 20, included_hidden: includedHidden } } });
      if (!result.data || !result.response.ok) throw new Error();
      const rows = result.data;
      setAnswers((existing) => [...existing, ...rows.filter((row) => !existing.some((item) => item.id === row.id))]);
      setPage((value) => value + 1); setMore(rows.length === 20);
    } catch { setMessage("無法載入更多紀錄。"); } finally { setBusy(false); }
  }
  async function visibility(id: string, hidden: boolean) {
    if (busy) return;
    setBusy(true);
    try {
      const options = { params: { path: { answer_id: id } }, headers: { "X-CSRF-Token": csrf } };
      const result = hidden ? await createApiClient().POST("/api/v1/answers/{answer_id}/restore", options)
        : await createApiClient().DELETE("/api/v1/answers/{answer_id}", options);
      if (!result.response.ok) throw new Error();
      window.location.reload();
    } catch { setMessage("無法變更紀錄顯示狀態。"); setBusy(false); }
  }
  return <section>{answers.length ? <ul>{answers.map((answer) => <li key={answer.id}>
    <h2>{String(answer.result_snapshot?.app_name ?? "答題紀錄")}</h2>
    <p>{String(answer.result_snapshot?.name ?? "評分中")}</p>{!answer.hidden_at && <a href={`/answers/${answer.id}`}>查看結果</a>}
    <button disabled={busy} onClick={() => visibility(answer.id, !!answer.hidden_at)}>{answer.hidden_at ? "恢復紀錄" : "隱藏紀錄"}</button>
  </li>)}</ul> : <p>還沒有作答紀錄。</p>}
  {more && <button disabled={busy} onClick={loadMore}>載入更多紀錄</button>}<p role="status">{message}</p></section>;
}
