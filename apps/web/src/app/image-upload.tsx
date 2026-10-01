"use client";

import Image from "next/image";
import { useState } from "react";
import { createApiClient } from "../lib/api/client";

export function ImageUpload({ label, purpose, value, csrf, busy, onBusy, onChange }: {
  label: string; purpose: "avatar" | "cover" | "result"; value: string | null | undefined;
  csrf: string; busy: boolean; onBusy: (value: boolean) => void; onChange: (id: string | null) => void;
}) {
  const [message, setMessage] = useState("");
  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file || busy) return;
    if (file.size > 1024 * 1024) { setMessage("圖片最大 1 MiB。"); input.value = ""; return; }
    onBusy(true); setMessage("");
    try {
      const result = await createApiClient().POST("/api/v1/uploads", {
        params: { query: { purpose } }, headers: { "X-CSRF-Token": csrf, "Content-Type": "application/octet-stream" },
        body: file as unknown as string, bodySerializer: () => file,
      });
      if (!result.response.ok || !result.data) throw new Error();
      onChange(result.data.id); setMessage("圖片已上傳，儲存後套用。");
    } catch { setMessage("無法上傳，請使用有效的 PNG、JPEG 或 WebP，最大 1 MiB。"); }
    finally { onBusy(false); input.value = ""; }
  }
  return <div><label>{label}<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={upload} /></label>
    {value && <><Image src={`/api/v1/uploads/${value}`} alt={label} width={160} height={160} unoptimized />
      <button type="button" disabled={busy} onClick={() => onChange(null)}>移除{label}</button></>}
    <p aria-live="polite">{message}</p></div>;
}
