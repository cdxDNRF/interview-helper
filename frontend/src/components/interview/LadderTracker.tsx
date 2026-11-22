"use client";

import { AlertTriangle, CheckCircle2, Circle, Code2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { InterviewStateSnapshot, PrepPlan } from "@/lib/types";
import { cn } from "@/lib/utils";

const LADDER_STEPS = [
  { level: 1, name: "L1 概念原理" },
  { level: 2, name: "L2 个人实战" },
  { level: 3, name: "L3 底层细节" },
  { level: 4, name: "L4 极端边界" },
] as const;

interface LadderTrackerProps {
  prepPlan: PrepPlan;
  state: InterviewStateSnapshot;
}

export function LadderTracker({ prepPlan, state }: LadderTrackerProps) {
  const activeTopic =
    prepPlan.topics[Math.min(state.current_topic_idx, Math.max(0, prepPlan.topics.length - 1))];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-sm">确定性四级追问阶梯</CardTitle>
            <Badge variant="default">
              L{state.ladder_level} · {LADDER_STEPS[state.ladder_level - 1]?.name}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-4 gap-1.5">
            {LADDER_STEPS.map((step) => {
              const active = state.ladder_level === step.level;
              const passed = state.ladder_level > step.level;
              return (
                <div
                  key={step.level}
                  className={cn(
                    "rounded-lg border px-2 py-2 text-center transition-all",
                    active
                      ? "border-sky-400 bg-sky-500/15 text-sky-200"
                      : passed
                      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                      : "border-zinc-800 bg-zinc-950/60 text-zinc-500"
                  )}
                >
                  <div className="text-[11px] font-semibold">L{step.level}</div>
                  <div className="mt-0.5 text-[10px] leading-tight">
                    {step.name.replace(/^L\d\s/, "")}
                  </div>
                </div>
              );
            })}
          </div>

          {activeTopic && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 text-xs space-y-1.5">
              <div className="font-medium text-zinc-100">{activeTopic.title}</div>
              {activeTopic.source_entrypoint && (
                <div className="flex items-center gap-1.5 font-mono text-[11px] text-sky-300">
                  <Code2 className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{activeTopic.source_entrypoint}</span>
                </div>
              )}
              <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-1">
                <span>连续未达标: {state.consecutive_fail_count}/2</span>
                {state.last_eval_score !== null && (
                  <span>上轮质量分: {state.last_eval_score.toFixed(2)}</span>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Prep 考点题纲（{prepPlan.topics.length} 题）</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {prepPlan.topics.map((topic, idx) => {
            const rec = state.topic_records?.[idx];
            const isCurr = idx === state.current_topic_idx && state.phase !== "completed";
            const status = rec?.status || "pending";
            return (
              <div
                key={topic.topic_id}
                className={cn(
                  "rounded-lg border p-2.5 text-xs transition-colors",
                  isCurr
                    ? "border-sky-500/50 bg-sky-500/10"
                    : "border-zinc-800/80 bg-zinc-950/40"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    {status === "mastered" ? (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                    ) : status === "failed_moved_on" ? (
                      <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />
                    ) : (
                      <Circle
                        className={cn(
                          "mt-0.5 h-3.5 w-3.5 shrink-0",
                          isCurr ? "text-sky-400" : "text-zinc-600"
                        )}
                      />
                    )}
                    <div>
                      <div className="font-medium text-zinc-200">
                        {idx + 1}. {topic.title}
                      </div>
                      {topic.source_entrypoint && (
                        <div className="mt-0.5 font-mono text-[10px] text-zinc-400">
                          {topic.source_entrypoint}
                        </div>
                      )}
                    </div>
                  </div>
                  {rec && (
                    <span className="shrink-0 font-mono text-[10px] text-zinc-400">
                      最高 L{rec.max_level_reached}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {prepPlan.resume_jd_gaps.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
              Prep 识别的简历-JD 差距点
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {prepPlan.resume_jd_gaps.map((gap, i) => (
              <div
                key={i}
                className="rounded-lg border border-zinc-800/80 bg-zinc-950/50 p-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-zinc-200">{gap.area}</span>
                  <Badge
                    variant={
                      gap.risk_level === "high"
                        ? "danger"
                        : gap.risk_level === "low"
                        ? "secondary"
                        : "warning"
                    }
                    className="text-[10px] px-1.5 py-0"
                  >
                    {gap.risk_level}
                  </Badge>
                </div>
                <p className="mt-1 text-[11px] text-zinc-400 leading-relaxed">
                  {gap.observation}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
