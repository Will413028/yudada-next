"use client";

import { useState } from "react";
import Image from "next/image";

export function SharePanel({ appId, url }: { appId: string; url: string }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  async function copy() {
    try { await navigator.clipboard.writeText(url); setMessage("分享連結已複製。"); }
    catch { setMessage("請選取分享連結並手動複製。"); }
  }
  return <section aria-label="分享應用"><button onClick={() => setOpen(!open)}>{open ? "收起分享" : "分享應用"}</button>
    {open && <div><label>分享連結<input readOnly value={url} /></label><button onClick={copy}>複製分享連結</button>
      <Image src={`/api/v1/apps/${appId}/qr`} alt="應用分享 QR Code" width={240} height={240} unoptimized />
      <a href={`/api/v1/apps/${appId}/qr`} download={`yudada-${appId}.png`}>下載 QR Code</a></div>}
    <p aria-live="polite">{message}</p></section>;
}
