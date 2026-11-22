"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, Save, Sparkles, Wifi, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  fetchRemoteModels,
  getSettings,
  testModelConnection,
  updateSettings,
} from "@/lib/api";
import type { SettingsReadResponse, VoiceSettings } from "@/lib/types";

interface StageFormState {
  base_url: string;
  api_key: string;
  api_key_masked: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

const STAGE_LABELS = [
  { key: "prep_llm" as const, stage: "prep" as const, title: "1. Prep 预规划模型", desc: "开场前一次性生成差距点与 4-5 个核心考点" },
  { key: "live_llm" as const, stage: "live" as const, title: "2. Live 面试对话模型", desc: "慢环打分与静态前缀流式追问（建议低延迟/高缓存模型）" },
  { key: "judge_llm" as const, stage: "judge" as const, title: "3. Judge 赛后裁判模型", desc: "独立生成证据锚定 JSON 与满分重构对比" },
];

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [mockMode, setMockMode] = useState(false);
  const [stages, setStages] = useState<{
    prep_llm: StageFormState;
    live_llm: StageFormState;
    judge_llm: StageFormState;
  } | null>(null);
  const [voice, setVoice] = useState<VoiceSettings | null>(null);

  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [testResults, setTestResults] = useState<
    Record<string, { ok: boolean; msg: string } | undefined>
  >({});
  const [saveFeedback, setSaveFeedback] = useState("");

