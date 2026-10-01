"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <main><h1>暫時無法載入應用</h1><p>請稍後再試一次。</p><button onClick={reset}>重新載入</button></main>;
}
