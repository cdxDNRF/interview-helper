import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "interview-helper · AI 模拟面试",
  description: "面向工程师的多赛道题库突击、源码深挖、四级追问状态机与证据锚定复盘平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="relative min-h-screen overflow-x-hidden bg-[#05070e] text-zinc-100 antialiased">
        {/* Ambient obsidian glassmorphism light field */}
        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
        >
          <div className="absolute -left-24 -top-28 h-[420px] w-[420px] rounded-full bg-sky-500/[0.11] blur-[120px]" />
          <div className="absolute right-[-80px] top-12 h-[380px] w-[380px] rounded-full bg-indigo-500/[0.10] blur-[120px]" />
          <div className="absolute bottom-[-140px] left-1/3 h-[360px] w-[460px] rounded-full bg-emerald-500/[0.07] blur-[130px]" />
        </div>

        <Suspense fallback={<div className="relative z-10 h-14 border-b border-white/[0.08] bg-[#070a14]/75 backdrop-blur-xl" />}>
          <Navbar />
        </Suspense>
        <main className="relative z-10 mx-auto max-w-7xl px-4 py-6 sm:px-6">
          <Suspense fallback={<div className="py-12 text-center text-sm text-zinc-400">加载中...</div>}>
            {children}
          </Suspense>
        </main>
      </body>
    </html>
  );
}
