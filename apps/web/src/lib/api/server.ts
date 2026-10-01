import "server-only";
import { headers } from "next/headers";
import { createApiClient, listApps } from "./client";

export async function apiForRequest() {
  const incoming = await headers();
  return createApiClient(process.env.API_ORIGIN ?? "http://127.0.0.1:8300", incoming.get("cookie") ?? undefined);
}

export async function listAppsForRequest(page?: number, q?: string) {
  const incoming = await headers();
  return listApps(process.env.API_ORIGIN ?? "http://127.0.0.1:8300", incoming.get("cookie") ?? undefined, page, q);
}
