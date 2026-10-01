import { listAppsForRequest } from "../lib/api/server";
import { RefreshApps } from "./refresh-apps";
import Link from "next/link";
import Image from "next/image";

export default async function Home({ searchParams }: { searchParams: Promise<{ page?: string; q?: string }> }) {
  const query = await searchParams;
  const requestedPage = Number(query.page ?? 1);
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const q = (query.q ?? "").slice(0, 120);
  const apps = await listAppsForRequest(page === 1 ? undefined : page, q || undefined);
  function pageUrl(number: number) { return `/?${new URLSearchParams({ page: String(number), ...(q ? { q } : {}) })}`; }
  return (
    <main>
      <nav><span className="brand">yudada<span>next</span></span><span><Link href="/studio">我的應用</Link> · <Link href="/account">帳號</Link></span></nav>
      <header><p className="eyebrow">每個問題，都是探索的起點</p><h1>發現你的下一個答案。</h1><p>用一組問題認識自己，也認識更多可能。</p></header>
      <section aria-label="答題應用"><div className="section-heading"><h2>探索應用</h2><span>{apps.length} 個應用</span></div>
        <form method="get"><label>搜尋應用<input name="q" maxLength={120} defaultValue={q} /></label><button>搜尋</button></form>
        <ul>{apps.map((app) => <li key={app.id}>{app.cover_id ? <Image src={`/api/v1/uploads/${app.cover_id}`} alt={`${app.name}封面`} width={320} height={180} unoptimized /> : <span className="app-icon" aria-hidden="true">✦</span>}<h3>{app.name}</h3><p>{app.description || "從這裡開始你的答題探索。"}</p><Link href={`/apps/${app.id}`}>開始探索</Link></li>)}</ul>
        {!apps.length && <p>沒有符合條件的公開應用。</p>}
        <div className="editor-actions">{page > 1 && <Link href={pageUrl(page - 1)}>上一頁</Link>}{apps.length === 20 && <Link href={pageUrl(page + 1)}>下一頁</Link>}</div>
        <RefreshApps page={page} q={q || undefined} />
      </section>
    </main>
  );
}
