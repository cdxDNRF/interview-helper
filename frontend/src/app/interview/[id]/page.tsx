"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { CheckSquare, Loader2 } from "lucide-react";

import { CostTelemetryHud } from "@/components/interview/CostTelemetryHud";
import { LadderTracker } from "@/components/interview/LadderTracker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { MinimalWaveform } from "@/components/voice/MinimalWaveform";
import { ThinkingBufferControls } from "@/components/voice/ThinkingBufferControls";
import {
  evaluateSession,
  finishSession,
  getSession,
  getSettings,
  requestTTS,
  streamTurn,
  transcribeAudioBlob,
} from "@/lib/api";
import {
  getBrowserSpeechRecognitionCtor,
  speakWithWebSpeech,
  type SpeechRecognitionLike,
} from "@/lib/speech";
import type {
  FourStateIndicator,
  InteractionMode,
  InterviewStateSnapshot,
  SessionDetailResponse,
  TelemetrySummary,
  TurnResponse,
} from "@/lib/types";
import { cn } from "@/lib/utils";

export default function InterviewRoomPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sessionId = params.id;

  const [session, setSession] = useState<SessionDetailResponse | null>(null);
  const [turns, setTurns] = useState<TurnResponse[]>([]);
  const [state, setState] = useState<InterviewStateSnapshot | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetrySummary | null>(null);
  const [mode, setMode] = useState<InteractionMode>("voice");
  const [indicator, setIndicator] = useState<FourStateIndicator>("listening");
  const [ttsBadge, setTtsBadge] = useState<string>("edge-tts");
  const [sttProviderConfig, setSttProviderConfig] = useState<string>("web_speech");

  const [draft, setDraft] = useState("");
  const [streamingAiText, setStreamingAiText] = useState("");
  const [isHoldingSpace, setIsHoldingSpace] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const sessionStartRef = useRef<number>(0);
  const lastAiDoneRef = useRef<number>(0);
  const firstUserActivityRef = useRef<number | null>(null);
  const audioElemRef = useRef<HTMLAudioElement | null>(null);
  const cancelWebSpeechRef = useRef<(() => void) | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoSubmitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdingSpaceRef = useRef(false);
  const draftRef = useRef("");
  const feedEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  useEffect(() => {
    holdingSpaceRef.current = isHoldingSpace;
  }, [isHoldingSpace]);

  const stopAiPlayback = useCallback(() => {
    if (audioElemRef.current) {
      audioElemRef.current.pause();
      audioElemRef.current = null;
    }
    cancelWebSpeechRef.current?.();
    cancelWebSpeechRef.current = null;
    setIndicator((prev) => (prev === "ai_speaking" ? "listening" : prev));
    lastAiDoneRef.current = Date.now();
  }, []);

  const playAiVoice = useCallback(
    async (text: string, activeMode: InteractionMode) => {
      if (activeMode === "text" || !text.trim()) {
        setIndicator("listening");
        lastAiDoneRef.current = Date.now();
        return;
      }

      stopAiPlayback();
      setIndicator("ai_speaking");
      try {
        const res = await requestTTS(text);
        if (!res.fallback) {
          setTtsBadge(res.provider);
          const audio = new Audio(res.blobUrl);
          audioElemRef.current = audio;
          audio.onended = () => {
            URL.revokeObjectURL(res.blobUrl);
            audioElemRef.current = null;
            setIndicator("listening");
            lastAiDoneRef.current = Date.now();
          };
          audio.onerror = () => {
            URL.revokeObjectURL(res.blobUrl);
            setTtsBadge("Web Speech 兜底");
            cancelWebSpeechRef.current = speakWithWebSpeech(
              text,
              () => setIndicator("ai_speaking"),
              () => {
                setIndicator("listening");
                lastAiDoneRef.current = Date.now();
              }
            );
          };
          await audio.play();
          return;
        }

        setTtsBadge(res.provider === "none" ? "静默" : "Web Speech 兜底");
        if (res.provider === "none") {
          setIndicator("listening");
          lastAiDoneRef.current = Date.now();
          return;
        }
        cancelWebSpeechRef.current = speakWithWebSpeech(
          text,
          () => setIndicator("ai_speaking"),
          () => {
            setIndicator("listening");
            lastAiDoneRef.current = Date.now();
          }
        );
      } catch {
        setTtsBadge("Web Speech 兜底");
        cancelWebSpeechRef.current = speakWithWebSpeech(
          text,
          () => setIndicator("ai_speaking"),
          () => {
            setIndicator("listening");
            lastAiDoneRef.current = Date.now();
          }
        );
      }
    },
    [stopAiPlayback]
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSession(sessionId), getSettings()])
      .then(([sess, cfg]) => {
        if (cancelled) return;
        setSession(sess);
        setTurns(sess.turns);
        setState(sess.state);
        setTelemetry(sess.telemetry);
        setMode(sess.interaction_mode);
        setSttProviderConfig(cfg.voice.stt_provider);
        sessionStartRef.current = Date.now();
        lastAiDoneRef.current = Date.now();

        const lastTurn = sess.turns[sess.turns.length - 1];
        if (lastTurn && lastTurn.speaker === "ai" && sess.status === "in_progress") {
          playAiVoice(lastTurn.content, sess.interaction_mode);
        }
      })
      .catch((err) => {
        if (!cancelled) setErrorMsg(err instanceof Error ? err.message : "加载面试场次失败");
      });

    return () => {
      cancelled = true;
      stopAiPlayback();
    };
  }, [sessionId, playAiVoice, stopAiPlayback]);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, streamingAiText]);

  const clearVoiceTimers = () => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    if (autoSubmitTimerRef.current) clearTimeout(autoSubmitTimerRef.current);
  };

  const handleSubmitTurn = useCallback(
    async (explicitText?: string, sttUsed?: string) => {
      const text = (explicitText ?? draftRef.current).trim();
      if (!text || submitting || !session) return;

      clearVoiceTimers();
      stopAiPlayback();
      setSubmitting(true);
      setErrorMsg("");
      setIndicator("ai_thinking");

      const now = Date.now();
      const startAct = firstUserActivityRef.current ?? now;
      const pauseBeforeMs = Math.max(0, startAct - lastAiDoneRef.current);
      const relStart = Math.max(0, startAct - sessionStartRef.current);
      const relEnd = Math.max(relStart + 500, now - sessionStartRef.current);

      const optimisticUserTurn: TurnResponse = {
        id: -now,
        turn_index: turns.length,
        topic_index: state?.current_topic_idx ?? 0,
        ladder_level: state?.ladder_level ?? 1,
        speaker: "user",
        content: text,
        timestamp_start_ms: relStart,
        timestamp_end_ms: relEnd,
        pause_before_ms: pauseBeforeMs,
        turn_eval: null,
        tts_provider_used: null,
        stt_provider_used: sttUsed || (mode === "text" ? "text" : sttProviderConfig),
        created_at: new Date().toISOString(),
      };

      setTurns((prev) => [...prev, optimisticUserTurn]);
      setDraft("");
      firstUserActivityRef.current = null;
      setStreamingAiText("");

      let latestAiReply = "";

      try {
        await streamTurn(
          session.id,
          {
            content: text,
            timestamp_start_ms: relStart,
            timestamp_end_ms: relEnd,
            pause_before_ms: pauseBeforeMs,
            stt_provider_used: sttUsed || (mode === "text" ? "text" : sttProviderConfig),
          },
          {
            onState: (ev) => {
              setState(ev.state);
            },
            onDelta: (delta) => {
              latestAiReply += delta;
              setStreamingAiText(latestAiReply);
            },
            onDone: (ev) => {
              setStreamingAiText("");
              setTurns((prev) => [
                ...prev.filter((t) => t.id !== optimisticUserTurn.id),
                ev.user_turn,
                ev.ai_turn,
              ]);
              setState(ev.state);
              setTelemetry(ev.telemetry);
              setSession((prev) => (prev ? { ...prev, status: ev.session_status } : prev));
              playAiVoice(ev.ai_turn.content, mode);
            },
            onError: (msg) => {
              setErrorMsg(msg);
              setIndicator("listening");
            },
          }
        );
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : "提交回答失败");
        setIndicator("listening");
      } finally {
        setSubmitting(false);
      }
    },
    [mode, playAiVoice, session, state, stopAiPlayback, sttProviderConfig, submitting, turns.length]
  );

  // Hold Spacebar thinking buffer (when not typing inside textarea/input)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      const inEditable = tag === "TEXTAREA" || tag === "INPUT";
      if (e.code === "Space" && (!inEditable || e.altKey)) {
        e.preventDefault();
        if (!holdingSpaceRef.current) {
          setIsHoldingSpace(true);
          clearVoiceTimers();
          if (indicator === "listening") setIndicator("thinking_pause");
        }
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space" && holdingSpaceRef.current) {
        e.preventDefault();
        setIsHoldingSpace(false);
        setIndicator((prev) => (prev === "thinking_pause" ? "listening" : prev));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [indicator]);

  const stopMic = useCallback(() => {
    clearVoiceTimers();
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
    setIsRecording(false);
    setAudioLevel(0);
  }, []);

  useEffect(() => () => stopMic(), [stopMic]);

  const startMic = async () => {
    setErrorMsg("");
    stopAiPlayback();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      // Live RMS waveform meter
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        if (!mediaStreamRef.current) {
          audioCtx.close().catch(() => {});
          return;
        }
        analyser.getByteFrequencyData(buf);
        const avg = buf.reduce((a, b) => a + b, 0) / buf.length;
        setAudioLevel(Math.min(1, avg / 90));
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);

      const SpeechCtor = getBrowserSpeechRecognitionCtor();
      if (sttProviderConfig === "web_speech" && SpeechCtor) {
        const rec = new SpeechCtor();
        rec.lang = "zh-CN";
        rec.continuous = true;
        rec.interimResults = true;
        rec.onresult = (rawEv: unknown) => {
          const ev = rawEv as {
            results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
          };
          if (!firstUserActivityRef.current) firstUserActivityRef.current = Date.now();
          let combined = "";
          for (let i = 0; i < ev.results.length; i++) {
            combined += ev.results[i][0].transcript;
          }
          setDraft(combined);
          if (!holdingSpaceRef.current) setIndicator("listening");

          clearVoiceTimers();
          // Thinking-pause friendly silence window:
          // 1.5s silence -> switch indicator to "检测到思考停顿，继续等你"
          // 4.0s silence (if not holding space) -> submit automatically
          silenceTimerRef.current = setTimeout(() => {
            if (draftRef.current.trim()) {
              setIndicator("thinking_pause");
            }
          }, 1500);
          autoSubmitTimerRef.current = setTimeout(() => {
            if (!holdingSpaceRef.current && draftRef.current.trim()) {
              handleSubmitTurn(draftRef.current, "web_speech");
            }
          }, 4200);
        };
        rec.onerror = () => {
          setIsRecording(false);
        };
        rec.start();
        recognitionRef.current = rec;
        setIsRecording(true);
        setIndicator("listening");
        return;
      }

      // OpenAI-compatible MediaRecorder upload fallback when stt_provider === "openai_stt" or no Web Speech
      const chunks: BlobPart[] = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };
      recorder.onstop = async () => {
        if (chunks.length === 0) return;
        const blob = new Blob(chunks, { type: "audio/webm" });
        try {
          const res = await transcribeAudioBlob(blob, sessionId);
          if (res.text) {
            setDraft((prev) => (prev ? `${prev} ${res.text}` : res.text));
          }
        } catch (err) {
          setErrorMsg(err instanceof Error ? err.message : "录音转写失败");
        }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setIndicator("listening");
    } catch {
      setErrorMsg("未检测到麦克风权限或设备，已可直接使用下方「纯文本调试」模式作答。");
    }
  };

  const toggleMic = () => {
    if (isRecording) stopMic();
    else startMic();
  };

  const handleFinishAndEvaluate = async () => {
    if (!session || finishing) return;
    stopMic();
    stopAiPlayback();
    setFinishing(true);
    setErrorMsg("");
    try {
      await finishSession(session.id);
      await evaluateSession(session.id);
      router.push(`/report/${session.id}`);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "生成复盘报告失败");
      setFinishing(false);
    }
  };

  if (!session || !state || !telemetry) {
    return (
      <div className="flex min-h-[400px] items-center justify-center text-sm text-zinc-400">
        {errorMsg ? (
          <span className="text-rose-400">{errorMsg}</span>
        ) : (
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载面试房中...
          </span>
        )}
      </div>
    );
  }

  const isCompleted = session.status === "completed" || session.status === "evaluated";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="text-base font-semibold text-zinc-100">{session.context_title}</h1>
          <Badge variant={session.interviewer_style === "pressure" ? "danger" : "success"}>
            {session.interviewer_style === "pressure" ? "大厂高压拷打" : "温和引导"}
          </Badge>
          {isCompleted && <Badge variant="purple">本场已结束</Badge>}
        </div>

        <div className="flex items-center gap-2">
          {session.has_report && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => router.push(`/report/${session.id}`)}
            >
              查看复盘报告
            </Button>
          )}
          <Button
            size="sm"
            variant={isCompleted ? "default" : "destructive"}
            onClick={handleFinishAndEvaluate}
            disabled={finishing}
          >
            {finishing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                独立裁判评分中...
              </>
            ) : (
              <>
                <CheckSquare className="h-3.5 w-3.5" />
                {isCompleted ? "生成/查看复盘台" : "结束面试并生成复盘"}
              </>
            )}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="lg:col-span-8 space-y-4">
          <MinimalWaveform
            indicator={indicator}
            audioLevel={audioLevel}
            ttsProviderBadge={ttsBadge}
          />

          <Card className="p-4">
            <div className="space-y-3 max-h-[420px] overflow-y-auto pr-2">
              {turns.map((t) => {
                const isAi = t.speaker === "ai";
                return (
                  <div
                    key={t.id}
                    className={cn(
                      "flex flex-col gap-1 rounded-xl border p-3.5 text-sm",
                      isAi
                        ? "border-zinc-800 bg-zinc-950/80 mr-8"
                        : "border-sky-500/30 bg-sky-500/10 ml-8"
                    )}
                  >
                    <div className="flex items-center justify-between text-[11px] text-zinc-400">
                      <span className="font-medium text-zinc-200">
                        {isAi ? "AI 面试官" : "候选人"}
                      </span>
                      <span className="font-mono">
                        Turn {t.turn_index} · L{t.ladder_level}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap leading-relaxed text-zinc-100">
                      {t.content}
                    </p>
                  </div>
                );
              })}

              {streamingAiText && (
                <div className="flex flex-col gap-1 rounded-xl border border-violet-500/40 bg-violet-500/10 p-3.5 text-sm mr-8">
                  <div className="text-[11px] font-medium text-violet-300">
                    AI 面试官（生成中...）
                  </div>
                  <p className="whitespace-pre-wrap leading-relaxed text-zinc-100">
                    {streamingAiText}
                  </p>
                </div>
              )}
              <div ref={feedEndRef} />
            </div>
          </Card>

          <ThinkingBufferControls
            mode={mode}
            onModeChange={(next) => {
              setMode(next);
              if (next === "text") {
                stopMic();
                stopAiPlayback();
              }
            }}
            indicator={indicator}
            isHoldingSpace={isHoldingSpace}
            onHoldStart={() => {
              setIsHoldingSpace(true);
              clearVoiceTimers();
              setIndicator("thinking_pause");
            }}
            onHoldEnd={() => {
              setIsHoldingSpace(false);
              setIndicator("listening");
            }}
            isRecording={isRecording}
            onToggleMic={toggleMic}
            onManualSubmit={() => handleSubmitTurn()}
            onSkipAiSpeech={stopAiPlayback}
            canSubmit={draft.trim().length > 0}
            disabled={isCompleted || submitting}
          />

          <div className="space-y-1.5">
            <Textarea
              rows={3}
              disabled={isCompleted || submitting}
              placeholder={
                isCompleted
                  ? "本场面试已结束，请点击右上角生成或查看复盘台。"
                  : mode === "voice"
                  ? "说话内容将实时转写到此，也可直接打字补充；按住「暂缓提交」可防止停顿被抢话（Ctrl+Enter 发送）"
                  : "纯文本调试模式：直接输入你的技术回答，按 Ctrl+Enter 或点击「结束发言并提交」..."
              }
              value={draft}
              onChange={(e) => {
                if (!firstUserActivityRef.current) firstUserActivityRef.current = Date.now();
                setDraft(e.target.value);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  handleSubmitTurn();
                }
              }}
            />
            {errorMsg && (
              <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                {errorMsg}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-4 space-y-4">
          <LadderTracker prepPlan={session.prep_plan} state={state} />
          <CostTelemetryHud telemetry={telemetry} />
        </div>
      </div>
    </div>
  );
}
