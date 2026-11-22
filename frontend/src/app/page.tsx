"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Code2,
  Cpu,
  FileCode2,
  FileText,
  Flame,
  GitBranch,
  History,
  Layers,
  Loader2,
  MessageSquareQuote,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { createContext, createSession, deleteSession, getPresets, listSessions } from "@/lib/api";
import type {
  GeneralPackPreset,
  InteractionMode,
  InterviewerStyle,
  InterviewType,
  KnowledgePackPreset,
  RoleTrackPreset,
  SessionListItem,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const SAMPLE_RESUME = `# 张三 · 高级 Python/TypeScript 后端工程师（4年经验）

## 核心技能
- 语言与框架：Python 3.12 (FastAPI, asyncio, LangGraph)、TypeScript (Next.js, Node.js)
- 数据与中间件：SQLite WAL、PostgreSQL、Redis Pub/Sub、WebSocket、SSE

## 代表项目：实时协同任务网关
- 在 \`ws_manager.py\` 中设计异步连接管理与心跳超时清理，支撑单节点 3,000+ 并发连接。
- 通过静态前缀缓存优化 LLM 多轮推理，命中率稳定在 82% 以上，P99 延迟控制在 45ms 内。
- 编写基于 pytest-asyncio 的状态机与降级熔断自动化测试。`;

const SAMPLE_JD = `高级后端与 AI Agent 研发工程师
岗位要求：
1. 精通 Python 异步编程（FastAPI / asyncio）及状态机编排（LangGraph）；
2. 具备高并发连接管理、背压控制、持久化一致性（SQLite WAL / Redis）与极端故障排查能力；
3. 熟悉 LLM Prompt Caching 工程优化与结构化输出可靠性保障。`;

const INTERVIEW_MODE_CARDS: {
  id: InterviewType;
  label: string;
  badge: string;
  desc: string;
  icon: typeof FileCode2;
}[] = [
  {
    id: "project_deep_dive",
    label: "项目 & 源码深挖",
    badge: "传简历 + GitHub",
    desc: "基于简历与 Repomix 源码做 L1-L4 工程深挖",
    icon: FileCode2,
  },
  {
    id: "general_behavioral",
    label: "通用综合面 · STAR",
    badge: "免简历直进",
    desc: "行为面、冲突沟通、故障复盘担当与反问",
    icon: MessageSquareQuote,
  },
  {
    id: "cs_role_track",
    label: "计算机职业专项",
    badge: "8 大岗位赛道",
    desc: "按后端/前端/Agent/算法/架构/SRE 等一键开考",
    icon: Cpu,
  },
  {
    id: "bagu_fundamentals",
    label: "重要八股突击",
    badge: "7 大专题多选",
    desc: "计算机网络、OS、MySQL、Redis、并发、大模型",
    icon: Layers,
  },
];

const HISTORY_MODE_BADGE: Record<InterviewType, { label: string; variant: "default" | "purple" | "warning" | "secondary" }> = {
  project_deep_dive: { label: "项目深挖", variant: "secondary" },
  general_behavioral: { label: "通用 STAR", variant: "purple" },
  cs_role_track: { label: "职业专项", variant: "default" },
  bagu_fundamentals: { label: "核心八股", variant: "warning" },
};

export default function HomePage() {
  const router = useRouter();
  const [interviewType, setInterviewType] = useState<InterviewType>("cs_role_track");
  const [roles, setRoles] = useState<RoleTrackPreset[]>([]);
  const [fundamentals, setFundamentals] = useState<KnowledgePackPreset[]>([]);
  const [generalPacks, setGeneralPacks] = useState<GeneralPackPreset[]>([]);
  const [presetsLoading, setPresetsLoading] = useState(true);

  const [selectedRoleId, setSelectedRoleId] = useState<string>("backend_engineer");
  const [selectedBaguIds, setSelectedBaguIds] = useState<string[]>([
    "network",
    "mysql",
    "redis_mq",
  ]);
  const [selectedGeneralIds, setSelectedGeneralIds] = useState<string[]>([
    "general_behavioral",
  ]);
  const [showOptionalContext, setShowOptionalContext] = useState(false);

  const [title, setTitle] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [style, setStyle] = useState<InterviewerStyle>("pressure");
  const [mode, setMode] = useState<InteractionMode>("voice");

  const [submitting, setSubmitting] = useState(false);
  const [stageHint, setStageHint] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const refreshHistory = async () => {
    setLoadingHistory(true);
    try {
      const data = await listSessions();
      setSessions(data);
    } catch {
      // Backend might still be starting
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    getPresets()
      .then((catalog) => {
        if (cancelled) return;
        setRoles(catalog.roles || []);
        setFundamentals(catalog.fundamentals || []);
        setGeneralPacks(catalog.general_packs || []);
        if (catalog.roles?.length && !catalog.roles.some((r) => r.id === "backend_engineer")) {
          setSelectedRoleId(catalog.roles[0].id);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setPresetsLoading(false);
      });

    listSessions()
      .then((data) => {
        if (!cancelled) setSessions(data);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const roleNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const r of roles) map[r.id] = r.name;
    return map;
  }, [roles]);

  const activeRole = useMemo(
    () => roles.find((r) => r.id === selectedRoleId) || null,
    [roles, selectedRoleId]
  );

  const togglePackId = (list: string[], setList: (next: string[]) => void, packId: string) => {
    if (list.includes(packId)) {
      if (list.length <= 1) return; // keep at least 1 active pack
      setList(list.filter((id) => id !== packId));
    } else {
      setList([...list, packId]);
    }
  };

  const fillDemoData = () => {
    setInterviewType("project_deep_dive");
    setTitle("高级 AI Agent 后端模拟");
    setResumeText(SAMPLE_RESUME);
    setJobDescription(SAMPLE_JD);
    setGithubUrl("");
    setErrorMsg("");
  };

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (interviewType === "project_deep_dive") {
      if (!resumeFile && !resumeText.trim()) {
        setErrorMsg("项目深挖模式下，请先上传 PDF/Markdown 简历或粘贴简历内容（也可切换上方免简历模式）。");
        return;
      }
      if (!jobDescription.trim()) {
        setErrorMsg("项目深挖模式下，请填写目标岗位 JD。");
        return;
      }
    } else if (interviewType === "cs_role_track" && !selectedRoleId) {
      setErrorMsg("请选择一个计算机职业专项赛道。");
      return;
    } else if (interviewType === "bagu_fundamentals" && selectedBaguIds.length === 0) {
      setErrorMsg("请至少勾选 1 个核心八股知识专题。");
      return;
    } else if (interviewType === "general_behavioral" && selectedGeneralIds.length === 0) {
      setErrorMsg("请至少选择 1 个综合素质面评估包。");
      return;
    }

    const packIds =
      interviewType === "bagu_fundamentals"
        ? selectedBaguIds
        : interviewType === "general_behavioral"
        ? selectedGeneralIds
        : [];

    setSubmitting(true);
    try {
      setStageHint(
        githubUrl.trim()
          ? "正在解析上下文并通过 Repomix AST 压缩仓库（≤20K Tokens）..."
          : interviewType === "project_deep_dive"
          ? "正在解析简历与岗位上下文..."
          : "正在装载赛道/八股题库并合成静态前缀上下文..."
      );

      const form = new FormData();
      form.append("interview_type", interviewType);
      form.append("title", title.trim());
      if (interviewType === "cs_role_track") {
        form.append("role_track_id", selectedRoleId);
      }
      if (packIds.length > 0) {
        form.append("knowledge_pack_ids", JSON.stringify(packIds));
      }
      form.append("job_description", jobDescription.trim());
      form.append("resume_text", resumeText.trim());
      form.append("github_repo_url", githubUrl.trim());
      if (resumeFile) {
        form.append("resume_file", resumeFile);
      }

      const ctx = await createContext(form);
      setStageHint("Prep 预规划中：正在构建静态前缀与 L1-L4 追问考点题纲...");
      const session = await createSession({
        context_id: ctx.id,
        interviewer_style: style,
        interaction_mode: mode,
      });

      router.push(`/interview/${session.id}`);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "启动失败");
    } finally {
      setSubmitting(false);
      setStageHint("");
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      // ignore
    }
  };

  const isPresetMode = interviewType !== "project_deep_dive";

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div className="lg:col-span-7 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white">
              上下文准备台
            </h1>
            <p className="mt-1 text-xs text-zinc-400">
              支持「项目源码深挖 / 通用综合面 / 8 大 CS 职业赛道 / 7 大八股突击」——免传简历也能一键开考。
            </p>
          </div>
          {interviewType === "project_deep_dive" && (
            <Button type="button" size="sm" variant="secondary" onClick={fillDemoData}>
              <Sparkles className="h-3.5 w-3.5 text-sky-300" />
              一键填入项目示例
            </Button>
          )}
        </div>

        <Card>
          <CardContent className="pt-5">
            <form onSubmit={handleStart} className="space-y-5">
              {/* Four-Mode Bento Switcher */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-zinc-300">选择面试类型</label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {INTERVIEW_MODE_CARDS.map((card) => {
                    const Icon = card.icon;
                    const active = interviewType === card.id;
                    return (
                      <button
                        key={card.id}
                        type="button"
                        onClick={() => {
                          setInterviewType(card.id);
                          setErrorMsg("");
                        }}
                        className={cn(
                          "group flex flex-col items-start rounded-2xl border p-3 text-left transition-all cursor-pointer backdrop-blur-md",
                          active
                            ? "border-sky-400/60 bg-sky-400/[0.12] text-white shadow-[0_0_24px_rgba(56,189,248,0.16),inset_0_1px_0_rgba(255,255,255,0.12)]"
                            : "border-white/[0.08] bg-white/[0.025] text-zinc-300 hover:border-white/[0.16] hover:bg-white/[0.05]"
                        )}
                      >
                        <div className="flex w-full items-center justify-between gap-2">
                          <span className="flex items-center gap-1.5 text-xs font-semibold">
                            <Icon
                              className={cn(
                                "h-4 w-4 transition-colors",
                                active ? "text-sky-300" : "text-zinc-400 group-hover:text-zinc-200"
                              )}
                            />
                            {card.label}
                          </span>
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5 text-[10px]",
                              active
                                ? "border-sky-300/40 bg-sky-300/15 text-sky-200"
                                : "border-white/[0.09] bg-white/[0.04] text-zinc-400"
                            )}
                          >
                            {card.badge}
                          </span>
                        </div>
                        <span className="mt-1.5 text-[11px] leading-relaxed text-zinc-400">
                          {card.desc}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Mode-Specific Panel */}
              {interviewType === "cs_role_track" && (
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-zinc-300">
                      选择计算机职业专项赛道（8 选 1）
                    </label>
                    {activeRole && (
                      <span className="text-[11px] text-sky-300">
                        已选：{activeRole.name}（{activeRole.core_topics.length} 个预设核心考点）
                      </span>
                    )}
                  </div>

                  {presetsLoading ? (
                    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] py-6 text-center text-xs text-zinc-400">
                      正在加载 8 大职业专项预设...
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {roles.map((role) => {
                        const selected = selectedRoleId === role.id;
                        const hasCodeChallenge = role.core_topics.some((t) => Boolean(t.coding_challenge));
                        return (
                          <button
                            key={role.id}
                            type="button"
                            onClick={() => setSelectedRoleId(role.id)}
                            className={cn(
                              "flex flex-col items-start rounded-xl border p-3 text-left transition-all cursor-pointer backdrop-blur-md",
                              selected
                                ? "border-sky-400/60 bg-sky-400/[0.11] text-white shadow-[0_0_20px_rgba(56,189,248,0.14),inset_0_1px_0_rgba(255,255,255,0.1)]"
                                : "border-white/[0.08] bg-white/[0.025] text-zinc-300 hover:border-white/[0.16] hover:bg-white/[0.045]"
                            )}
                          >
                            <div className="flex w-full items-center justify-between gap-1.5">
                              <span className="text-xs font-semibold">{role.name}</span>
                              <div className="flex items-center gap-1">
                                {hasCodeChallenge && (
                                  <span
                                    title="含 Pyodide 编程实操题"
                                    className="inline-flex items-center gap-0.5 rounded border border-emerald-400/35 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] text-emerald-200"
                                  >
                                    <Code2 className="h-2.5 w-2.5" />
                                    机试
                                  </span>
                                )}
                                {selected && <Check className="h-3.5 w-3.5 text-sky-300" />}
                              </div>
                            </div>
                            <span className="mt-1 line-clamp-2 text-[11px] text-zinc-400">
                              {role.tagline}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {interviewType === "bagu_fundamentals" && (
                <div className="space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <label className="text-xs font-medium text-zinc-300">
                      多选核心八股专题（已选 {selectedBaguIds.length}/{fundamentals.length || 7}）
                    </label>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setSelectedBaguIds(["network", "mysql", "redis_mq"])}
                        className="rounded-lg border border-white/[0.09] bg-white/[0.04] px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-white/[0.08] cursor-pointer"
                      >
                        后端高频三件套
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedBaguIds(fundamentals.map((f) => f.id))}
                        className="rounded-lg border border-white/[0.09] bg-white/[0.04] px-2 py-0.5 text-[11px] text-zinc-300 hover:bg-white/[0.08] cursor-pointer"
                      >
                        全选 7 项
                      </button>
                    </div>
                  </div>

                  {presetsLoading ? (
                    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] py-6 text-center text-xs text-zinc-400">
                      正在加载八股专题包...
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {fundamentals.map((pack) => {
                        const selected = selectedBaguIds.includes(pack.id);
                        const hasCodeChallenge = pack.core_topics.some((t) => Boolean(t.coding_challenge));
                        return (
                          <button
                            key={pack.id}
                            type="button"
                            onClick={() =>
                              togglePackId(selectedBaguIds, setSelectedBaguIds, pack.id)
                            }
                            className={cn(
                              "flex flex-col items-start rounded-xl border p-3 text-left transition-all cursor-pointer backdrop-blur-md",
                              selected
                                ? "border-amber-400/55 bg-amber-400/[0.10] text-white shadow-[0_0_20px_rgba(251,191,36,0.12),inset_0_1px_0_rgba(255,255,255,0.1)]"
                                : "border-white/[0.08] bg-white/[0.025] text-zinc-300 hover:border-white/[0.16] hover:bg-white/[0.045]"
                            )}
                          >
                            <div className="flex w-full items-center justify-between gap-2">
                              <span className="text-xs font-semibold">{pack.name}</span>
                              <div className="flex items-center gap-1">
                                {hasCodeChallenge && (
                                  <span className="rounded border border-emerald-400/35 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] text-emerald-200">
                                    手撕代码
                                  </span>
                                )}
                                <span
                                  className={cn(
                                    "flex h-4 w-4 items-center justify-center rounded border text-[10px]",
                                    selected
                                      ? "border-amber-300 bg-amber-400/30 text-amber-100"
                                      : "border-white/20 bg-white/[0.03]"
                                  )}
                                >
                                  {selected && <Check className="h-3 w-3" />}
                                </span>
                              </div>
                            </div>
                            <span className="mt-1 line-clamp-2 text-[11px] text-zinc-400">
                              {pack.summary}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {interviewType === "general_behavioral" && (
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-zinc-300">
                      选择综合素质与 STAR 面试模块（已选 {selectedGeneralIds.length}）
                    </label>
                    <span className="text-[11px] text-violet-300">
                      纯行为/综合面未提交代码时「代码与测试」维度诚实标 N/A
                    </span>
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    {generalPacks.map((pack) => {
                      const selected = selectedGeneralIds.includes(pack.id);
                      return (
                        <button
                          key={pack.id}
                          type="button"
                          onClick={() =>
                            togglePackId(selectedGeneralIds, setSelectedGeneralIds, pack.id)
                          }
                          className={cn(
                            "flex items-start justify-between gap-3 rounded-xl border p-3 text-left transition-all cursor-pointer backdrop-blur-md",
                            selected
                              ? "border-violet-400/55 bg-violet-400/[0.11] text-white shadow-[0_0_20px_rgba(167,139,250,0.12)]"
                              : "border-white/[0.08] bg-white/[0.025] text-zinc-300 hover:border-white/[0.16] hover:bg-white/[0.045]"
                          )}
                        >
                          <div>
                            <div className="text-xs font-semibold">{pack.name}</div>
                            <div className="mt-0.5 text-[11px] text-zinc-400">{pack.summary}</div>
                          </div>
                          <span
                            className={cn(
                              "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                              selected
                                ? "border-violet-300 bg-violet-400/30 text-violet-100"
                                : "border-white/20 bg-white/[0.03]"
                            )}
                          >
                            {selected && <Check className="h-3 w-3" />}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Title */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  场次名称（可选，留空自动按模式/赛道命名）
                </label>
                <Input
                  placeholder={
                    interviewType === "project_deep_dive"
                      ? "例如：字节后端二面 · 项目深挖"
                      : activeRole && interviewType === "cs_role_track"
                      ? `例如：${activeRole.name}专项冲刺`
                      : "例如：高频八股 + STAR 模拟"
                  }
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              {/* Optional Toggle for Preset Modes, Always Open for Project Deep Dive */}
              {isPresetMode && (
                <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-3.5 py-2.5">
                  <button
                    type="button"
                    onClick={() => setShowOptionalContext((v) => !v)}
                    className="flex w-full items-center justify-between text-xs text-zinc-300 hover:text-white cursor-pointer"
                  >
                    <span className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-sky-300" />
                      可选：附加简历 / 目标 JD / GitHub 仓库（不填亦可直接开考）
                    </span>
                    {showOptionalContext ? (
                      <ChevronUp className="h-4 w-4 text-zinc-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-zinc-400" />
                    )}
                  </button>
                </div>
              )}

              {(!isPresetMode || showOptionalContext) && (
                <div className="space-y-4 rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <label className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
                        <FileText className="h-3.5 w-3.5 text-sky-400" />
                        简历（PDF / Markdown via MarkItDown，或直接粘贴）
                        {!isPresetMode && <span className="text-rose-400">*</span>}
                      </label>
                      <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-white/[0.12] bg-white/[0.05] px-2.5 py-1 text-[11px] text-zinc-200 hover:bg-white/[0.1]">
                        <Upload className="h-3 w-3" />
                        {resumeFile ? resumeFile.name : "选择 PDF / MD 文件"}
                        <input
                          type="file"
                          accept=".pdf,.md,.markdown,.txt"
                          className="hidden"
                          onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                        />
                      </label>
                    </div>
                    <Textarea
                      rows={4}
                      placeholder="可直接粘贴简历 Markdown 文本（若同时上传文件将优先采用文件解析结果）..."
                      value={resumeText}
                      onChange={(e) => setResumeText(e.target.value)}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-zinc-300">
                      目标岗位 JD {!isPresetMode && <span className="text-rose-400">*</span>}
                    </label>
                    <Textarea
                      rows={3}
                      placeholder={
                        isPresetMode
                          ? "可选：若粘贴具体公司 JD，Prep 会将你的自定义 JD 与所选赛道自动融合..."
                          : "粘贴目标公司/岗位的职位描述（JD），Prep 阶段会据此定位差距与考点..."
                      }
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
                      <GitBranch className="h-3.5 w-3.5 text-zinc-300" />
                      公开 GitHub 仓库链接（可选 · Repomix AST 压缩 ≤20K Tokens）
                    </label>
                    <Input
                      placeholder="https://github.com/owner/repo"
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                    />
                  </div>
                </div>
              )}

              {/* Interviewer Style & Interaction Mode */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">面试官风格</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setStyle("gentle")}
                      className={cn(
                        "flex flex-col items-start rounded-xl border p-2.5 text-left transition-all cursor-pointer backdrop-blur-md",
                        style === "gentle"
                          ? "border-emerald-400/60 bg-emerald-400/[0.12] text-emerald-100 shadow-[0_0_16px_rgba(52,211,153,0.14)]"
                          : "border-white/[0.08] bg-white/[0.025] text-zinc-400 hover:border-white/[0.16]"
                      )}
                    >
                      <span className="flex items-center gap-1.5 text-xs font-semibold">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        温和引导
                      </span>
                      <span className="mt-1 text-[10px] opacity-80">
                        卡壳时适度启发，稳步深挖
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setStyle("pressure")}
                      className={cn(
                        "flex flex-col items-start rounded-xl border p-2.5 text-left transition-all cursor-pointer backdrop-blur-md",
                        style === "pressure"
                          ? "border-rose-400/60 bg-rose-400/[0.12] text-rose-100 shadow-[0_0_16px_rgba(244,63,94,0.14)]"
                          : "border-white/[0.08] bg-white/[0.025] text-zinc-400 hover:border-white/[0.16]"
                      )}
                    >
                      <span className="flex items-center gap-1.5 text-xs font-semibold">
                        <Flame className="h-3.5 w-3.5" />
                        大厂高压拷打
                      </span>
                      <span className="mt-1 text-[10px] opacity-80">
                        直击漏洞、拒收空话、强压追问
                      </span>
                    </button>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">默认交互模式</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setMode("voice")}
                      className={cn(
                        "flex flex-col items-start rounded-xl border p-2.5 text-left transition-all cursor-pointer backdrop-blur-md",
                        mode === "voice"
                          ? "border-sky-400/60 bg-sky-400/[0.12] text-sky-100 shadow-[0_0_16px_rgba(56,189,248,0.14)]"
                          : "border-white/[0.08] bg-white/[0.025] text-zinc-400 hover:border-white/[0.16]"
                      )}
                    >
                      <span className="text-xs font-semibold">语音双模</span>
                      <span className="mt-1 text-[10px] opacity-80">
                        TTS 提问 + 语音/文本作答
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setMode("text")}
                      className={cn(
                        "flex flex-col items-start rounded-xl border p-2.5 text-left transition-all cursor-pointer backdrop-blur-md",
                        mode === "text"
                          ? "border-sky-400/60 bg-sky-400/[0.12] text-sky-100 shadow-[0_0_16px_rgba(56,189,248,0.14)]"
                          : "border-white/[0.08] bg-white/[0.025] text-zinc-400 hover:border-white/[0.16]"
                      )}
                    >
                      <span className="text-xs font-semibold">纯文本调试</span>
                      <span className="mt-1 text-[10px] opacity-80">
                        无麦克风静音完整走通
                      </span>
                    </button>
                  </div>
                </div>
              </div>

              {errorMsg && (
                <div className="rounded-xl border border-rose-400/40 bg-rose-500/15 backdrop-blur-md px-3.5 py-2.5 text-xs text-rose-200">
                  {errorMsg}
                </div>
              )}

              {stageHint && (
                <div className="flex items-center gap-2 rounded-xl border border-sky-400/40 bg-sky-500/15 backdrop-blur-md px-3.5 py-2.5 text-xs text-sky-100">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>{stageHint}</span>
                </div>
              )}

              <Button type="submit" size="lg" className="w-full" disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在构建 Prep 题纲...
                  </>
                ) : (
                  <>
                    {isPresetMode ? "免简历一键生成题纲并进入面试房" : "生成 Prep 题纲并进入面试房"}
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* History Column */}
      <div className="lg:col-span-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-base font-semibold text-white">
            <History className="h-4 w-4 text-sky-300" />
            历史模拟面试场次
          </h2>
          <Button type="button" size="sm" variant="ghost" onClick={refreshHistory}>
            刷新
          </Button>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>
              所有场次、逐字稿、代码快照与复盘报告均持久化于 SQLite (WAL)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5 max-h-[700px] overflow-y-auto">
            {loadingHistory ? (
              <div className="py-8 text-center text-xs text-zinc-400">加载历史场次中...</div>
            ) : sessions.length === 0 ? (
              <div className="rounded-xl border border-dashed border-white/[0.12] bg-white/[0.02] py-10 text-center text-xs text-zinc-400">
                暂无历史面试记录。上方任选赛道/八股/STAR 模式即可直接开考。
              </div>
            ) : (
              sessions.map((s) => {
                const modeMeta =
                  HISTORY_MODE_BADGE[s.interview_type] || HISTORY_MODE_BADGE.project_deep_dive;
                const roleLabel = s.role_track_id ? roleNameMap[s.role_track_id] || s.role_track_id : null;
                return (
                  <div
                    key={s.id}
                    className="rounded-2xl border border-white/[0.08] bg-white/[0.03] backdrop-blur-md p-3.5 text-xs space-y-2 transition-all hover:border-white/[0.16] hover:bg-white/[0.05]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="font-medium text-zinc-100 line-clamp-1">
                          {s.context_title || "模拟面试"}
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-zinc-400">
                          <Badge variant={modeMeta.variant} className="text-[10px] px-1.5 py-0">
                            {modeMeta.label}
                          </Badge>
                          {roleLabel && (
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                              {roleLabel}
                            </Badge>
                          )}
                          <Badge
                            variant={s.interviewer_style === "pressure" ? "danger" : "success"}
                            className="text-[10px] px-1.5 py-0"
                          >
                            {s.interviewer_style === "pressure" ? "大厂高压" : "温和引导"}
                          </Badge>
                          <span>轮次: {s.total_turns}</span>
                          <span>缓存: {(s.cache_hit_rate * 100).toFixed(0)}%</span>
                          <span>¥{s.estimated_cost_cny.toFixed(4)}</span>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        {s.overall_score !== null ? (
                          <div className="font-mono text-base font-bold text-sky-300">
                            {s.overall_score.toFixed(1)}
                          </div>
                        ) : (
                          <Badge variant="secondary" className="text-[10px]">
                            {s.status}
                          </Badge>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-1.5 border-t border-white/[0.07]">
                      <div className="flex items-center gap-3">
                        <Link
                          href={`/interview/${s.id}`}
                          className="text-sky-300 hover:text-sky-200 hover:underline font-medium"
                        >
                          {s.status === "in_progress" ? "继续面试" : "查看对话"}
                        </Link>
                        {(s.status === "completed" || s.status === "evaluated") && (
                          <Link
                            href={`/report/${s.id}`}
                            className="text-emerald-300 hover:text-emerald-200 hover:underline font-medium"
                          >
                            证据复盘台
                          </Link>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteSession(s.id)}
                        className="text-zinc-500 hover:text-rose-400 cursor-pointer"
                        title="删除场次"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
