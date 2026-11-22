import type {
  CodeSnapshotPayload,
  ContextResponse,
  EvaluationReportResponse,
  InterviewStateSnapshot,
  MistakeItemResponse,
  ObservabilityOverviewResponse,
  PresetsCatalogResponse,
  SessionDetailResponse,
  SessionListItem,
  SessionObservabilityResponse,
  SettingsReadResponse,
  TelemetrySummary,
  TurnResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, init);
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const data = await resp.json();
      msg = data.detail || data.message || msg;
    } catch {
      msg = (await resp.text()) || msg;
    }
    throw new Error(msg);
  }
  return resp.json() as Promise<T>;
}

export async function getSettings(): Promise<SettingsReadResponse> {
  return apiJson("/api/settings");
}

export async function updateSettings(payload: unknown): Promise<SettingsReadResponse> {
  return apiJson("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchRemoteModels(base_url: string, api_key: string): Promise<string[]> {
  const data = await apiJson<{ models: string[] }>("/api/settings/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base_url, api_key }),
  });
  return data.models;
}

export async function testModelConnection(payload: {
  base_url: string;
  api_key: string;
  model: string;
  stage: "prep" | "live" | "judge";
}): Promise<{ ok: boolean; latency_ms: number; model: string; reply_preview: string; error: string }> {
  return apiJson("/api/settings/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getPresets(): Promise<PresetsCatalogResponse> {
  return apiJson("/api/presets");
}

export async function createContext(formData: FormData): Promise<ContextResponse> {
  return apiJson("/api/contexts", {
    method: "POST",
    body: formData,
  });
}

export async function createSession(payload: {
  context_id: string;
  interviewer_style: "gentle" | "pressure";
  interaction_mode: "voice" | "text";
}): Promise<SessionDetailResponse> {
  return apiJson("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listSessions(): Promise<SessionListItem[]> {
  return apiJson("/api/sessions");
}

export async function getSession(sessionId: string): Promise<SessionDetailResponse> {
  return apiJson(`/api/sessions/${sessionId}`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiJson(`/api/sessions/${sessionId}`, { method: "DELETE" });
}

export async function finishSession(sessionId: string): Promise<SessionDetailResponse> {
  return apiJson(`/api/sessions/${sessionId}/finish`, { method: "POST" });
}

export async function evaluateSession(sessionId: string): Promise<EvaluationReportResponse> {
  return apiJson(`/api/sessions/${sessionId}/evaluate`, { method: "POST" });
}

export async function getReport(sessionId: string): Promise<EvaluationReportResponse> {
  return apiJson(`/api/sessions/${sessionId}/report`);
}

export function getReportExportUrl(sessionId: string): string {
  return `${API_BASE}/api/sessions/${sessionId}/report/export`;
}

export async function transcribeAudioBlob(
  blob: Blob,
  sessionId: string
): Promise<{ text: string; provider_used: string; word_timestamps: unknown[]; duration_ms: number }> {
  const form = new FormData();
  form.append("audio", blob, "answer.webm");
  form.append("session_id", sessionId);
  return apiJson("/api/voice/stt", { method: "POST", body: form });
}

export type TTSClientResult =
  | { fallback: false; blobUrl: string; provider: string }
  | { fallback: true; provider: string; reason: string };

export async function requestTTS(text: string): Promise<TTSClientResult> {
  const resp = await fetch(`${API_BASE}/api/voice/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!resp.ok) {
    return {
      fallback: true,
      provider: "web_speech_fallback",
      reason: `TTS HTTP ${resp.status}`,
    };
  }

  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = (await resp.json()) as { fallback: boolean; provider: string; reason: string };
    return {
      fallback: true,
      provider: data.provider || "web_speech_fallback",
      reason: data.reason || "自动降级为浏览器 Web Speech",
    };
  }

  const blob = await resp.blob();
  if (blob.size === 0) {
    return {
      fallback: true,
      provider: "web_speech_fallback",
      reason: "收到 0 字节音频，降级为浏览器 Web Speech",
    };
  }
  return {
    fallback: false,
    blobUrl: URL.createObjectURL(blob),
    provider: resp.headers.get("X-TTS-Provider") || "edge_tts",
  };
}

export interface StreamTurnHandlers {
  onState: (payload: {
    eval_result: Record<string, unknown>;
    eval_action: string;
    state: InterviewStateSnapshot;
    static_prefix_sha256: string;
  }) => void;
  onDelta: (text: string) => void;
  onDone: (payload: {
    ai_turn: TurnResponse;
    user_turn: TurnResponse;
    state: InterviewStateSnapshot;
    session_status: string;
    telemetry: TelemetrySummary;
  }) => void;
  onError: (message: string) => void;
}

export async function streamTurn(
  sessionId: string,
  payload: {
    content: string;
    timestamp_start_ms: number;
    timestamp_end_ms: number;
    pause_before_ms: number;
    word_timestamps?: unknown[];
    stt_provider_used: string;
    code_snapshot?: CodeSnapshotPayload | null;
  },
  handlers: StreamTurnHandlers
): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/sessions/${sessionId}/turns/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok || !resp.body) {
    const errText = await resp.text();
    throw new Error(errText || `流式请求失败 (HTTP ${resp.status})`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      if (!block.trim()) continue;
      let eventType = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim());
        }
      }
      if (!dataLines.length) continue;
      const parsed = JSON.parse(dataLines.join("\n"));
      if (eventType === "state") handlers.onState(parsed);
      else if (eventType === "delta") handlers.onDelta(parsed.text || "");
      else if (eventType === "done") handlers.onDone(parsed);
      else if (eventType === "error") handlers.onError(parsed.message || "流式处理异常");
    }
  }
}

export async function listMistakes(status?: "open" | "mastered"): Promise<MistakeItemResponse[]> {
  const qs = status ? `?status=${status}` : "";
  return apiJson(`/api/mistakes${qs}`);
}

export async function getMistake(mistakeId: string): Promise<MistakeItemResponse> {
  return apiJson(`/api/mistakes/${mistakeId}`);
}

export async function retryMistake(
  mistakeId: string,
  payload: { retry_answer: string; duration_sec: number }
): Promise<MistakeItemResponse> {
  return apiJson(`/api/mistakes/${mistakeId}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getObservabilityOverview(): Promise<ObservabilityOverviewResponse> {
  return apiJson("/api/observability/overview");
}

export async function getSessionObservability(
  sessionId: string
): Promise<SessionObservabilityResponse> {
  return apiJson(`/api/observability/sessions/${sessionId}`);
}

