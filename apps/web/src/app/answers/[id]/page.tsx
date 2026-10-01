import Link from "next/link";
import Image from "next/image";
import { notFound, redirect } from "next/navigation";
import { apiForRequest } from "../../../lib/api/server";

export default async function AnswerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await (await apiForRequest()).GET("/api/v1/answers/{answer_id}", { params: { path: { answer_id: id } } });
  if (result.response.status === 401) redirect("/account");
  if (result.response.status === 404 || result.response.status === 422) notFound();
  if (!result.data) throw new Error("無法載入結果");
  const snapshot = result.data.result_snapshot;
  return <main><nav><Link href="/">yudada next</Link><a href="/history">作答紀錄</a></nav>
    <header><p>{String(snapshot?.app_name ?? "答題結果")}</p><h1>{String(snapshot?.name ?? "評分中")}</h1></header>
    <section><p>{String(snapshot?.description ?? "稍後重新載入查看結果。")}</p>
      {typeof snapshot?.image_id === "string" && <Image src={`/api/v1/uploads/${snapshot.image_id}`} alt="結果圖片" width={640} height={360} unoptimized />}
      {snapshot?.score !== null && snapshot?.score !== undefined && <p>得分：{String(snapshot.score)}</p>}
      <p>提交時間：{new Date(result.data.created_at).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" })}</p>
      <a href={`/apps/${result.data.app_id}`}>再次探索</a></section></main>;
}
