"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Code2, Loader2, Play, RotateCcw, Terminal, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CodeSnapshotPayload, CodingChallenge } from "@/lib/types";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[260px] items-center justify-center bg-zinc-950 text-xs text-zinc-500">
      正在加载 Monaco 编辑器...
    </div>
  ),
});

const DEFAULT_FALLBACK_CHALLENGE: CodingChallenge = {
  title: "Python 现场编程与边界单测（Pyodide 浏览器沙箱）",
  starter_code:
    "def dedup_preserve_order(items: list[str]) -> list[str]:\n" +
    "    # TODO: 去重并保持原顺序\n" +
    "    seen = set()\n" +
    "    out = []\n" +
    "    for x in items:\n" +
    "        if x not in seen:\n" +
    "            seen.add(x)\n" +
    "            out.append(x)\n" +
    "    return out\n",
  test_cases_code:
    "assert dedup_preserve_order(['a', 'b', 'a', 'c']) == ['a', 'b', 'c']\n" +
    "assert dedup_preserve_order([]) == []\n" +
    "print('ALL_TESTS_PASSED: 2/2')\n",
};

interface CodingSandboxPanelProps {
  challenge?: CodingChallenge | null;
  latestSnapshot: CodeSnapshotPayload | null;
  onSnapshotChange: (snapshot: CodeSnapshotPayload | null) => void;
}

