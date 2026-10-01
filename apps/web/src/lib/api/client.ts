import createClient from "openapi-fetch";
import type { paths } from "./schema";

export function createApiClient(baseUrl = "", cookie?: string) {
  return createClient<paths>({
    baseUrl,
    credentials: "same-origin",
    headers: cookie ? { cookie } : undefined,
    cache: "no-store",
  });
}

export async function listApps(baseUrl = "", cookie?: string, page?: number, q?: string) {
  const { data, response } = await createApiClient(baseUrl, cookie).GET("/api/v1/apps", page || q ? { params: { query: { page, q } } } : undefined);
  if (!response.ok || !data) throw new Error(`API request failed (${response.status})`);
  return data;
}
