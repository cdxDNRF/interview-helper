import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "interview-helper · AI 模拟面试",
  description: "面向工程师的源码级深挖、四级追问状态机与证据锚定复盘平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        <Suspense fallback={<div className="h-14 border-b border-zinc-800/80 bg-zinc-950" />}>
          <Navbar />
        </Suspense>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          <Suspense fallback={<div className="py-12 text-center text-sm text-zinc-500">加载中...</div>}>
            {children}
          </Suspense>
        </main>
      </body>
    </html>
  );
}