export function CodingSandboxPanel({
  challenge,
  latestSnapshot,
  onSnapshotChange,
}: CodingSandboxPanelProps) {
  const activeChallenge = challenge || DEFAULT_FALLBACK_CHALLENGE;
  const [code, setCode] = useState(activeChallenge.starter_code);
  const [testsCode, setTestsCode] = useState(activeChallenge.test_cases_code);
  const [showTests, setShowTests] = useState(false);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("");
  const workerRef = useRef<Worker | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRunRef = useRef<{ id: number; codeSnapshotText: string; totalTests: number } | null>(
    null
  );
  const onSnapshotChangeRef = useRef(onSnapshotChange);

  useEffect(() => {
    onSnapshotChangeRef.current = onSnapshotChange;
  }, [onSnapshotChange]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      workerRef.current?.terminate();
      workerRef.current = null;
    };
  }, []);

  const createFreshWorker = () => {
    workerRef.current?.terminate();
    const w = new Worker("/workers/pyodide.worker.js");
    w.onmessage = (ev: MessageEvent) => {
      const pending = activeRunRef.current;
      if (!pending || ev.data?.id !== pending.id) return;

      if (ev.data?.phase === "loading_runtime") {
        setOutput("正在首次加载 Pyodide WASM 运行时（约 15MB，随后自动缓存）...");
        return;
      }

      if (ev.data?.phase === "executing") {
        setOutput("Pyodide 运行时已就绪，正在执行 Python 单测（5 秒超时保护）...");
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => {
          createFreshWorker();
          setRunning(false);
          const timeoutMsg = "Python 代码执行超时（>5s），已强杀并重置沙箱线程。";
          setOutput(timeoutMsg);
          onSnapshotChangeRef.current({
            language: "python",
            source_code: pending.codeSnapshotText,
            tests_passed: false,
            passed_count: 0,
            total_count: pending.totalTests,
            test_output: timeoutMsg,
            exec_time_ms: 5000,
          });
        }, 5000);
        return;
      }

      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setRunning(false);
      const { testsPassed, passedCount, totalCount, output: outText, execTimeMs } = ev.data;
      setOutput(String(outText || ""));
      onSnapshotChangeRef.current({
        language: "python",
        source_code: pending.codeSnapshotText,
        tests_passed: Boolean(testsPassed),
        passed_count: Number(passedCount || 0),
        total_count: Number(totalCount || pending.totalTests),
        test_output: String(outText || ""),
        exec_time_ms: Number(execTimeMs || 0),
      });
    };
    workerRef.current = w;
    return w;
  };

  const handleRunTests = () => {
    if (running) return;
    setRunning(true);
    setOutput("正在初始化 Pyodide WebWorker...");

    const worker = workerRef.current || createFreshWorker();
    const runId = Date.now();
    const totalTests = Math.max(1, (testsCode.match(/\bassert\b/g) || []).length);
    activeRunRef.current = { id: runId, codeSnapshotText: code, totalTests };

    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    // Boot timeout (45s) for cold WASM fetch; replaced by strict 5s timeout once code execution begins
    timeoutRef.current = setTimeout(() => {
      createFreshWorker();
      setRunning(false);
      const timeoutMsg =
        "Pyodide WASM 运行时加载超时（>45s）。若处于离线环境，可在 .env 配置本地 NEXT_PUBLIC_PYODIDE_INDEX_URL 镜像。";
      setOutput(timeoutMsg);
      onSnapshotChangeRef.current({
        language: "python",
        source_code: code,
        tests_passed: false,
        passed_count: 0,
        total_count: totalTests,
        test_output: timeoutMsg,
        exec_time_ms: 45000,
      });
    }, 45000);

    worker.postMessage({
      id: runId,
      sourceCode: code,
      testCasesCode: testsCode,
      indexURL: process.env.NEXT_PUBLIC_PYODIDE_INDEX_URL || undefined,
    });
  };

  const handleReset = () => {
    setCode(activeChallenge.starter_code);
    setTestsCode(activeChallenge.test_cases_code);
    setOutput("");
    onSnapshotChange(null);
  };

  return (
    <Card className="border-sky-500/30 bg-zinc-950/90">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Code2 className="h-4 w-4 text-sky-400" />
            <CardTitle className="text-sm">{activeChallenge.title}</CardTitle>
            <Badge variant="secondary" className="text-[10px]">
              Pyodide 零后端沙箱
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {latestSnapshot && (
              <Badge
                variant={latestSnapshot.tests_passed ? "success" : "danger"}
                className="gap-1 text-[10px]"
              >
                {latestSnapshot.tests_passed ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <XCircle className="h-3 w-3" />
                )}
                {latestSnapshot.passed_count}/{latestSnapshot.total_count} ·{" "}
                {latestSnapshot.exec_time_ms}ms（下轮提交将同步给面试官）
              </Badge>
            )}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setShowTests((v) => !v)}
            >
              {showTests ? "隐藏单测" : "查看单测用例"}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={handleReset}>
              <RotateCcw className="h-3.5 w-3.5" />
              重置
            </Button>
            <Button type="button" size="sm" onClick={handleRunTests} disabled={running}>
              {running ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  运行中...
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" />
                  运行单测
                </>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <MonacoEditor
            height="240px"
            language="python"
            theme="vs-dark"
            value={code}
            onChange={(val) => {
              const next = val ?? "";
              setCode(next);
              onSnapshotChange({
                language: "python",
                source_code: next,
                tests_passed: latestSnapshot?.tests_passed ?? false,
                passed_count: latestSnapshot?.passed_count ?? 0,
                total_count: latestSnapshot?.total_count ?? 0,
                test_output: latestSnapshot?.test_output ?? "(代码已修改，尚未运行单测)",
                exec_time_ms: latestSnapshot?.exec_time_ms ?? 0,
              });
            }}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: "on",
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 4,
            }}
          />
        </div>

        {showTests && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-2.5">
            <div className="mb-1 text-[10px] font-medium text-zinc-400">
              单元测试断言代码（可自行补充边界用例）
            </div>
            <textarea
              rows={5}
              value={testsCode}
              onChange={(e) => setTestsCode(e.target.value)}
              className="w-full rounded bg-zinc-950 p-2 font-mono text-xs text-zinc-200 border border-zinc-800 focus:outline-none"
            />
          </div>
        )}

        {output && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs">
            <div className="mb-1 flex items-center gap-1.5 text-[10px] text-zinc-400">
              <Terminal className="h-3 w-3" />
              Pyodide 标准输出 / Traceback
            </div>
            <pre className="whitespace-pre-wrap text-zinc-200 max-h-36 overflow-y-auto">
              {output}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
