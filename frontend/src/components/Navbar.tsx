"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Activity, AudioWaveform, BookMarked, Settings, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { getSettings } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Navbar() {
  const pathname = usePathname();
  const [mockMode, setMockMode] = useState<boolean | null>(null);

  useEffect(() => {
    const syncStatus = () => {
      getSettings()
        .then((s) => setMockMode(s.mock_mode))
        .catch(() => setMockMode(null));
    };
    syncStatus();
    window.addEventListener("interview-helper-settings-updated", syncStatus);
    return () => {
      window.removeEventListener("interview-helper-settings-updated", syncStatus);
    };
  }, [pathname]);

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-[#070a14]/70 backdrop-blur-2xl shadow-[0_8px_32px_rgba(0,0,0,0.45)]">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-4 sm:gap-6">
          <Link href="/" className="flex items-center gap-2.5 text-zinc-100 hover:opacity-90">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/15 text-sky-300 border border-sky-400/30 shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]">
              <AudioWaveform className="h-4 w-4" />
            </span>
            <span className="font-semibold tracking-tight text-sm sm:text-base">
              interview-helper
            </span>
            <Badge variant="secondary" className="hidden md:inline-flex text-[11px]">
              P2 · Glass &amp; Tracks
            </Badge>
          </Link>

          <nav className="flex items-center gap-1 overflow-x-auto">
            <Link
              href="/"
              className={cn(
                "rounded-lg px-2.5 py-1.5 text-xs sm:text-sm whitespace-nowrap transition-all",
                pathname === "/"
                  ? "bg-white/[0.11] border border-white/[0.12] text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]"
                  : "border border-transparent text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100"
              )}
            >
              准备台 &amp; 历史
            </Link>
            <Link
              href="/mistakes"
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs sm:text-sm whitespace-nowrap transition-all",
                pathname.startsWith("/mistakes")
                  ? "bg-white/[0.11] border border-white/[0.12] text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]"
                  : "border border-transparent text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100"
              )}
            >
              <BookMarked className="h-3.5 w-3.5" />
              错题本
            </Link>
            <Link
              href="/observability"
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs sm:text-sm whitespace-nowrap transition-all",
                pathname.startsWith("/observability")
                  ? "bg-white/[0.11] border border-white/[0.12] text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]"
                  : "border border-transparent text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100"
              )}
            >
              <Activity className="h-3.5 w-3.5" />
              可观测性
            </Link>
            <Link
              href="/settings"
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs sm:text-sm whitespace-nowrap transition-all",
                pathname === "/settings"
                  ? "bg-white/[0.11] border border-white/[0.12] text-white font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]"
                  : "border border-transparent text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-100"
              )}
            >
              <Settings className="h-3.5 w-3.5" />
              BYOK 设置
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-2">
          {mockMode === true && (
            <Badge variant="warning" className="gap-1">
              <Sparkles className="h-3 w-3" />
              离线 Mock 模式
            </Badge>
          )}
          {mockMode === false && (
            <Badge variant="success" className="gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              OpenAI-Compatible 已连接
            </Badge>
          )}
        </div>
      </div>
    </header>
  );
}
