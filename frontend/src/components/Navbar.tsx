"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AudioWaveform, Settings, Sparkles } from "lucide-react";

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
    <header className="sticky top-0 z-40 border-b border-zinc-800/80 bg-zinc-950/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5 text-zinc-100 hover:opacity-90">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/15 text-sky-400 border border-sky-500/30">
              <AudioWaveform className="h-4 w-4" />
            </span>
            <span className="font-semibold tracking-tight text-sm sm:text-base">
              interview-helper
            </span>
            <Badge variant="secondary" className="hidden sm:inline-flex text-[11px]">
              P0 · Dual-Loop
            </Badge>
          </Link>

          <nav className="flex items-center gap-1">
            <Link
              href="/"
              className={cn(
                "rounded-md px-3 py-1.5 text-xs sm:text-sm transition-colors",
                pathname === "/"
                  ? "bg-zinc-800 text-zinc-100 font-medium"
                  : "text-zinc-400 hover:text-zinc-100"
              )}
            >
              准备台 & 历史
            </Link>
            <Link
              href="/settings"
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs sm:text-sm transition-colors",
                pathname === "/settings"
                  ? "bg-zinc-800 text-zinc-100 font-medium"
                  : "text-zinc-400 hover:text-zinc-100"
              )}
            >
              <Settings className="h-3.5 w-3.5" />
              BYOK & 语音设置
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
