import { headers } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { createApiClient } from "../../lib/api/client";
import { Studio } from "./studio";

export default async function StudioPage({ searchParams }: { searchParams: Promise<{ app?: string; deleted?: string }> }) {
  const query = await searchParams;
  const deletedMode = query.deleted === "1";
  const incoming = await headers();
  const api = createApiClient(process.env.API_ORIGIN ?? "http://127.0.0.1:8300", incoming.get("cookie") ?? undefined);
  const identity = await api.GET("/api/v1/auth/me");
  if (identity.response.status === 401) redirect("/account");
  if (!identity.response.ok || !identity.data) throw new Error("Unable to load account");
  const drafts = await api.GET("/api/v1/me/apps", { params: { query: { deleted: deletedMode } } });
  if (!drafts.response.ok || !drafts.data) throw new Error("Unable to load applications");
  let initialEditing;
  if (query.app && !deletedMode) {
    const selected = await api.GET("/api/v1/apps/{app_id}/draft", { params: { path: { app_id: query.app } } });
    if (selected.response.status === 404 || selected.response.status === 422) notFound();
    if (!selected.data) throw new Error("無法載入草稿");
    initialEditing = selected.data;
  }
  return <Studio key={`${query.app ?? "new"}:${deletedMode}`} identity={identity.data} initialDrafts={drafts.data} initialEditing={initialEditing} deletedMode={deletedMode} />;
}
