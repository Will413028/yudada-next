"use client";

import Link from "next/link";

import { useState } from "react";
import { createApiClient } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { ContentEditor } from "./content-editor";
import { PublicationPanel } from "./publication-panel";
import { ImageUpload } from "../image-upload";

type Draft = components["schemas"]["DraftView"];
type Identity = components["schemas"]["Identity"];

export function Studio({ identity, initialDrafts, initialEditing, deletedMode = false }: { identity: Identity; initialDrafts: Draft[]; initialEditing?: Draft; deletedMode?: boolean }) {
  const [drafts, setDrafts] = useState(initialDrafts);
  const [editing, setEditing] = useState<Draft | null>(initialEditing ?? null);
  const [content, setContent] = useState<components["schemas"]["DraftContent"]>(initialEditing?.content ?? { questions: [], rules: [] });
  const [appType, setAppType] = useState(initialEditing?.app_type ?? "assessment");
  const [strategy, setStrategy] = useState(initialEditing?.strategy ?? "rules");
  const [coverId, setCoverId] = useState<string | null>(initialEditing?.cover_id ?? null);
  function chooseDraft(draft: Draft | null) {
    setEditing(draft); setContent(draft?.content ?? { questions: [], rules: [] });
    setAppType(draft?.app_type ?? "assessment"); setStrategy(draft?.strategy ?? "rules");
    setCoverId(draft?.cover_id ?? null);
  }
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [nextPage, setNextPage] = useState(2);
  const [hasMore, setHasMore] = useState(initialDrafts.length === 20);
  async function loadMore() {
    setBusy(true);
    try {
      const result = await createApiClient().GET("/api/v1/me/apps", {
        params: { query: { page: nextPage, page_size: 20, deleted: deletedMode } },
      });
      if (!result.response.ok || !result.data) throw new Error();
      const more = result.data;
      setDrafts((rows) => [...rows, ...more.filter((draft) => !rows.some((row) => row.app_id === draft.app_id))]);
      setNextPage((page) => page + 1); setHasMore(more.length === 20);
    } catch { setMessage("無法載入更多應用，請稍後重試。"); }
    finally { setBusy(false); }
  }
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setMessage("");
    const form = new FormData(event.currentTarget);
    const body = { title: String(form.get("title")), description: String(form.get("description")),
      app_type: String(form.get("app_type")), strategy: String(form.get("strategy")), content, cover_id: coverId };
    const options = { headers: { "X-CSRF-Token": identity.csrf_token } };
    try {
      const result = editing
        ? await createApiClient().PATCH("/api/v1/apps/{app_id}/draft", { ...options, params: { path: { app_id: editing.app_id } }, body: { ...body, expected_revision: editing.revision } })
        : await createApiClient().POST("/api/v1/apps", { ...options, body });
      if (result.response.status === 409) { setMessage("草稿已在其他地方更新，請重新載入頁面。"); return; }
      if (!result.response.ok || !result.data) throw new Error();
      const saved = result.data;
      setDrafts((rows) => [saved, ...rows.filter((row) => row.app_id !== saved.app_id)]);
      chooseDraft(saved); setMessage("草稿已儲存。");
    } catch { setMessage("無法儲存，請確認設定或重新登入。"); }
    finally { setBusy(false); }
  }
  async function restore(appId: string) {
    if (busy) return; setBusy(true);
    try {
      const result = await createApiClient().POST("/api/v1/apps/{app_id}/restore", { params: { path: { app_id: appId } }, headers: { "X-CSRF-Token": identity.csrf_token } });
      if (!result.response.ok) throw new Error();
      window.location.reload();
    } catch { setMessage("恢復失敗，請重新載入。"); }
    finally { setBusy(false); }
  }
  return <main><nav><Link href="/">yudada next</Link><a href="/account">{identity.user.display_name}</a></nav>
    <header><h1>我的應用</h1><p>建立一份屬於你的答題體驗。</p></header>
    <nav><a href="/studio">我的草稿</a><a href="/studio?deleted=1">已刪除應用</a>{identity.user.role === "admin" && <a href="/admin">管理後台</a>}</nav>
    <section><h2>{deletedMode ? "已刪除應用" : "我的草稿"}</h2>{drafts.length ? <ul>{drafts.map((draft) => <li key={draft.app_id}><h3>{draft.title}</h3><p>{draft.description}</p>{deletedMode
      ? <button disabled={busy} onClick={() => restore(draft.app_id)}>恢復為未公開</button>
      : <button disabled={busy} onClick={() => chooseDraft(draft)}>編輯</button>}</li>)}</ul> : <p>{deletedMode ? "沒有已刪除的應用。" : "還沒有應用，從下方開始建立。"}</p>}</section>
    {hasMore && <button disabled={busy} onClick={loadMore}>載入更多應用</button>}
    {!deletedMode && <section><h2>{editing ? "編輯草稿" : "建立應用"}</h2><form key={editing?.app_id ?? "new"} onSubmit={save}>
      <fieldset disabled={busy}>
      <label>名稱<input name="title" required maxLength={120} defaultValue={editing?.title ?? ""} /></label>
      <label>介紹<textarea name="description" maxLength={2000} defaultValue={editing?.description ?? ""} /></label>
      <label htmlFor="draft-app-type">應用類型</label><select id="draft-app-type" name="app_type" value={appType} onChange={(event) => { setAppType(event.target.value); if (event.target.value === "score") setStrategy("rules"); }}><option value="assessment">測評</option><option value="score">得分</option></select>
      <label htmlFor="draft-strategy">評分方式</label><select id="draft-strategy" name="strategy" value={strategy} onChange={(event) => setStrategy(event.target.value)}><option value="rules">自訂規則</option><option value="ai" disabled={appType === "score"}>AI 評分（限測評）</option></select>
      <ImageUpload label="應用封面" purpose="cover" value={coverId} csrf={identity.csrf_token} busy={busy} onBusy={setBusy} onChange={setCoverId} />
      <ContentEditor value={content} onChange={setContent} csrf={identity.csrf_token} busy={busy} onBusy={setBusy} />
      <button disabled={busy}>儲存草稿</button></fieldset></form>{editing && <button disabled={busy} onClick={() => chooseDraft(null)}>建立另一個應用</button>}
    </section>}<p role="status" aria-label="草稿儲存狀態">{message}</p>
    {editing && <PublicationPanel key={`${editing.app_id}:${editing.revision}`} draft={editing} csrf={identity.csrf_token} busy={busy} onBusy={setBusy} />}
    </main>;
}
