"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Coins,
  Cpu,
  DatabaseZap,
  Gauge,
  Loader2,
  ShieldAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getObservabilityOverview, getSessionObservability } from "@/lib/api";
import type {
  ObservabilityOverviewResponse,
  SessionObservabilityResponse,
} from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ObservabilityPage() {
  const searchParams = useSearchParams();
  const initialSessionId = searchParams.get("session") || "";

  const [overview, setOverview] = useState<ObservabilityOverviewResponse | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string>(initialSessionId);
  const [sessionObs, setSessionObs] = useState<SessionObservabilityResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getObservabilityOverview()
      .then((data) => {
        if (cancelled) return;
        setOverview(data);
        if (!selectedSessionId && data.session_trends.length > 0) {
          setSelectedSessionId(
            data.session_trends[data.session_trends.length - 1].session_id
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) return;
    let cancelled = false;
    getSessionObservability(selectedSessionId)
      .then((data) => {
        if (!cancelled) setSessionObs(data);
      })
      .catch(() => {
        if (!cancelled) setSessionObs(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSessionId]);

  if (loading) {
    return (
      <div className="flex min-h-[360px] items-center justify-center text-sm text-zinc-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        加载工程可观测性指标中...
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="rounded-xl border border-zinc-800 p-6 text-sm text-zinc-400">
        暂无可观测性日志数据。
      </div>
    );
  }

  const hitRatePct = (overview.avg_cache_hit_rate * 100).toFixed(1);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold text-zinc-100">
          <Activity className="h-5 w-5 text-sky-400" />
          工程可观测性与 Prompt Cache 审计台
        </h1>
        <p className="mt-1 text-xs text-zinc-400">
          基于 SQLite `llm_usage_logs` 真实落盘数据，监控各阶段响应时延（Avg / P95）、静态前缀缓存命中率、SHA-256 零漂移校验及单场精细花费。
        </p>
      </div>

      {/* Top KPI Grid */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Card>
          <CardContent className="pt-5">
            <div className="flex items-center gap-1.5 text-xs text-zinc-400">
              <Cpu className="h-3.5 w-3.5 text-sky-400" />
              累计场次 / 调用
            </div>
            <div className="mt-1 font-mono text-xl font-bold text-zinc-100">
              {overview.total_sessions} 场 / {overview.total_llm_calls} 次
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5">
            <div className="flex items-center gap-1.5 text-xs text-zinc-400">
              <DatabaseZap className="h-3.5 w-3.5 text-emerald-400" />
              全站平均 Cache 命中率
            </div>
            <div className="mt-1 font-mono text-xl font-bold text-emerald-300">
              {hitRatePct}%
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5">
            <div className="flex items-center gap-1.5 text-xs text-zinc-400">
              <Gauge className="h-3.5 w-3.5 text-violet-400" />
              平均 LLM 时延
            </div>
            <div className="mt-1 font-mono text-xl font-bold text-zinc-100">
              {overview.avg_latency_ms} ms
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5">
            <div className="flex items-center gap-1.5 text-xs text-zinc-400">
              <Coins className="h-3.5 w-3.5 text-amber-400" />
              累计估算消耗
            </div>
            <div className="mt-1 font-mono text-xl font-bold text-amber-300">
              ¥{overview.total_cost_cny.toFixed(4)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5">
            <div className="text-xs text-zinc-400">单场均摊花费</div>
            <div className="mt-1 font-mono text-xl font-bold text-zinc-100">
              ¥
              {overview.total_sessions > 0
                ? (overview.total_cost_cny / overview.total_sessions).toFixed(4)
                : "0.0000"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Stage Breakdown + Session Cache Trend */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">四阶段耗时与成本分布（Prep / Live Eval / Live Reply / Judge）</CardTitle>
          </CardHeader>
          <CardContent>
            {overview.stage_breakdown.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-500">
                暂无真实模型调用记录（离线 Mock 模式不产生外部计费日志）。
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-400">
                      <th className="py-2 pr-3">阶段</th>
                      <th className="py-2 pr-3">次数</th>
                      <th className="py-2 pr-3">输入 / 命中</th>
                      <th className="py-2 pr-3">输出</th>
                      <th className="py-2 pr-3">Avg / P95 延迟</th>
                      <th className="py-2">花费 (CNY)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 font-mono">
                    {overview.stage_breakdown.map((s) => (
                      <tr key={s.stage}>
                        <td className="py-2 pr-3 font-sans font-medium text-zinc-200">
                          {s.stage}
                        </td>
                        <td className="py-2 pr-3 text-zinc-300">{s.call_count}</td>
                        <td className="py-2 pr-3 text-zinc-300">
                          {s.prompt_tokens.toLocaleString()} /{" "}
                          <span className="text-emerald-300">
                            {s.cached_tokens.toLocaleString()}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-zinc-300">
                          {s.completion_tokens.toLocaleString()}
                        </td>
                        <td className="py-2 pr-3 text-zinc-300">
                          {s.avg_latency_ms}ms / {s.p95_latency_ms}ms
                        </td>
                        <td className="py-2 text-amber-300">
                          ¥{s.estimated_cost_cny.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">各场次 Cache 命中率趋势（点击切换下钻审计）</CardTitle>
            <CardDescription>目标基准：静态前缀锁定后命中率应稳居 ≥ 70%</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[280px] overflow-y-auto">
            {overview.session_trends.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-500">暂无场次数据</div>
            ) : (
              overview.session_trends.map((t) => {
                const pct = Math.round(t.cache_hit_rate * 1000) / 10;
                const active = selectedSessionId === t.session_id;
                return (
                  <button
                    key={t.session_id}
                    type="button"
                    onClick={() => setSelectedSessionId(t.session_id)}
                    className={cn(
                      "w-full rounded-lg border p-2.5 text-left text-xs transition-colors cursor-pointer",
                      active
                        ? "border-sky-400 bg-sky-500/10"
                        : "border-zinc-800 bg-zinc-950/60 hover:border-zinc-700"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="font-medium text-zinc-200 truncate">
                        {t.context_title}
                      </span>
                      <span className="font-mono text-emerald-300 shrink-0">
                        {pct}% · ¥{t.estimated_cost_cny.toFixed(4)}
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className="h-full bg-emerald-400 transition-all"
                        style={{ width: `${Math.min(100, pct)}%` }}
                      />
                    </div>
                  </button>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>

      {/* Selected Session Call Audit */}
      {sessionObs && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-sm">
                  单场调用级审计：{sessionObs.context_title}
                </CardTitle>
                <CardDescription className="mt-1 font-mono text-[11px]">
                  static_prefix_sha256: {sessionObs.static_prefix_sha256 || "(未记录)"}
                </CardDescription>
              </div>
              <Badge
                variant={sessionObs.prefix_consistent ? "success" : "danger"}
                className="gap-1"
              >
                {sessionObs.prefix_consistent ? (
                  <>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    静态前缀 SHA-256 全程零漂移
                  </>
                ) : (
                  <>
                    <ShieldAlert className="h-3.5 w-3.5" />
                    检测到前缀哈希变化
                  </>
                )}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {sessionObs.logs.length === 0 ? (
              <div className="py-6 text-center text-xs text-zinc-500">
                该场次在离线 Mock 模式下运行，未调用外部模型。
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-400">
                      <th className="py-2 pr-3">#</th>
                      <th className="py-2 pr-3">阶段</th>
                      <th className="py-2 pr-3">模型</th>
                      <th className="py-2 pr-3">Prompt</th>
                      <th className="py-2 pr-3">Cached</th>
                      <th className="py-2 pr-3">命中率</th>
                      <th className="py-2 pr-3">耗时</th>
                      <th className="py-2">费用</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 font-mono">
                    {sessionObs.logs.map((log, i) => (
                      <tr key={log.id}>
                        <td className="py-2 pr-3 text-zinc-500">{i + 1}</td>
                        <td className="py-2 pr-3 font-sans text-zinc-200">{log.stage}</td>
                        <td className="py-2 pr-3 text-zinc-300">{log.model_name}</td>
                        <td className="py-2 pr-3 text-zinc-300">{log.prompt_tokens}</td>
                        <td className="py-2 pr-3 text-emerald-300">{log.cached_tokens}</td>
                        <td className="py-2 pr-3 text-emerald-300">
                          {(log.cache_hit_rate * 100).toFixed(1)}%
                        </td>
                        <td className="py-2 pr-3 text-zinc-300">{log.latency_ms}ms</td>
                        <td className="py-2 text-amber-300">
                          ¥{log.estimated_cost_cny.toFixed(5)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
