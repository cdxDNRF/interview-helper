"use client";

import { CheckCircle2, HelpCircle, ListChecks, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EvaluationReportResponse } from "@/lib/types";

export function AtomicChecklistCard({
  checklist,
}: {
  checklist: EvaluationReportResponse["checklist_results"];
}) {
  const passedCount = checklist.filter((c) => c.status === "passed").length;
  const testedCount = checklist.filter((c) => c.status !== "not_tested").length;

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <ListChecks className="h-4 w-4 text-violet-400" />
            右栏：原子核查清单达标状态
          </CardTitle>
          <Badge variant="secondary" className="text-[10px]">
            {passedCount}/{testedCount || checklist.length} 达标
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2.5 max-h-[640px] overflow-y-auto pr-2">
        {checklist.map((item, idx) => (
          <div
            key={idx}
            className="rounded-lg border border-zinc-800/90 bg-zinc-950/60 p-3 text-xs space-y-1.5"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2">
                {item.status === "passed" ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                ) : item.status === "missed" ? (
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
                ) : (
                  <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
                )}
                <div>
                  <div className="text-[10px] text-zinc-500">{item.topic_title}</div>
                  <div className="font-medium text-zinc-200 mt-0.5">{item.criterion}</div>
                </div>
              </div>
              <Badge
                variant={
                  item.status === "passed"
                    ? "success"
                    : item.status === "missed"
                    ? "danger"
                    : "secondary"
                }
                className="shrink-0 text-[10px]"
              >
                {item.status === "passed"
                  ? "达标"
                  : item.status === "missed"
                  ? "未达标"
                  : "N/A 未考到"}
              </Badge>
            </div>
            {item.evidence_quote && (
              <div className="pl-6 text-[11px] text-zinc-400 italic">
                证据引用 [Turn {item.turn_index ?? "?"}]: “{item.evidence_quote}”
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
