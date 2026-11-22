"use client";

import { Coins, Cpu, DatabaseZap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { TelemetrySummary } from "@/lib/types";

export function CostTelemetryHud({ telemetry }: { telemetry: TelemetrySummary }) {
  const hitPct = Math.round(telemetry.cache_hit_rate * 1000) / 10;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-1.5">
            <DatabaseZap className="h-3.5 w-3.5 text-sky-400" />
            Prompt Cache 与费用透明面板
          </span>
          <span className="font-mono text-[10px] text-zinc-500">
            #{telemetry.static_prefix_sha256.slice(0, 8)}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-xs">
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-zinc-400">静态前缀缓存命中率</span>
            <span className="font-mono font-semibold text-emerald-300">{hitPct}%</span>
          </div>
          <Progress value={hitPct} />
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
            <div className="text-[10px] text-zinc-500">输入 Tokens</div>
            <div className="mt-0.5 font-mono text-zinc-200">
              {telemetry.total_prompt_tokens.toLocaleString()}
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
            <div className="text-[10px] text-zinc-500">缓存命中</div>
            <div className="mt-0.5 font-mono text-emerald-300">
              {telemetry.total_cached_tokens.toLocaleString()}
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
            <div className="text-[10px] text-zinc-500">输出 Tokens</div>
            <div className="mt-0.5 font-mono text-zinc-200">
              {telemetry.total_completion_tokens.toLocaleString()}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-zinc-800/80 bg-zinc-950/80 px-3 py-2">
          <span className="flex items-center gap-1.5 text-zinc-400">
            <Coins className="h-3.5 w-3.5 text-amber-400" />
            本场预估消耗
          </span>
          <span className="flex items-center gap-2 font-mono text-zinc-100">
            <span>¥{telemetry.estimated_cost_cny.toFixed(4)}</span>
            <span className="text-zinc-500">(${telemetry.estimated_cost_usd.toFixed(4)})</span>
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
          <Cpu className="h-3 w-3" />
          <span>静态前缀锁死于系统提示词头部（人设→工具→简历→JD/题纲→源码）</span>
        </div>
      </CardContent>
    </Card>
  );
}
