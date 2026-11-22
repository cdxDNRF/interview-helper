"use client";

import { useEffect, useRef } from "react";
import type { FourStateIndicator } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATE_CONFIG: Record<
  FourStateIndicator,
  {
    label: string;
    dotClass: string;
    pillClass: string;
    strokeColor: string;
    subtext: string;
  }
> = {
  listening: {
    label: "倾听中",
    dotClass: "bg-emerald-400 shadow-[0_0_10px_#34d399]",
    pillClass: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    strokeColor: "#34d399",
    subtext: "你可以自然停顿，按住空格可暂缓提交",
  },
  thinking_pause: {
    label: "检测到思考停顿，继续等你",
    dotClass: "bg-amber-400 shadow-[0_0_10px_#fbbf24]",
    pillClass: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    strokeColor: "#fbbf24",
    subtext: "思考缓冲已激活，AI 不会抢话打断",
  },
  ai_thinking: {
    label: "AI 思考中",
    dotClass: "bg-violet-400 animate-pulse shadow-[0_0_10px_#a78bfa]",
    pillClass: "border-violet-500/40 bg-violet-500/10 text-violet-300",
    strokeColor: "#a78bfa",
    subtext: "慢环状态机正在判定深度阶梯并组织追问",
  },
  ai_speaking: {
    label: "AI 发言中",
    dotClass: "bg-sky-400 shadow-[0_0_10px_#38bdf8]",
    pillClass: "border-sky-500/40 bg-sky-500/10 text-sky-300",
    strokeColor: "#38bdf8",
    subtext: "面试官正在提问，可随时点击跳过播报直接作答",
  },
};

interface MinimalWaveformProps {
  indicator: FourStateIndicator;
  audioLevel?: number; // 0..1
  ttsProviderBadge?: string;
}

export function MinimalWaveform({
  indicator,
  audioLevel = 0,
  ttsProviderBadge,
}: MinimalWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const levelRef = useRef(audioLevel);
  const stateRef = useRef(indicator);

  useEffect(() => {
    levelRef.current = audioLevel;
  }, [audioLevel]);

  useEffect(() => {
    stateRef.current = indicator;
  }, [indicator]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let rafId = 0;
    let phase = 0;

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      const mid = h / 2;
      const currState = stateRef.current;
      const cfg = STATE_CONFIG[currState];

      ctx.clearRect(0, 0, w, h);

      // Subtle center baseline
      ctx.strokeStyle = "rgba(161, 161, 170, 0.16)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(w, mid);
      ctx.stroke();

      const amp =
        currState === "listening"
          ? Math.max(4, levelRef.current * 24)
          : currState === "ai_speaking"
          ? 16
          : currState === "ai_thinking"
          ? 9
          : 3;

      const freq = currState === "ai_speaking" ? 0.045 : currState === "ai_thinking" ? 0.06 : 0.03;
      const speed =
        currState === "ai_speaking" ? 0.14 : currState === "ai_thinking" ? 0.09 : 0.05;

      phase += speed;

      ctx.strokeStyle = cfg.strokeColor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let x = 0; x <= w; x += 3) {
        const env = Math.sin((x / w) * Math.PI);
        const y =
          mid +
          Math.sin(x * freq + phase) * amp * env +
          Math.sin(x * freq * 1.8 - phase * 0.7) * (amp * 0.35) * env;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      rafId = requestAnimationFrame(render);
    };

    rafId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(rafId);
  }, []);

  const cfg = STATE_CONFIG[indicator];

  return (
    <div className="rounded-2xl border border-white/[0.10] bg-white/[0.04] backdrop-blur-xl shadow-[0_12px_36px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.07)] px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          className={cn(
            "inline-flex items-center gap-2 rounded-full border backdrop-blur-md px-3 py-1 text-xs font-medium",
            cfg.pillClass
          )}
        >
          <span className={cn("h-2 w-2 rounded-full", cfg.dotClass)} />
          <span>{cfg.label}</span>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-zinc-400">
          {ttsProviderBadge && (
            <span className="rounded-lg border border-white/[0.10] bg-white/[0.05] px-2 py-0.5 font-mono text-[10px] text-zinc-200">
              语音: {ttsProviderBadge}
            </span>
          )}
          <span>{cfg.subtext}</span>
        </div>
      </div>

      <canvas
        ref={canvasRef}
        width={640}
        height={56}
        className="mt-2 h-12 w-full rounded-md"
      />
    </div>
  );
}