  useEffect(() => {
    getSettings()
      .then((s: SettingsReadResponse) => {
        setMockMode(s.mock_mode);
        setStages({
          prep_llm: {
            base_url: s.prep_llm.base_url,
            api_key: "",
            api_key_masked: s.prep_llm.api_key_masked,
            model: s.prep_llm.model,
            temperature: s.prep_llm.temperature,
            max_tokens: s.prep_llm.max_tokens,
          },
          live_llm: {
            base_url: s.live_llm.base_url,
            api_key: "",
            api_key_masked: s.live_llm.api_key_masked,
            model: s.live_llm.model,
            temperature: s.live_llm.temperature,
            max_tokens: s.live_llm.max_tokens,
          },
          judge_llm: {
            base_url: s.judge_llm.base_url,
            api_key: "",
            api_key_masked: s.judge_llm.api_key_masked,
            model: s.judge_llm.model,
            temperature: s.judge_llm.temperature,
            max_tokens: s.judge_llm.max_tokens,
          },
        });
        setVoice(s.voice);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleFetchModels = async (baseUrl: string, apiKey: string) => {
    setFetchingModels(true);
    setSaveFeedback("");
    try {
      const models = await fetchRemoteModels(baseUrl, apiKey);
      setAvailableModels(models);
      setSaveFeedback(`成功拉取 ${models.length} 个可用模型。`);
    } catch (err) {
      setSaveFeedback(err instanceof Error ? err.message : "拉取模型失败");
    } finally {
      setFetchingModels(false);
    }
  };

  const handleTest = async (
    key: "prep_llm" | "live_llm" | "judge_llm",
    stage: "prep" | "live" | "judge"
  ) => {
    if (!stages) return;
    const cfg = stages[key];
    setTestResults((prev) => ({ ...prev, [key]: { ok: true, msg: "测速中..." } }));
    const res = await testModelConnection({
      base_url: cfg.base_url,
      api_key: cfg.api_key,
      model: cfg.model,
      stage,
    });
    setTestResults((prev) => ({
      ...prev,
      [key]: {
        ok: res.ok,
        msg: res.ok
          ? `连接成功 (${res.latency_ms}ms): ${res.reply_preview}`
          : `失败 (${res.latency_ms}ms): ${res.error}`,
      },
    }));
  };

  const handleSave = async () => {
    if (!stages || !voice) return;
    setSaving(true);
    setSaveFeedback("");
    try {
      const updated = await updateSettings({
        mock_mode: mockMode,
        prep_llm: {
          base_url: stages.prep_llm.base_url,
          api_key: stages.prep_llm.api_key || null,
          model: stages.prep_llm.model,
          temperature: stages.prep_llm.temperature,
          max_tokens: stages.prep_llm.max_tokens,
        },
        live_llm: {
          base_url: stages.live_llm.base_url,
          api_key: stages.live_llm.api_key || null,
          model: stages.live_llm.model,
          temperature: stages.live_llm.temperature,
          max_tokens: stages.live_llm.max_tokens,
        },
        judge_llm: {
          base_url: stages.judge_llm.base_url,
          api_key: stages.judge_llm.api_key || null,
          model: stages.judge_llm.model,
          temperature: stages.judge_llm.temperature,
          max_tokens: stages.judge_llm.max_tokens,
        },
        voice,
      });
      setStages({
        prep_llm: { ...stages.prep_llm, api_key: "", api_key_masked: updated.prep_llm.api_key_masked },
        live_llm: { ...stages.live_llm, api_key: "", api_key_masked: updated.live_llm.api_key_masked },
        judge_llm: { ...stages.judge_llm, api_key: "", api_key_masked: updated.judge_llm.api_key_masked },
      });
      window.dispatchEvent(new Event("interview-helper-settings-updated"));
      setSaveFeedback("配置已保存至本地 SQLite。");
    } catch (err) {
      setSaveFeedback(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading || !stages || !voice) {
    return (
      <div className="flex min-h-[300px] items-center justify-center text-sm text-zinc-400">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        加载设置中...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">BYOK 多阶段模型与轻量语音设置</h1>
          <p className="mt-1 text-xs text-zinc-400">
            密钥仅保存在本机 SQLite（或 .env），支持 OpenAI-compatible 本地/远程中转接口，以及零密钥离线 Mock 模式。
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          保存全部配置
        </Button>
      </div>

      {saveFeedback && (
        <div className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-4 py-2.5 text-xs text-sky-200">
          {saveFeedback}
        </div>
      )}

      <Card>
        <CardContent className="flex items-center justify-between pt-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
              <Sparkles className="h-4 w-4 text-amber-400" />
              零 API Key 离线 Mock 演示模式
            </div>
            <p className="text-xs text-zinc-400">
              开启后无需任何模型余额或网络连接，即可完整跑通 Prep 题纲、四级追问状态机、TTS 兜底与证据复盘台。
            </p>
          </div>
          <Switch checked={mockMode} onCheckedChange={setMockMode} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4">
        {STAGE_LABELS.map(({ key, stage, title, desc }) => {
          const item = stages[key];
          const tr = testResults[key];
          return (
            <Card key={key}>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="text-sm">{title}</CardTitle>
                    <CardDescription className="mt-1">{desc}</CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => handleFetchModels(item.base_url, item.api_key)}
                      disabled={fetchingModels}
                    >
                      <RefreshCw
                        className={`h-3.5 w-3.5 ${fetchingModels ? "animate-spin" : ""}`}
                      />
                      拉取 /v1/models
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => handleTest(key, stage)}
                    >
                      <Wifi className="h-3.5 w-3.5" />
                      测试连通性
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="space-y-1">
                    <label className="text-[11px] text-zinc-400">Base URL</label>
                    <Input
                      value={item.base_url}
                      onChange={(e) =>
                        setStages((prev) =>
                          prev ? { ...prev, [key]: { ...prev[key], base_url: e.target.value } } : prev
                        )
                      }
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] text-zinc-400">
                      API Key（留空保留原值 {item.api_key_masked ? `· 当前: ${item.api_key_masked}` : ""}）
                    </label>
                    <Input
                      type="password"
                      placeholder={item.api_key_masked || "输入新 API Key"}
                      value={item.api_key}
                      onChange={(e) =>
                        setStages((prev) =>
                          prev ? { ...prev, [key]: { ...prev[key], api_key: e.target.value } } : prev
                        )
                      }
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] text-zinc-400">Model 名称</label>
                    <Input
                      list={`models-${key}`}
                      value={item.model}
                      onChange={(e) =>
                        setStages((prev) =>
                          prev ? { ...prev, [key]: { ...prev[key], model: e.target.value } } : prev
                        )
                      }
                    />
                    {availableModels.length > 0 && (
                      <datalist id={`models-${key}`}>
                        {availableModels.map((m) => (
                          <option key={m} value={m} />
                        ))}
                      </datalist>
                    )}
                  </div>
                </div>

                {tr && (
                  <div
                    className={`flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs ${
                      tr.ok
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border-rose-500/40 bg-rose-500/10 text-rose-300"
                    }`}
                  >
                    {tr.ok ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <span className="truncate">{tr.msg}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm">可插拔 TTS / STT 语音配置</CardTitle>
              <CardDescription className="mt-1">
                P0 默认 edge-tts（含 0 字节自动检测与 Web Speech 兜底）；已预留 Kokoro-82M 与 LiveKit WebRTC + Smart Turn v3.2 接口。
              </CardDescription>
            </div>
            <Badge variant="secondary">可扩展插件架构</Badge>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2 text-xs">
          <div className="space-y-2">
            <label className="text-zinc-400">TTS 引擎</label>
            <select
              value={voice.tts_provider}
              onChange={(e) =>
                setVoice({
                  ...voice,
                  tts_provider: e.target.value as VoiceSettings["tts_provider"],
                })
              }
              className="flex h-10 w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-100"
            >
              <option value="edge_tts">edge-tts (&gt;=7.3.1, 失败自动降级 Web Speech)</option>
              <option value="web_speech">纯浏览器 Web Speech (speechSynthesis)</option>
              <option value="kokoro">Kokoro-82M（P1 预留扩展位）</option>
              <option value="openai_tts">OpenAI / 商业 TTS（预留扩展位）</option>
              <option value="none">静默模式（不朗读）</option>
            </select>
            <Input
              value={voice.edge_tts_voice}
              onChange={(e) => setVoice({ ...voice, edge_tts_voice: e.target.value })}
              placeholder="Edge 音色，如 zh-CN-XiaoxiaoNeural"
            />
          </div>

          <div className="space-y-2">
            <label className="text-zinc-400">STT 识别引擎</label>
            <select
              value={voice.stt_provider}
              onChange={(e) =>
                setVoice({
                  ...voice,
                  stt_provider: e.target.value as VoiceSettings["stt_provider"],
                })
              }
              className="flex h-10 w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-100"
            >
              <option value="web_speech">浏览器原生 SpeechRecognition（零成本）</option>
              <option value="openai_stt">OpenAI 兼容 /audio/transcriptions（带热词注入）</option>
              <option value="text_only">纯文本模式</option>
            </select>
            <Input
              value={voice.stt_base_url}
              onChange={(e) => setVoice({ ...voice, stt_base_url: e.target.value })}
              placeholder="STT Base URL"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
