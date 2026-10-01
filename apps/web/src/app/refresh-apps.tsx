"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { listApps } from "../lib/api/client";

export function RefreshApps({ page = 1, q }: { page?: number; q?: string }) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  async function refresh() {
    setLoading(true);
    setStatus("");
    try {
      const apps = await listApps("", undefined, page === 1 ? undefined : page, q);
      setStatus(`已更新：${apps.map((app) => app.name).join("、")}`);
      router.refresh();
    } catch {
      setStatus("暫時無法更新，請稍後重試。");
    } finally {
      setLoading(false);
    }
  }
  return <div className="refresh"><button disabled={loading} onClick={refresh}>{loading ? "更新中…" : "更新列表"}</button><p role="status">{status}</p></div>;
}
