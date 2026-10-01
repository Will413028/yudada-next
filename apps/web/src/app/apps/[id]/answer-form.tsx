"use client";

import { useRef, useState } from "react";
import { createApiClient } from "../../../lib/api/client";
import type { components } from "../../../lib/api/schema";

export function AnswerForm({ versionId, questions, csrf }: {
  versionId: string; questions: components["schemas"]["PublicQuestion"][]; csrf: string;
}) {
  const submission = useRef<{ key: string; choices: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [answerId, setAnswerId] = useState<string | null>(null);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || answerId) return;
    const form = new FormData(event.currentTarget);
    const choices = questions.map((_, index) => String(form.get(`question-${index}`)));
    if (!submission.current || JSON.stringify(submission.current.choices) !== JSON.stringify(choices)) {
      submission.current = { key: crypto.randomUUID(), choices };
    }
    setBusy(true); setMessage("");
    try {
      const result = await createApiClient().POST("/api/v1/versions/{version_id}/answers", {
        params: { path: { version_id: versionId }, header: { "idempotency-key": submission.current.key } }, body: { choices },
        headers: { "X-CSRF-Token": csrf },
      });
      if (!result.response.ok || !result.data) throw new Error();
      setAnswerId(result.data.id); setMessage("答案已提交。");
    } catch { setMessage("提交失敗，請重試或重新登入。"); }
    finally { setBusy(false); }
  }
  return <section><form onSubmit={submit}>
    <fieldset disabled={busy || !!answerId}>{questions.map((question, index) => <fieldset key={index}>
      <legend>{index + 1}. {question.title}</legend>{question.options.map((option) => <label key={option.key}>
        <input type="radio" name={`question-${index}`} value={option.key} required />{option.text}
      </label>)}
    </fieldset>)}<button disabled={busy || !!answerId}>{busy ? "提交中…" : "提交答案"}</button></fieldset>
  </form><p role="status">{message}</p>{answerId && <a href={`/answers/${answerId}`}>查看結果</a>}</section>;
}
