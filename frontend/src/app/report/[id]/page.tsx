"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowLeft,
  BookMarked,
  Download,
  Gauge,
  Loader2,
  MessageCircleWarning,
  Quote,
  RefreshCw,
  Timer,
} from "lucide-react";

import { AtomicChecklistCard } from "@/components/report/AtomicChecklistCard";
import { RewriteDiffPanel } from "@/components/report/RewriteDiffPanel";
import { TranscriptAnnotator } from "@/components/report/TranscriptAnnotator";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  evaluateSession,
  getReport,
  getReportExportUrl,
  getSession,
} from "@/lib/api";
import type {
  DimensionEvaluation,
  EvaluationReportResponse,
  SessionDetailResponse,
} from "@/lib/types";

const DIMENSION_META: {
  key: keyof EvaluationReportResponse["dimensions"];
  label: string;
}[] = [
  { key: "technical_depth", label: "技术原理深度" },
  { key: "engineering_tradeoffs", label: "工程权衡与边界意识" },
  { key: "problem_structuring", label: "问题拆解与表达结构" },
  { key: "code_and_testing", label: "代码细节与自测意识" },
];

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  const [session, setSession] = useState<SessionDetailResponse | null>(null);
  const [report, setReport] = useState<EvaluationReportResponse | null>(null);
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [reEvaluating, setReEvaluating] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErrorMsg("");
      try {
        const sess = await getSession(sessionId);
        if (cancelled) return;
        setSession(sess);
        try {
          const rep = await getReport(sessionId);
          if (!cancelled) setReport(rep);
        } catch {
          const rep = await evaluateSession(sessionId);
          if (!cancelled) setReport(rep);
        }
      } catch (err) {
        if (!cancelled) setErrorMsg(err instanceof Error ? err.message : "加载复盘失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleReEvaluate = async () => {
    setReEvaluating(true);
    setErrorMsg("");
    try {
      const rep = await evaluateSession(sessionId);
      setReport(rep);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "重新评分失败");
    } finally {
      setReEvaluating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[420px] items-center justify-center gap-2 text-sm text-zinc-400">
        <Loader2 className="h-4 w-4 animate-spin" />
        独立裁判正在生成证据锚定复盘报告...
      </div>
    );
  }

  if (errorMsg || !session || !report) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-300">
        {errorMsg || "复盘报告不存在"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回准备台
            </Link>
            <span className="text-zinc-600">/</span>
            <span className="text-xs text-zinc-400">{session.context_title}</span>
          </div>
          <h1 className="text-xl font-semibold text-zinc-100">证据锚定复盘台</h1>
          <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <span>裁判模型: `{report.judge_model}`</span>
            <span>·</span>
            <span>Pydantic 校验重试: {report.raw_retry_count} 次</span>
            <span>·</span>
            <span>
              缓存命中: {(session.telemetry.cache_hit_rate * 100).toFixed(1)}% · 花费 ¥
              {session.telemetry.estimated_cost_cny.toFixed(4)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-2 text-center">
            <div className="text-[10px] text-sky-300">综合得分</div>
            <div className="font-mono text-2xl font-bold text-sky-200">
              {report.overall_score !== null ? report.overall_score.toFixed(1) : "N/A"}
            </div>
          </div>

          <Button size="sm" variant="secondary" onClick={handleReEvaluate} disabled={reEvaluating}>
            <RefreshCw className={`h-3.5 w-3.5 ${reEvaluating ? "animate-spin" : ""}`} />
            重新评分
          </Button>
          <Link
            href="/mistakes"
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 text-xs font-medium text-amber-300 hover:bg-amber-500/20"
          >
            <BookMarked className="h-3.5 w-3.5" />
            错题本重录
          </Link>
          <Link
            href={`/observability?session=${sessionId}`}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900 px-3 text-xs font-medium text-zinc-200 hover:bg-zinc-800"
          >
            <Activity className="h-3.5 w-3.5" />
            可观测性
          </Link>
          <a
            href={getReportExportUrl(sessionId)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900 px-3 text-xs font-medium text-zinc-200 hover:bg-zinc-800"
          >
            <Download className="h-3.5 w-3.5" />
            导出 MD
          </a>
        </div>
      </div>

      {/* Deterministic Python Speech Metrics */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3 pt-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-500/15 text-sky-400">
              <Gauge className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs text-zinc-400">语速（纯确定性统计）</div>
              <div className="font-mono text-lg font-semibold text-zinc-100">
                {report.speech_metrics.chars_per_min} 字(词)/分
              </div>
              <div className="text-[11px] text-zinc-500">
                共 {report.speech_metrics.total_chars_and_words} 字词 ·{" "}
                {report.speech_metrics.total_speaking_duration_sec}s
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-3 pt-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15 text-amber-400">
              <Timer className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs text-zinc-400">最长冷场停顿秒数</div>
              <div className="font-mono text-lg font-semibold text-zinc-100">
                {report.speech_metrics.longest_silence_sec.toFixed(2)} s
              </div>
              <div className="text-[11px] text-zinc-500">基于停顿与词级时间间隔计算</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-3 pt-5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-rose-500/15 text-rose-400">
              <MessageCircleWarning className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-zinc-400">填充词频次</div>
              <div className="font-mono text-lg font-semibold text-zinc-100">
                {report.speech_metrics.total_filler_count} 次
              </div>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {report.speech_metrics.filler_breakdown.slice(0, 4).map((f) => (
                  <span
                    key={f.word}
                    className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-300"
                  >
                    {f.word}×{f.count}
                  </span>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 4 Orthogonal Dimensions (Evidence First -> Reasoning -> Nullable Score) */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {DIMENSION_META.map(({ key, label }) => {
          const dim: DimensionEvaluation = report.dimensions[key];
          return (
            <Card key={key}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-sm">{label}</CardTitle>
                  {dim.score === null ? (
                    <Badge variant="secondary">N/A (未充分考察)</Badge>
                  ) : (
                    <Badge
                      variant={
                        dim.score >= 75 ? "success" : dim.score >= 55 ? "warning" : "danger"
                      }
                      className="font-mono"
                    >
                      {dim.score} / 100
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs">
                {dim.evidence_quotes.length > 0 && (
                  <div className="space-y-1.5">
                    {dim.evidence_quotes.map((q, qi) => (
                      <div
                        key={qi}
                        className="rounded-lg border border-zinc-800 bg-zinc-950/80 p-2 text-[11px] text-zinc-300"
                      >
                        <div className="flex items-center gap-1 text-sky-400 font-mono text-[10px] mb-0.5">
                          <Quote className="h-3 w-3" />
                          Turn {q.turn_index} · {(q.timestamp_ms / 1000).toFixed(1)}s
                        </div>
                        <p className="italic">“{q.quote}”</p>
                        <div className="mt-1 text-zinc-500">→ {q.relevance}</div>
                      </div>
                    ))}
                  </div>
                )}
                <p className="text-zinc-300 leading-relaxed">{dim.reasoning}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Three-column Evidence-Anchored Diagnosis Desk */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <TranscriptAnnotator
          turns={session.turns}
          fillersByTurn={report.speech_metrics.detected_fillers_by_turn}
          selectedTurnIndex={selectedTurn}
          onSelectTurn={setSelectedTurn}
        />
        <RewriteDiffPanel
          annotations={report.transcript_annotations}
          selectedTurnIndex={selectedTurn}
        />
        <AtomicChecklistCard checklist={report.checklist_results} />
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">综合诊断建议</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap text-xs leading-relaxed text-zinc-300">
            {report.summary_markdown}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
