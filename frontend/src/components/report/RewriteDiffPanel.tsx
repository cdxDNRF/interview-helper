"use client";

import { GitCompareArrows } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EvaluationReportResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface RewriteDiffPanelProps {
  annotations: EvaluationReportResponse["transcript_annotations"];
  selectedTurnIndex: number | null;
}

export function RewriteDiffPanel({
  annotations,
  selectedTurnIndex,
}: RewriteDiffPanelProps) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <GitCompareArrows className="h-4 w-4 text-emerald-400" />
          中栏：原话 vs 满分重构版对比
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 max-h-[640px] overflow-y-auto pr-2">
        {annotations.length === 0 ? (
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4 text-xs text-zinc-400">
            本场暂无可对比的作答重构批注。
          </div>
        ) : (
          annotations.map((ann, idx) => {
            const highlighted = selectedTurnIndex === ann.turn_index;
            return (
              <div
                key={idx}
                className={cn(
                  "rounded-xl border p-3.5 text-xs space-y-2.5 transition-all",
                  highlighted
                    ? "border-sky-400 bg-sky-500/10"
                    : "border-zinc-800 bg-zinc-950/70"
                )}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-medium text-zinc-100">
                    Turn {ann.turn_index} · {ann.topic_title}
                  </div>
                  <Badge variant="secondary" className="text-[10px]">
                    L{ann.ladder_level}
                  </Badge>
                </div>

                <div className="rounded-md bg-zinc-900/90 px-2.5 py-2 text-zinc-300 border border-zinc-800">
                  <span className="text-sky-300 font-medium">批注：</span>
                  {ann.critique}
                </div>

                <div className="space-y-2">
                  <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-2.5">
                    <div className="text-[10px] font-semibold text-rose-300 mb-1">
                      − 你的原话
                    </div>
                    <p className="text-zinc-300 leading-relaxed whitespace-pre-wrap">
                      {ann.original_utterance}
                    </p>
                  </div>

                  <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-2.5">
                    <div className="text-[10px] font-semibold text-emerald-300 mb-1">
                      + 对标目标职级满分重构版
                    </div>
                    <p className="text-zinc-100 leading-relaxed whitespace-pre-wrap">
                      {ann.ideal_rewrite}
                    </p>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
