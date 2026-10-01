"use client";

import { useState } from "react";
import Image from "next/image";
import { createApiClient } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";

export function ReviewBoard({ reviews, csrf }: { reviews: components["schemas"]["ReviewView"][]; csrf: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function decide(event: React.FormEvent<HTMLFormElement>, versionId: string) {
    event.preventDefault(); if (busy) return; setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await createApiClient().POST("/api/v1/admin/reviews/{version_id}", {
        params: { path: { version_id: versionId } }, headers: { "X-CSRF-Token": csrf },
        body: { status: String(form.get("status")) as "approved" | "rejected", reason: String(form.get("reason")) },
      });
      if (!result.response.ok) { setMessage(result.response.status === 409 ? "審核狀態已變更，或已有更新的核准版本。" : "審核失敗。"); return; }
      window.location.reload();
    } catch { setMessage("審核失敗，請稍後重試。"); }
    finally { setBusy(false); }
  }
  return <section><h2>待審核版本</h2>{!reviews.length && <p>目前沒有待審核版本。</p>}
    <ul>{reviews.map((review) => <li key={review.version_id}><h3>{review.title} · 版本 {review.sequence}</h3><p>{review.description}</p>
      {review.cover_id && <Image src={`/api/v1/uploads/${review.cover_id}`} alt={`${review.title}審核封面`} width={320} height={180} unoptimized />}
      <p>{review.app_type === "score" ? "得分" : "測評"} · {review.strategy === "ai" ? "AI 評分" : "自訂規則"}</p>
      <ol>{review.content.questions.map((question, index) => <li key={index}>{question.title}<ul>{question.options.map((option) => <li key={option.key}>{option.key}：{option.text} · 分數 {option.score} · 屬性 {option.property}</li>)}</ul></li>)}</ol>
      <ol>{review.content.rules?.map((rule, index) => <li key={index}>{rule.name} · 最低分 {rule.threshold} · 屬性 {rule.properties?.join("、")}<p>{rule.description}</p>
        {rule.image_id && <Image src={`/api/v1/uploads/${rule.image_id}`} alt={`${rule.name}圖片`} width={160} height={160} unoptimized />}</li>)}</ol>
      <form onSubmit={(event) => decide(event, review.version_id)}><fieldset disabled={busy}>
        <label htmlFor={`decision-${review.version_id}`}>審核結果</label><select id={`decision-${review.version_id}`} name="status"><option value="approved">核准</option><option value="rejected">退回</option></select>
        <label>審核意見<textarea name="reason" maxLength={2000} /></label><button>確認審核</button>
      </fieldset></form></li>)}</ul><p role="status">{message}</p></section>;
}

