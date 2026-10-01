import { afterEach, describe, expect, it, vi } from "vitest";
import { listApps } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("forwards request cookies only through HTTP headers", async () => {
    const fetchMock = vi.fn(async (request: Request) => {
      expect(request.url).toBe("http://api.test/api/v1/apps");
      expect(request.headers.get("cookie")).toBe("probe_marker=1");
      return new Response(JSON.stringify([{ id: "example", name: "Example" }]), {
        headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(listApps("http://api.test", "probe_marker=1")).resolves.toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("rejects non-2xx without presenting a successful list", async () => {
    vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ code: "unavailable" }), {
      status: 503,
      headers: { "content-type": "application/json" },
    }));
    await expect(listApps("http://api.test")).rejects.toThrow("API request failed (503)");
  });
});
