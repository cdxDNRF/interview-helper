export type InterviewerStyle = "gentle" | "pressure";
export type InteractionMode = "voice" | "text";
export type FourStateIndicator =
  | "listening"
  | "thinking_pause"
  | "ai_thinking"
  | "ai_speaking";

export interface MaskedStageLLMSettings {
  base_url: string;
  api_key_masked: string;
  has_api_key: boolean;
  model: string;
  temperature: number;
  max_tokens: number;
}

export interface VoiceSettings {
  tts_provider: "edge_tts" | "web_speech" | "kokoro" | "openai_tts" | "none";
  edge_tts_voice: string;
  edge_tts_rate: string;
  stt_provider: "web_speech" | "openai_stt" | "text_only";
  stt_base_url: string;
  stt_api_key: string;
  stt_model: string;
}

export interface SettingsReadResponse {
  mock_mode: boolean;
  prep_llm: MaskedStageLLMSettings;
  live_llm: MaskedStageLLMSettings;
  judge_llm: MaskedStageLLMSettings;
  voice: VoiceSettings;
  pricing: Record<
    string,
    {
      input_per_1m_cny: number;
      cached_input_per_1m_cny: number;
      output_per_1m_cny: number;
    }
  >;
}

export interface ContextResponse {
  id: string;
  title: string;
  resume_filename: string;
  resume_markdown: string;
  job_description: string;
  github_repo_url: string | null;
  repo_digest_markdown: string | null;
  repo_token_count: number;
  repo_warnings: string[];
  created_at: string;
}

export interface GapPoint {
  area: string;
  observation: string;
  risk_level: string;
}

export interface PrepTopic {
  topic_id: string;
  title: string;
  source_entrypoint: string;
  target_dimensions: string[];
  atomic_checklist: string[];
  l1_seed_question: string;
}

export interface PrepPlan {
  candidate_summary: string;
  resume_jd_gaps: GapPoint[];
  topics: PrepTopic[];
  hotwords: string[];
}

export interface TopicRecord {
  topic_id: string;
  title: string;
  status: "pending" | "in_progress" | "mastered" | "failed_moved_on";
  max_level_reached: number;
  turns_spent: number;
}

export interface InterviewStateSnapshot {
  current_topic_idx: number;
  ladder_level: 1 | 2 | 3 | 4;
  consecutive_fail_count: number;
  turns_on_current_topic: number;
  phase: "opening" | "questioning" | "closing" | "completed";
  topic_records: TopicRecord[];
  last_eval_score: number | null;
  last_eval_action: string;
}

export interface TurnResponse {
  id: number;
  turn_index: number;
  topic_index: number;
  ladder_level: number;
  speaker: "ai" | "user" | "system";
  content: string;
  timestamp_start_ms: number;
  timestamp_end_ms: number;
  pause_before_ms: number;
  turn_eval: {
    score?: number;
    action?: string;
    brief_diagnosis?: string;
    is_rote_memorization?: boolean;
    is_off_topic?: boolean;
  } | null;
  tts_provider_used: string | null;
  stt_provider_used: string | null;
  created_at: string;
}

export interface TelemetrySummary {
  total_prompt_tokens: number;
  total_cached_tokens: number;
  total_completion_tokens: number;
  cache_hit_rate: number;
  estimated_cost_cny: number;
  estimated_cost_usd: number;
  static_prefix_sha256: string;
}

export interface SessionDetailResponse {
  id: string;
  context_id: string;
  context_title: string;
  interviewer_style: InterviewerStyle;
  interaction_mode: InteractionMode;
  status: string;
  prep_plan: PrepPlan;
  state: InterviewStateSnapshot;
  telemetry: TelemetrySummary;
  turns: TurnResponse[];
  has_report: boolean;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface SessionListItem {
  id: string;
  context_id: string;
  context_title: string;
  interviewer_style: InterviewerStyle;
  interaction_mode: InteractionMode;
  status: string;
  total_turns: number;
  cache_hit_rate: number;
  estimated_cost_cny: number;
  overall_score: number | null;
  created_at: string;
}

export interface EvidenceQuote {
  quote: string;
  turn_index: number;
  timestamp_ms: number;
  relevance: string;
}

export interface DimensionEvaluation {
  evidence_quotes: EvidenceQuote[];
  reasoning: string;
  score: number | null;
}

export interface EvaluationReportResponse {
  id: string;
  session_id: string;
  judge_model: string;
  overall_score: number | null;
  dimensions: {
    technical_depth: DimensionEvaluation;
    engineering_tradeoffs: DimensionEvaluation;
    problem_structuring: DimensionEvaluation;
    code_and_testing: DimensionEvaluation;
  };
  checklist_results: {
    topic_title: string;
    criterion: string;
    status: "passed" | "missed" | "not_tested";
    evidence_quote: string;
    turn_index: number | null;
  }[];
  transcript_annotations: {
    turn_index: number;
    topic_title: string;
    ladder_level: number;
    critique: string;
    original_utterance: string;
    ideal_rewrite: string;
  }[];
  speech_metrics: {
    total_user_turns: number;
    total_chars_and_words: number;
    total_speaking_duration_sec: number;
    chars_per_min: number;
    longest_silence_sec: number;
    total_filler_count: number;
    filler_breakdown: { word: string; count: number }[];
    detected_fillers_by_turn: Record<string, string[]>;
    estimation_note: string;
  };
  summary_markdown: string;
  raw_retry_count: number;
  created_at: string;
}
