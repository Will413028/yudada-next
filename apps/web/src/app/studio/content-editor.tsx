"use client";
import type { components } from "../../lib/api/schema";
import { ImageUpload } from "../image-upload";

type Content = components["schemas"]["DraftContent"];

export function ContentEditor({ value, onChange, csrf, busy, onBusy }: { value: Content; onChange: (value: Content) => void; csrf: string; busy: boolean; onBusy: (value: boolean) => void }) {
  const questions = value.questions ?? [];
  const rules = value.rules ?? [];
  function question(index: number, patch: Partial<components["schemas"]["Question"]>) {
    onChange({ ...value, questions: questions.map((row, ordinal) => ordinal === index ? { ...row, ...patch } : row) });
  }
  function rule(index: number, patch: Partial<components["schemas"]["Rule"]>) {
    onChange({ ...value, rules: rules.map((row, ordinal) => ordinal === index ? { ...row, ...patch } : row) });
  }
  return <div><h3>題目與選項</h3><p>測評以選項屬性配對結果；得分類以選項分數加總。</p>
    {questions.map((row, index) => <fieldset key={index}><legend>題目 {index + 1}</legend>
      <label>題目 {index + 1} 內容<input required maxLength={1000} value={row.title} onChange={(event) => question(index, { title: event.target.value })} /></label>
      {row.options.map((option, ordinal) => <fieldset key={ordinal}><legend>選項 {ordinal + 1}</legend>
        <label>題目 {index + 1} 選項 {ordinal + 1} 代號<input required maxLength={16} value={option.key} onChange={(event) => question(index, { options: row.options.map((item, number) => number === ordinal ? { ...item, key: event.target.value } : item) })} /></label>
        <label>題目 {index + 1} 選項 {ordinal + 1} 文字<input required maxLength={500} value={option.text} onChange={(event) => question(index, { options: row.options.map((item, number) => number === ordinal ? { ...item, text: event.target.value } : item) })} /></label>
        <label>題目 {index + 1} 選項 {ordinal + 1} 分數<input type="number" min={-10000} max={10000} required value={option.score ?? 0} onChange={(event) => question(index, { options: row.options.map((item, number) => number === ordinal ? { ...item, score: Number(event.target.value) } : item) })} /></label>
        <label>題目 {index + 1} 選項 {ordinal + 1} 屬性<input maxLength={80} value={option.property ?? ""} onChange={(event) => question(index, { options: row.options.map((item, number) => number === ordinal ? { ...item, property: event.target.value } : item) })} /></label>
        {row.options.length > 2 && <button type="button" onClick={() => question(index, { options: row.options.filter((_, number) => number !== ordinal) })}>移除選項 {ordinal + 1}</button>}
      </fieldset>)}
      <div className="editor-actions"><button type="button" disabled={row.options.length >= 6} onClick={() => {
        const key = ["A", "B", "C", "D", "E", "F"].find((candidate) => !row.options.some((option) => option.key === candidate)) ?? crypto.randomUUID().slice(0, 8);
        question(index, { options: [...row.options, { key, text: "新選項", score: 0, property: "" }] });
      }}>新增選項</button><button type="button" onClick={() => onChange({ ...value, questions: questions.filter((_, ordinal) => ordinal !== index) })}>移除題目 {index + 1}</button>
      {index > 0 && <button type="button" onClick={() => {
        const reordered = [...questions]; [reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]];
        onChange({ ...value, questions: reordered });
      }}>上移題目 {index + 1}</button>}</div>
    </fieldset>)}
    <button type="button" disabled={questions.length >= 100} onClick={() => onChange({ ...value, questions: [...questions, {
      title: "新題目", options: [{ key: "A", text: "選項 A", score: 0, property: "I" }, { key: "B", text: "選項 B", score: 1, property: "E" }],
    }] })}>新增題目</button>
    <h3>結果規則</h3><p>結果依此順序保存；平手時使用較前面的規則。得分類需有涵蓋最低分的門檻。</p>
    {rules.map((row, index) => <fieldset key={index}><legend>結果 {index + 1}</legend>
      <label>結果 {index + 1} 名稱<input required maxLength={120} value={row.name} onChange={(event) => rule(index, { name: event.target.value })} /></label>
      <label>結果 {index + 1} 說明<textarea maxLength={4000} value={row.description ?? ""} onChange={(event) => rule(index, { description: event.target.value })} /></label>
      <ImageUpload label={`結果 ${index + 1} 圖片`} purpose="result" value={row.image_id} csrf={csrf} busy={busy} onBusy={onBusy} onChange={(image_id) => rule(index, { image_id })} />
      <label>結果 {index + 1} 最低分<input type="number" required min={-1000000} max={1000000} value={row.threshold ?? 0} onChange={(event) => rule(index, { threshold: Number(event.target.value) })} /></label>
      <label>結果 {index + 1} 屬性（逗號分隔）<input value={(row.properties ?? []).join(",")} onChange={(event) => rule(index, { properties: event.target.value ? event.target.value.split(",").map((item) => item.trim()) : [] })} /></label>
      <div className="editor-actions"><button type="button" onClick={() => onChange({ ...value, rules: rules.filter((_, ordinal) => ordinal !== index) })}>移除結果 {index + 1}</button>
      {index > 0 && <button type="button" onClick={() => { const reordered = [...rules]; [reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]]; onChange({ ...value, rules: reordered }); }}>上移結果 {index + 1}</button>}</div>
    </fieldset>)}
    <button type="button" disabled={rules.length >= 50} onClick={() => onChange({ ...value, rules: [...rules, { name: "新結果", description: "", threshold: 0, properties: ["I"] }] })}>新增結果</button>
  </div>;
}
