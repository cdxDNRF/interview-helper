"use client";

import { Hand, Mic, MicOff, Send, VolumeX } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FourStateIndicator, InteractionMode } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ThinkingBufferControlsProps {
  mode: InteractionMode;
  onModeChange: (next: InteractionMode) => void;
  indicator: FourStateIndicator;
  isHoldingSpace: boolean;
  onHoldStart: () => void;
  onHoldEnd: () => void;
  isRecording: boolean;
  onToggleMic: () => void;
  onManualSubmit: () => void;
  onSkipAiSpeech: () => void;
  canSubmit: boolean;
  disabled: boolean;
}

export function ThinkingBufferControls({
  mode,
  onModeChange,
  indicator,
  isHoldingSpace,
  onHoldStart,
  onHoldEnd,
  isRecording,
  onToggleMic,
  onManualSubmit,
  onSkipAiSpeech,
  canSubmit,
  disabled,
}: ThinkingBufferControlsProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-white/[0.09] bg-white/[0.04] backdrop-blur-xl shadow-[0_8px_28px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)] px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex rounded-xl border border-white/[0.09] bg-white/[0.03] p-0.5">
          <button
            type="button"
            onClick={() => onModeChange("voice")}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer",
              mode === "voice"
                ? "bg-sky-500/20 text-sky-300"
                : "text-zinc-400 hover:text-zinc-200"
            )}
          >
            语音双模
          </button>
          <button
            type="button"
            onClick={() => onModeChange("text")}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer",
              mode === "text"
                ? "bg-sky-500/20 text-sky-300"
                : "text-zinc-400 hover:text-zinc-200"
            )}
          >
            纯文本调试
          </button>
        </div>

        {mode === "voice" && (
          <Button
            type="button"
            size="sm"
            variant={isRecording ? "default" : "secondary"}
            onClick={onToggleMic}
            disabled={disabled || indicator === "ai_thinking"}
          >
            {isRecording ? (
              <>
                <Mic className="h-3.5 w-3.5" />
                麦克风收音中
              </>
            ) : (
              <>
                <MicOff className="h-3.5 w-3.5" />
                开启麦克风
              </>
            )}
          </Button>
        )}

        <button
          type="button"
          onMouseDown={onHoldStart}
          onMouseUp={onHoldEnd}
          onMouseLeave={() => isHoldingSpace && onHoldEnd()}
          onTouchStart={onHoldStart}
          onTouchEnd={onHoldEnd}
          disabled={disabled}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-all select-none cursor-pointer",
            isHoldingSpace
              ? "border-amber-400/70 bg-amber-400/20 text-amber-100 shadow-[0_0_20px_rgba(251,191,36,0.2)]"
              : "border-white/[0.11] bg-white/[0.05] text-zinc-200 hover:bg-white/[0.1]"
          )}
          title="在非输入框焦点时按住 Space，或按住此按钮暂缓提交"
        >
          <Hand className="h-3.5 w-3.5" />
          {isHoldingSpace ? "思考缓冲中（松开恢复）" : "按住空格暂缓提交"}
        </button>
      </div>

      <div className="flex items-center gap-2">
        {indicator === "ai_speaking" && (
          <Button type="button" size="sm" variant="outline" onClick={onSkipAiSpeech}>
            <VolumeX className="h-3.5 w-3.5" />
            跳过播报
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          onClick={onManualSubmit}
          disabled={disabled || !canSubmit || indicator === "ai_thinking"}
        >
          <Send className="h-3.5 w-3.5" />
          结束发言并提交
        </Button>
      </div>
    </div>
  );
}