export function UserBoard({ users, csrf }: { users: components["schemas"]["AdminUserView"][]; csrf: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function save(event: React.FormEvent<HTMLFormElement>, userId?: string) {
    event.preventDefault(); if (busy) return; setBusy(true);
    const form = new FormData(event.currentTarget);
    const display_name = String(form.get("display_name"));
    const role = String(form.get("role")) as "user" | "admin";
    try {
      const api = createApiClient();
      const result = userId ? await api.PATCH("/api/v1/admin/users/{user_id}", {
        params: { path: { user_id: userId } }, headers: { "X-CSRF-Token": csrf },
        body: { display_name, role, active: form.get("active") === "on" },
      }) : await api.POST("/api/v1/admin/users", { headers: { "X-CSRF-Token": csrf },
        body: { display_name, role, account: String(form.get("account")), password: String(form.get("password")) },
      });
      if (!result.response.ok) { setMessage("更新失敗，請確認帳號與輸入。"); return; }
      window.location.reload();
    } catch { setMessage("更新失敗，請稍後重試。"); }
    finally { setBusy(false); }
  }
  return <section><h2>使用者管理</h2><ul>{users.map((user) => <li key={user.id}><h3>{user.account}</h3>
    <form onSubmit={(event) => save(event, user.id)}><fieldset disabled={busy}>
      <label>顯示名稱<input name="display_name" maxLength={80} required defaultValue={user.display_name} /></label>
      <label htmlFor={`role-${user.id}`}>角色</label><select id={`role-${user.id}`} name="role" defaultValue={user.role}><option value="user">一般使用者</option><option value="admin">管理者</option></select>
      <label><input type="checkbox" name="active" defaultChecked={user.active} />帳號啟用</label><button>儲存使用者</button>
    </fieldset></form></li>)}</ul><h3>建立使用者</h3><form onSubmit={(event) => save(event)}><fieldset disabled={busy}>
      <label>新帳號<input name="account" required minLength={3} maxLength={64} pattern="[a-zA-Z0-9_]+" autoComplete="off" /></label>
      <label>新使用者名稱<input name="display_name" required maxLength={80} /></label>
      <label>初始密碼<input type="password" name="password" required minLength={12} maxLength={128} autoComplete="new-password" /></label>
      <label htmlFor="new-user-role">新使用者角色</label><select id="new-user-role" name="role"><option value="user">一般使用者</option><option value="admin">管理者</option></select><button>建立使用者</button>
    </fieldset></form><p role="status">{message}</p></section>;
}

export function AppBoard({ apps, csrf }: { apps: components["schemas"]["AdminAppView"][]; csrf: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function act(appId: string, action: "unpublish" | "delete" | "restore") {
    if (busy) return; setBusy(true);
    const options = { params: { path: { app_id: appId } }, headers: { "X-CSRF-Token": csrf } };
    try {
      const api = createApiClient();
      const result = action === "delete" ? await api.DELETE("/api/v1/apps/{app_id}", options)
        : action === "restore" ? await api.POST("/api/v1/apps/{app_id}/restore", options)
        : await api.POST("/api/v1/apps/{app_id}/unpublish", options);
      if (!result.response.ok) { setMessage("操作失敗，請重新載入。"); return; }
      window.location.reload();
    } catch { setMessage("操作失敗，請稍後重試。"); }
    finally { setBusy(false); }
  }
  return <section><h2>應用管理</h2><ul>{apps.map((app) => <li key={app.app_id}><h3>{app.title}</h3><p>{app.description}</p>
    {app.cover_id && <Image src={`/api/v1/uploads/${app.cover_id}`} alt={`${app.title}管理封面`} width={320} height={180} unoptimized />}
    <p>{app.deleted_at ? "已刪除" : app.active_version_id ? "公開中" : "未公開"}</p>
    {app.deleted_at ? <button disabled={busy} onClick={() => act(app.app_id, "restore")}>恢復為未公開</button>
      : <div className="editor-actions"><a href={`/studio?app=${app.app_id}`}>編輯內容草稿</a><button disabled={busy} onClick={() => act(app.app_id, "unpublish")}>下架</button><button disabled={busy} onClick={() => act(app.app_id, "delete")}>移至已刪除</button></div>}
  </li>)}</ul><p role="status">{message}</p></section>;
}

export function AnswerBoard({ answers, csrf }: { answers: components["schemas"]["AdminAnswerView"][]; csrf: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function visibility(answer: components["schemas"]["AdminAnswerView"]) {
    if (busy) return; setBusy(true);
    try {
      const result = await createApiClient().PATCH("/api/v1/admin/answers/{answer_id}", {
        params: { path: { answer_id: answer.id } }, headers: { "X-CSRF-Token": csrf }, body: { hidden: !answer.hidden_at },
      });
      if (!result.response.ok) { setMessage("操作失敗。"); return; }
      window.location.reload();
    } catch { setMessage("操作失敗，請稍後重試。"); }
    finally { setBusy(false); }
  }
  return <section><h2>答案管理</h2><ul>{answers.map((answer) => <li key={answer.id}><h3>{String(answer.result_snapshot?.app_name ?? "答題結果")}</h3>
    <p>結果：{String(answer.result_snapshot?.name ?? answer.status)} · {answer.hidden_at ? "已隱藏" : "顯示中"}</p>
    <p>選項：{answer.choices.join("、")}</p><p>{String(answer.result_snapshot?.description ?? "")}</p>
    <button disabled={busy} onClick={() => visibility(answer)}>{answer.hidden_at ? "恢復答案" : "隱藏答案"}</button>
  </li>)}</ul><p role="status">{message}</p></section>;
}
