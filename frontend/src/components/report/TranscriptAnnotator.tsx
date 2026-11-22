"use client";

import { Clock, MessageSquare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TurnResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TranscriptAnnotatorProps {
  turns: TurnResponse[];
  fillersByTurn: Record<string, string[]>;
  selectedTurnIndex: number | null;
  onSelectTurn: (turnIndex: number) => void;
}

function formatMs(ms: number): string {
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function TranscriptAnnotator({
  turns,
  fillersByTurn,
  selectedTurnIndex,
  onSelectTurn,
}: TranscriptAnnotatorProps) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <MessageSquare className="h-4 w-4 text-sky-400" />
          左栏：逐字稿与填充词/停顿批注
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5 max-h-[640px] overflow-y-auto pr-2">
        {turns.map((t) => {
          const isUser = t.speaker === "user";
          const fillers = fillersByTurn[String(t.turn_index)] || [];
          const selected = selectedTurnIndex === t.turn_index;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => isUser && onSelectTurn(t.turn_index)}
              className={cn(
                "w-full text-left rounded-lg border p-3 text-xs transition-all",
                isUser ? "cursor-pointer" : "cursor-default opacity-85",
                selected
                  ? "border-sky-400 bg-sky-500/10"
                  : isUser
                  ? "border-zinc-800 bg-zinc-950/70 hover:border-zinc-700"
                  : "border-zinc-800/60 bg-zinc-900/40"
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-1.5 mb-1.5">
                <div className="flex items-center gap-1.5">
                  <Badge variant={isUser ? "default" : "secondary"} className="text-[10px]">
                    {isUser ? "候选人" : "面试官"} · Turn {t.turn_index}
                  </Badge>
                  <span className="font-mono text-[10px] text-zinc-400">L{t.ladder_level}</span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
                  <span className="flex items-center gap-0.5">
                    <Clock className="h-3 w-3" />
                    {formatMs(t.timestamp_start_ms)}
                  </span>
                  {isUser && t.pause_before_ms > 0 && (
                    <span
                      className={
                        t.pause_before_ms >= 3000 ? "text-amber-300" : "text-zinc-500"
                      }
                    >
                      停顿 {(t.pause_before_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
              </div>

              <p className="text-zinc-200 leading-relaxed whitespace-pre-wrap">{t.content}</p>

              {isUser && fillers.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  <span className="text-[10px] text-amber-400">填充词:</span>
                  {fillers.map((f, idx) => (
                    <span
                      key={idx}
                      className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300 border border-amber-500/30"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}

              {isUser && t.turn_eval?.score !== undefined && (
                <div className="mt-2 text-[10px] text-zinc-400">
                  状态机瞬时判定分:{" "}
                  <span className="font-mono text-zinc-200">
                    {Number(t.turn_eval.score).toFixed(2)}
                  </span>{" "}
                  ({t.turn_eval.action})
                </div>
              )}
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}
