"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookMarked,
  CheckCircle2,
  Flame,
  Loader2,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listMistakes } from "@/lib/api";
import type { MistakeItemResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function MistakesPage() {
  const [filter, setFilter] = useState<"all" | "open" | "mastered">("all");
  const [items, setItems] = useState<MistakeItemResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const statusParam = filter === "all" ? undefined : filter;
    listMistakes(statusParam)
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  const openCount = items.filter((i) => i.status === "open").length;
  const masteredCount = items.filter((i) => i.status === "mastered").length;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-zinc-100">
            <BookMarked className="h-5 w-5 text-amber-400" />
            错题本与 2 分钟单题重录训练营
          </h1>
          <p className="mt-1 text-xs text-zinc-400">
            低分考点（&lt;70 分或连续两轮追问未达标）自动沉淀于此。点击任意题目可发起 2 分钟单题重录，对比前后得分跃迁。
          </p>
        </div>

        <div className="inline-flex rounded-lg border border-zinc-800 bg-zinc-900 p-1 text-xs">
          {(
            [
              ["all", "全部"],
              ["open", "待攻克"],
              ["mastered", "已掌握"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                setLoading(true);
                setFilter(key);
              }}
              className={cn(
                "rounded-md px-3 py-1.5 font-medium transition-colors cursor-pointer",
                filter === key
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-5">
            <div className="text-xs text-zinc-400">当前筛选错题数</div>
            <div className="mt-1 font-mono text-2xl font-bold text-zinc-100">
              {items.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <div className="text-xs text-zinc-400">待攻克考点</div>
            <div className="mt-1 font-mono text-2xl font-bold text-amber-300">
              {openCount}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5">
            <div className="text-xs text-zinc-400">重录后已掌握（≥75 分）</div>
            <div className="mt-1 font-mono text-2xl font-bold text-emerald-300">
              {masteredCount}
            </div>
          </CardContent>
        </Card>
      </div>

      {loading ? (
        <div className="flex min-h-[240px] items-center justify-center text-sm text-zinc-400">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          加载错题本中...
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-xs text-zinc-400 space-y-3">
            <p>当前筛选下暂无错题记录。完成一场模拟面试并生成复盘报告后，低分考点会自动收入此处。</p>
            <Link href="/">
              <Button size="sm" variant="secondary">
                前往准备台开启模拟面试
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {items.map((item) => (
            <Card key={item.id} className="flex flex-col justify-between">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="text-[11px] text-zinc-500">
                      {item.context_title || "模拟面试"} · 切入点 {item.source_entrypoint}
                    </div>
                    <CardTitle className="text-base leading-snug">
                      {item.topic_title}
                    </CardTitle>
                  </div>
                  <Badge
                    variant={item.status === "mastered" ? "success" : "warning"}
                    className="shrink-0 gap-1"
                  >
                    {item.status === "mastered" ? (
                      <>
                        <CheckCircle2 className="h-3 w-3" />
                        已掌握
                      </>
                    ) : (
                      <>
                        <Flame className="h-3 w-3" />
                        待攻克
                      </>
                    )}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="space-y-3 text-xs">
                <p className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-2.5 text-zinc-300 line-clamp-2">
                  原提问：{item.question_prompt}
                </p>

                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-3 py-2">
                  <div className="flex items-center gap-3 font-mono">
                    <span className="text-rose-300">
                      原得分 {item.original_score.toFixed(1)}
                    </span>
                    <span className="text-zinc-600">→</span>
                    <span className="text-sky-300">
                      最佳重录{" "}
                      {item.best_retry_score !== null
                        ? item.best_retry_score.toFixed(1)
                        : "未挑战"}
                    </span>
                    {item.score_delta !== null && (
                      <Badge
                        variant={item.score_delta >= 0 ? "success" : "danger"}
                        className="gap-0.5 text-[10px]"
                      >
                        <TrendingUp className="h-3 w-3" />
                        {item.score_delta >= 0 ? "+" : ""}
                        {item.score_delta.toFixed(1)}
                      </Badge>
                    )}
                  </div>
                  <span className="text-[11px] text-zinc-500">
                    挑战 {item.retry_count} 次
                  </span>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <Link
                    href={`/report/${item.session_id}`}
                    className="text-zinc-400 hover:text-zinc-200 hover:underline"
                  >
                    查看原场复盘
                  </Link>
                  <Link href={`/mistakes/${item.id}`}>
                    <Button size="sm">
                      2 分钟重录挑战
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
