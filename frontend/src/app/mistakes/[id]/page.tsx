"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  Mic,
  MicOff,
  Play,
  Send,
  Timer,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { getMistake, retryMistake } from "@/lib/api";
import {
  getBrowserSpeechRecognitionCtor,
  type SpeechRecognitionLike,
} from "@/lib/speech";
import type { MistakeItemResponse } from "@/lib/types";

const DRILL_SECONDS = 120;

export default function MistakeDrillPage() {
  const params = useParams<{ id: string }>();
  const mistakeId = params.id;

  const [item, setItem] = useState<MistakeItemResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  const [secondsLeft, setSecondsLeft] = useState(DRILL_SECONDS);
  const [timerRunning, setTimerRunning] = useState(false);
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showReference, setShowReference] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMistake(mistakeId)
      .then((data) => {
        if (!cancelled) setItem(data);
      })
      .catch((err) => {
        if (!cancelled) setErrorMsg(err instanceof Error ? err.message : "加载错题失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mistakeId]);

  useEffect(() => {
    if (!timerRunning) return;
    const id = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          setTimerRunning(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [timerRunning]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  const toggleVoice = () => {
    if (isRecording) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setIsRecording(false);
      return;
    }
    const Ctor = getBrowserSpeechRecognitionCtor();
    if (!Ctor) {
      setErrorMsg("当前浏览器不支持原生 SpeechRecognition，请直接输入文本作答。");
      return;
    }
    if (!timerRunning) setTimerRunning(true);
    const rec = new Ctor();
    rec.lang = "zh-CN";
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (rawEv: unknown) => {
      const ev = rawEv as {
        results: ArrayLike<{ 0: { transcript: string } }>;
      };
      let text = "";
      for (let i = 0; i < ev.results.length; i++) {
        text += ev.results[i][0].transcript;
      }
      setAnswer(text);
    };
    rec.onerror = () => setIsRecording(false);
    rec.start();
    recognitionRef.current = rec;
    setIsRecording(true);
  };

  const handleSubmit = async () => {
    if (!item || !answer.trim() || submitting) return;
    recognitionRef.current?.stop();
    setIsRecording(false);
    setTimerRunning(false);
    setSubmitting(true);
    setErrorMsg("");
    try {
      const elapsed = Math.max(1, DRILL_SECONDS - secondsLeft);
      const updated = await retryMistake(item.id, {
        retry_answer: answer.trim(),
        duration_sec: elapsed,
      });
      setItem(updated);
      setShowReference(true);
      setAnswer("");
      setSecondsLeft(DRILL_SECONDS);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "提交重录评分失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[320px] items-center justify-center text-sm text-zinc-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        加载单题重录台...
      </div>
    );
  }

  if (!item) {
    return (
      <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-300">
        {errorMsg || "错题记录不存在"}
      </div>
    );
  }

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, "0");
  const ss = String(secondsLeft % 60).padStart(2, "0");
  const latestRetry =
    item.retries.length > 0 ? item.retries[item.retries.length - 1] : null;

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/70 p-4">
        <div className="space-y-1">
          <Link
            href="/mistakes"
            className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            返回错题本
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-semibold text-zinc-100">{item.topic_title}</h1>
            <Badge variant={item.status === "mastered" ? "success" : "warning"}>
              {item.status === "mastered" ? "已掌握 (≥75分)" : "待攻克"}
            </Badge>
          </div>
          <div className="text-xs text-zinc-400">
            源码/项目切入点：<span className="font-mono text-sky-300">{item.source_entrypoint}</span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 font-mono text-lg font-bold text-amber-300">
            <Timer className="h-4 w-4" />
            {mm}:{ss}
          </div>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => {
              if (!timerRunning) {
                if (secondsLeft === 0) setSecondsLeft(DRILL_SECONDS);
                setTimerRunning(true);
              } else {
                setTimerRunning(false);
              }
            }}
          >
            <Play className="h-3.5 w-3.5" />
            {timerRunning ? "暂停计时" : "开始 2 分钟计时"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="lg:col-span-7 space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">面试官原提问</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 text-zinc-100 leading-relaxed">
                {item.question_prompt}
              </p>

              <div className="space-y-1.5 text-xs">
                <div className="font-medium text-zinc-300">本轮必须命中的原子核查点：</div>
                {item.atomic_checklist.map((c, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 rounded border border-zinc-800/70 bg-zinc-950/40 px-2.5 py-1.5 text-zinc-300"
                  >
                    <span className="font-mono text-[10px] text-sky-400">#{idx + 1}</span>
                    <span>{c}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">2 分钟重录作答区</CardTitle>
                <Button type="button" size="sm" variant="outline" onClick={toggleVoice}>
                  {isRecording ? (
                    <>
                      <Mic className="h-3.5 w-3.5 text-emerald-400" />
                      语音录入中（点击停止）
                    </>
                  ) : (
                    <>
                      <MicOff className="h-3.5 w-3.5" />
                      语音转写重录
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                rows={5}
                placeholder="脱稿重新作答：给出原理机制 + 具体代码/并发锁粒度 + 量化延迟指标 + 极端故障降级策略..."
                value={answer}
                onChange={(e) => {
                  if (!timerRunning) setTimerRunning(true);
                  setAnswer(e.target.value);
                }}
              />
              {errorMsg && (
                <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                  {errorMsg}
                </div>
              )}
              <div className="flex items-center justify-between">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => setShowReference((v) => !v)}
                >
                  {showReference ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  {showReference ? "隐藏原话与满分参考" : "偷看历史原话与满分参考"}
                </Button>
                <Button onClick={handleSubmit} disabled={!answer.trim() || submitting}>
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      对比评判中...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" />
                      提交重录并对比跃迁
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-5 space-y-4">
          <Card className="border-sky-500/30">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
                重录前后得分跃迁对比
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5">
                  <div className="text-[10px] text-rose-300">原回答得分</div>
                  <div className="mt-1 font-mono text-xl font-bold text-rose-200">
                    {item.original_score.toFixed(1)}
                  </div>
                </div>
                <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-2.5">
                  <div className="text-[10px] text-sky-300">最佳重录得分</div>
                  <div className="mt-1 font-mono text-xl font-bold text-sky-200">
                    {item.best_retry_score !== null
                      ? item.best_retry_score.toFixed(1)
                      : "--"}
                  </div>
                </div>
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2.5">
                  <div className="text-[10px] text-emerald-300">得分跃迁</div>
                  <div className="mt-1 font-mono text-xl font-bold text-emerald-200">
                    {item.score_delta !== null
                      ? `${item.score_delta >= 0 ? "+" : ""}${item.score_delta.toFixed(1)}`
                      : "--"}
                  </div>
                </div>
              </div>

              {latestRetry && (
                <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-zinc-200">最新一次挑战反馈</span>
                    <span className="font-mono text-sky-300">
                      {latestRetry.retry_score.toFixed(1)} 分 · {latestRetry.duration_sec}s
                    </span>
                  </div>
                  <p className="text-zinc-300 leading-relaxed">{latestRetry.feedback}</p>
                  {latestRetry.newly_passed_checklist.length > 0 && (
                    <div className="space-y-1 pt-1">
                      <div className="text-[10px] text-emerald-400">新达标核查项：</div>
                      {latestRetry.newly_passed_checklist.map((c, ci) => (
                        <div key={ci} className="flex items-center gap-1.5 text-[11px] text-emerald-200">
                          <CheckCircle2 className="h-3 w-3 shrink-0" />
                          <span>{c}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {showReference && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">历史原话 vs 满分重构参考</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs">
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-2.5">
                  <div className="text-[10px] font-semibold text-rose-300 mb-1">
                    − 当时原回答
                  </div>
                  <p className="text-zinc-300 whitespace-pre-wrap">{item.original_answer}</p>
                </div>
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-2.5">
                  <div className="text-[10px] font-semibold text-emerald-300 mb-1">
                    + 满分重构版参考
                  </div>
                  <p className="text-zinc-100 whitespace-pre-wrap">{item.ideal_rewrite}</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
