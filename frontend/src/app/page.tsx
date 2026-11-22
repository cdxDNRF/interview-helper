"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  FileText,
  Flame,
  GitBranch,
  History,
  Loader2,
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
import { createContext, createSession, deleteSession, listSessions } from "@/lib/api";
import type { InteractionMode, InterviewerStyle, SessionListItem } from "@/lib/types";
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

export default function HomePage() {
  const router = useRouter();
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

  const fillDemoData = () => {
    setTitle("高级 AI Agent 后端模拟");
    setResumeText(SAMPLE_RESUME);
    setJobDescription(SAMPLE_JD);
    setGithubUrl("");
    setErrorMsg("");
  };

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (!resumeFile && !resumeText.trim()) {
      setErrorMsg("请先上传 PDF/Markdown 简历，或粘贴简历内容。");
      return;
    }
    if (!jobDescription.trim()) {
      setErrorMsg("请填写目标岗位 JD。");
      return;
    }

    setSubmitting(true);
    try {
      setStageHint(
        githubUrl.trim()
          ? "正在解析简历并通过 Repomix AST 压缩仓库（≤20K Tokens）..."
          : "正在解析简历与岗位上下文..."
      );
      const form = new FormData();
      form.append("title", title.trim());
      form.append("job_description", jobDescription.trim());
      form.append("resume_text", resumeText.trim());
      form.append("github_repo_url", githubUrl.trim());
      if (resumeFile) {
        form.append("resume_file", resumeFile);
      }

      const ctx = await createContext(form);
      setStageHint("Prep 预规划中：正在生成简历-JD 差距点与 4~5 个核心考点题纲...");
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

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div className="lg:col-span-7 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
              上下文准备台
            </h1>
            <p className="mt-1 text-xs text-zinc-400">
              上传简历 + 岗位 JD + 可选 1 个公开 GitHub 仓库（Repomix AST 压缩 ≤20K Tokens），生成静态前缀缓存题纲。
            </p>
          </div>
          <Button type="button" size="sm" variant="secondary" onClick={fillDemoData}>
            <Sparkles className="h-3.5 w-3.5" />
            一键填入示例
          </Button>
        </div>

        <Card>
          <CardContent className="pt-5">
            <form onSubmit={handleStart} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">
                  场次名称（可选）
                </label>
                <Input
                  placeholder="例如：字节后端二面 · 项目深挖"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
                    <FileText className="h-3.5 w-3.5 text-sky-400" />
                    简历（支持上传 PDF / Markdown via MarkItDown，或直接粘贴）
                  </label>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-[11px] text-zinc-200 hover:bg-zinc-800">
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
                  rows={5}
                  placeholder="可直接粘贴简历 Markdown 文本（若同时上传文件将优先采用文件解析结果）..."
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-300">目标岗位 JD *</label>
                <Textarea
                  rows={4}
                  placeholder="粘贴目标公司/岗位的职位描述（JD），Prep 阶段会据此定位差距与考点..."
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

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-300">面试官风格</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setStyle("gentle")}
                      className={cn(
                        "flex flex-col items-start rounded-lg border p-2.5 text-left transition-colors cursor-pointer",
                        style === "gentle"
                          ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-200"
                          : "border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700"
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
                        "flex flex-col items-start rounded-lg border p-2.5 text-left transition-colors cursor-pointer",
                        style === "pressure"
                          ? "border-rose-500/60 bg-rose-500/10 text-rose-200"
                          : "border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700"
                      )}
                    >
                      <span className="flex items-center gap-1.5 text-xs font-semibold">
                        <Flame className="h-3.5 w-3.5" />
                        大厂高压拷打
                      </span>
                      <span className="mt-1 text-[10px] opacity-80">
                        直击漏洞、拒收八股、强压追问
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
                        "flex flex-col items-start rounded-lg border p-2.5 text-left transition-colors cursor-pointer",
                        mode === "voice"
                          ? "border-sky-500/60 bg-sky-500/10 text-sky-200"
                          : "border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700"
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
                        "flex flex-col items-start rounded-lg border p-2.5 text-left transition-colors cursor-pointer",
                        mode === "text"
                          ? "border-sky-500/60 bg-sky-500/10 text-sky-200"
                          : "border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700"
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
                <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
                  {errorMsg}
                </div>
              )}

              {stageHint && (
                <div className="flex items-center gap-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
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
                    生成 Prep 题纲并进入面试房
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <div className="lg:col-span-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-base font-semibold text-zinc-100">
            <History className="h-4 w-4 text-sky-400" />
            历史模拟面试场次
          </h2>
          <Button type="button" size="sm" variant="ghost" onClick={refreshHistory}>
            刷新
          </Button>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>
              所有场次、对话逐字稿与复盘报告均本地持久化于 SQLite (WAL)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5 max-h-[640px] overflow-y-auto">
            {loadingHistory ? (
              <div className="py-8 text-center text-xs text-zinc-500">加载历史场次中...</div>
            ) : sessions.length === 0 ? (
              <div className="rounded-lg border border-dashed border-zinc-800 py-10 text-center text-xs text-zinc-500">
                暂无历史面试记录。点击左侧「一键填入示例」可立即体验。
              </div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className="rounded-xl border border-zinc-800/90 bg-zinc-950/60 p-3 text-xs space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium text-zinc-100 line-clamp-1">
                        {s.context_title || "模拟面试"}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-zinc-400">
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

                  <div className="flex items-center justify-between pt-1 border-t border-zinc-800/60">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/interview/${s.id}`}
                        className="text-sky-400 hover:underline font-medium"
                      >
                        {s.status === "in_progress" ? "继续面试" : "查看对话"}
                      </Link>
                      {(s.status === "completed" || s.status === "evaluated") && (
                        <Link
                          href={`/report/${s.id}`}
                          className="text-emerald-400 hover:underline font-medium"
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
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
