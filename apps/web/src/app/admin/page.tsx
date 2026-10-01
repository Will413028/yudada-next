import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { apiForRequest } from "../../lib/api/server";
import { AnswerBoard, AppBoard, ReviewBoard, UserBoard } from "./boards";

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ tab?: string; page?: string; q?: string; all?: string }> }) {
  const query = await searchParams;
  const api = await apiForRequest();
  const identity = await api.GET("/api/v1/auth/me");
  if (identity.response.status === 401) redirect("/account");
  if (!identity.data) throw new Error("無法載入管理者身分");
  if (identity.data.user.role !== "admin") notFound();
  const tab = ["reviews", "users", "apps", "questions", "rules", "answers"].includes(query.tab ?? "") ? query.tab! : "reviews";
  const requested = Number(query.page ?? 1);
  const page = Number.isSafeInteger(requested) && requested > 0 ? requested : 1;
  const q = (query.q ?? "").slice(0, 120);
  const all = query.all === "1";
  const csrf = identity.data.csrf_token;
  let content: React.ReactNode;
  let count = 0;
  if (tab === "users") {
    const result = await api.GET("/api/v1/admin/users", { params: { query: { page, page_size: 20, q } } });
    if (!result.data) throw new Error("無法載入使用者");
    count = result.data.length; content = <UserBoard users={result.data} csrf={csrf} />;
  } else if (tab === "reviews") {
    const result = await api.GET("/api/v1/admin/reviews", { params: { query: { page, page_size: 20 } } });
    if (!result.data) throw new Error("無法載入審核");
    count = result.data.length; content = <ReviewBoard reviews={result.data} csrf={csrf} />;
  } else if (tab === "answers") {
    const result = await api.GET("/api/v1/admin/answers", { params: { query: { page, page_size: 20, included_hidden: all } } });
    if (!result.data) throw new Error("無法載入答案");
    count = result.data.length; content = <AnswerBoard answers={result.data} csrf={csrf} />;
  } else if (tab === "questions") {
    const result = await api.GET("/api/v1/admin/questions", { params: { query: { page, page_size: 20 } } });
    if (!result.data) throw new Error("無法載入題目");
    count = result.data.length; content = <section><h2>題目管理</h2><ul>{result.data.map((row) => <li key={row.app_id}><h3>{row.title}</h3>
      <ol>{row.questions.map((question, index) => <li key={index}>{question.title}<ul>{question.options.map((option) => <li key={option.key}>{option.key}：{option.text} · 分數 {option.score} · 屬性 {option.property}</li>)}</ul></li>)}</ol>
      <a href={`/studio?app=${row.app_id}`}>編輯題目草稿</a></li>)}</ul></section>;
  } else if (tab === "rules") {
    const result = await api.GET("/api/v1/admin/scoring-rules", { params: { query: { page, page_size: 20 } } });
    if (!result.data) throw new Error("無法載入規則");
    count = result.data.length; content = <section><h2>評分規則管理</h2><ul>{result.data.map((row) => <li key={row.app_id}><h3>{row.title}</h3>
      <ol>{row.rules.map((rule, index) => <li key={index}>{rule.name} · 最低分 {rule.threshold} · 屬性 {rule.properties?.join("、")}<p>{rule.description}</p></li>)}</ol>
      <a href={`/studio?app=${row.app_id}`}>編輯評分規則草稿</a></li>)}</ul></section>;
  } else {
    const result = await api.GET("/api/v1/admin/apps", { params: { query: { page, page_size: 20, q, included_deleted: all } } });
    if (!result.data) throw new Error("無法載入應用");
    count = result.data.length; content = <AppBoard apps={result.data} csrf={csrf} />;
  }
  function pageUrl(number: number) { return `/admin?${new URLSearchParams({ tab, page: String(number), q, all: all ? "1" : "0" })}`; }
  return <main><nav><Link href="/">yudada next</Link><a href="/account">我的帳號</a></nav><header><h1>管理後台</h1></header>
    <nav aria-label="管理功能">{[["reviews", "版本審核"], ["users", "使用者"], ["apps", "應用"], ["questions", "題目"], ["rules", "評分規則"], ["answers", "答案"]].map(([key, name]) => <a key={key} href={`/admin?tab=${key}`} aria-current={tab === key ? "page" : undefined}>{name}</a>)}</nav>
    <form method="get"><input type="hidden" name="tab" value={tab} />
      {(tab === "users" || tab === "apps") && <label>管理搜尋<input name="q" maxLength={120} defaultValue={q} /></label>}
      {(tab === "apps" || tab === "answers") && <label><input name="all" type="checkbox" value="1" defaultChecked={all} />包含已刪除或隱藏</label>}
      <button>套用篩選</button></form>
    {content}
    <div className="editor-actions">{page > 1 && <a href={pageUrl(page - 1)}>上一頁</a>}{count === 20 && <a href={pageUrl(page + 1)}>下一頁</a>}</div>
  </main>;
}
