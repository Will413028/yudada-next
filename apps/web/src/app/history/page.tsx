import Link from "next/link";
import { redirect } from "next/navigation";
import { apiForRequest } from "../../lib/api/server";
import { HistoryList } from "./history-list";

export default async function HistoryPage({ searchParams }: { searchParams: Promise<{ all?: string }> }) {
  const includedHidden = (await searchParams).all === "1";
  const api = await apiForRequest();
  const identity = await api.GET("/api/v1/auth/me");
  if (identity.response.status === 401) redirect("/account");
  if (!identity.data) throw new Error("無法確認登入狀態");
  const answers = await api.GET("/api/v1/me/answers", { params: { query: { included_hidden: includedHidden } } });
  if (!answers.data) throw new Error("無法載入紀錄");
  return <main><nav><Link href="/">yudada next</Link><a href="/account">我的帳號</a></nav>
    <header><h1>作答紀錄</h1><p>每次探索的答案，都留在這裡。</p></header>
    <nav><a href="/history">顯示中的紀錄</a><a href="/history?all=1">包含已隱藏紀錄</a></nav>
    <HistoryList key={String(includedHidden)} initialAnswers={answers.data} csrf={identity.data.csrf_token} includedHidden={includedHidden} /></main>;
}
