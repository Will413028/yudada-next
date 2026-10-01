"use client";

import Link from "next/link";

import { useEffect, useState } from "react";
import { createApiClient } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { ImageUpload } from "../image-upload";

type Identity = components["schemas"]["Identity"];

export default function Account() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [register, setRegister] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [avatarId, setAvatarId] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    let active = true;
    createApiClient().GET("/api/v1/auth/me").then(({ data }) => {
      if (active && data) { setIdentity(data); setAvatarId(data.user.avatar_id); }
    }).catch(() => { if (active) setMessage("暫時無法連線，請稍後重試。"); });
    return () => { active = false; };
  }, []);
  async function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const form = new FormData(event.currentTarget);
    const credentials = { account: String(form.get("account")), password: String(form.get("password")) };
    try {
      const result = register
        ? await createApiClient().POST("/api/v1/auth/register", { body: { ...credentials, display_name: String(form.get("display_name")) } })
        : await createApiClient().POST("/api/v1/auth/login", { body: credentials });
      if (!result.response.ok || !result.data) throw new Error();
      setIdentity(result.data); setAvatarId(result.data.user.avatar_id); setMessage(register ? "帳號建立成功。" : "登入成功。");
      (event.target as HTMLFormElement).reset();
    } catch { setMessage("無法完成登入或註冊，請檢查輸入；若嘗試過多，請稍後再試。"); }
    finally { setBusy(false); }
  }
  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!identity) return; setBusy(true);
    const display_name = String(new FormData(event.currentTarget).get("display_name"));
    try {
      const result = await createApiClient().PATCH("/api/v1/me", { body: { display_name, avatar_id: avatarId }, headers: { "X-CSRF-Token": identity.csrf_token } });
      if (!result.response.ok || !result.data) throw new Error();
      setIdentity({ ...identity, user: result.data }); setMessage("個人資料已更新。");
    } catch { setMessage("更新失敗，請重新登入再試。"); }
    finally { setBusy(false); }
  }
  async function logout() {
    if (!identity) return; setBusy(true);
    try {
      const result = await createApiClient().POST("/api/v1/auth/logout", { headers: { "X-CSRF-Token": identity.csrf_token } });
      if (!result.response.ok) throw new Error();
      setIdentity(null); setAvatarId(undefined); setMessage("已登出。");
    } catch { setMessage("登出失敗，請稍後重試。"); }
    finally { setBusy(false); }
  }
  return <main><nav><Link href="/">yudada next</Link><a href="/studio">我的應用</a></nav>
    <header><h1>{identity ? "我的帳號" : register ? "建立帳號" : "歡迎回來"}</h1></header>
    {identity ? <section><p>帳號：{identity.user.account}</p><form onSubmit={saveProfile}>
      <fieldset disabled={busy}>
      <label>顯示名稱<input name="display_name" required maxLength={80} defaultValue={identity.user.display_name} /></label>
      <ImageUpload label="頭像" purpose="avatar" value={avatarId} csrf={identity.csrf_token} busy={busy} onBusy={setBusy} onChange={setAvatarId} />
      <button disabled={busy}>儲存個人資料</button></fieldset></form><button disabled={busy} onClick={logout}>登出</button>
      {identity.user.role === "admin" && <a href="/admin">管理後台</a>}</section>
      : <section><form onSubmit={authenticate}>
        <label>帳號<input name="account" required minLength={3} maxLength={64} pattern="[a-zA-Z0-9_]+" autoComplete="username" /></label>
        {register && <label>顯示名稱<input name="display_name" required maxLength={80} /></label>}
        <label>密碼<input name="password" type="password" required minLength={12} maxLength={128} autoComplete={register ? "new-password" : "current-password"} /></label>
        <p>密碼至少 12 個字元。</p><button disabled={busy}>{register ? "註冊" : "登入"}</button>
      </form><button disabled={busy} onClick={() => { setRegister(!register); setMessage(""); }}>{register ? "已有帳號，前往登入" : "沒有帳號，建立帳號"}</button></section>}
    <p role="status">{message}</p></main>;
}
