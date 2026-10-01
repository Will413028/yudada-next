import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import { apiForRequest } from "../../../lib/api/server";
import { AnswerForm } from "./answer-form";
import { SharePanel } from "./share-panel";

export default async function AppPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const api = await apiForRequest();
  const app = await api.GET("/api/v1/apps/{app_id}", { params: { path: { app_id: id } } });
  if (app.response.status === 404 || app.response.status === 422) notFound();
  if (!app.data) throw new Error("無法載入應用");
  const questions = await api.GET("/api/v1/versions/{version_id}/questions", {
    params: { path: { version_id: app.data.version_id } },
  });
  if (!questions.data) throw new Error("無法載入題目");
  const identity = await api.GET("/api/v1/auth/me");
  return <main><nav><Link href="/">yudada next</Link><a href="/history">作答紀錄</a></nav>
    <header><h1>{app.data.name}</h1><p>{app.data.description}</p></header>
    {app.data.cover_id && <Image src={`/api/v1/uploads/${app.data.cover_id}`} alt={`${app.data.name}封面`} width={640} height={360} unoptimized />}
    <SharePanel appId={id} url={app.data.share_url} />
    {identity.data ? <AnswerForm key={`${identity.data.user.id}:${app.data.version_id}`} versionId={app.data.version_id} questions={questions.data} csrf={identity.data.csrf_token} />
      : <section><p>登入後即可作答。</p><a href="/account">登入或建立帳號</a></section>}
  </main>;
}
