import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "yudada-next · 答題探索",
  description: "建立、分享與探索你的答題應用",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-Hant"><body>{children}</body></html>;
}
