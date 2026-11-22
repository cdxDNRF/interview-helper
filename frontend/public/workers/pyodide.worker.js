/* Dedicated Pyodide WebWorker for zero-backend Python execution & unit tests */
let pyodideInstance = null;
let loadingPromise = null;

async function ensurePyodide(indexURL) {
  if (pyodideInstance) return pyodideInstance;
  if (!loadingPromise) {
    loadingPromise = (async () => {
      const base = indexURL || "https://cdn.jsdelivr.net/pyodide/v0.27.5/full/";
      self.importScripts(`${base}pyodide.js`);
      pyodideInstance = await self.loadPyodide({ indexURL: base });
      return pyodideInstance;
    })();
  }
  return loadingPromise;
}

self.onmessage = async (event) => {
  const { id, sourceCode, testCasesCode, indexURL } = event.data;
  const startedAt = performance.now();

  try {
    const pyodide = await ensurePyodide(indexURL);
    const wrappedScript = `
import io, sys, traceback

_stdout = io.StringIO()
_stderr = io.StringIO()
_old_out, _old_err = sys.stdout, sys.stderr
sys.stdout, sys.stderr = _stdout, _stderr

_passed = True
_error_msg = ""
_ns = {}

try:
    exec(${JSON.stringify(sourceCode || "")}, _ns)
    if ${JSON.stringify(Boolean((testCasesCode || "").trim()))}:
        exec(${JSON.stringify(testCasesCode || "")}, _ns)
except Exception:
    _passed = False
    _error_msg = traceback.format_exc()
finally:
    sys.stdout, sys.stderr = _old_out, _old_err

(_passed, _stdout.getvalue(), _stderr.getvalue(), _error_msg)
`;

    const resProxy = await pyodide.runPythonAsync(wrappedScript);
    const [passed, stdoutStr, stderrStr, errorMsg] = resProxy.toJs();
    resProxy.destroy();

    const execTimeMs = Math.round(performance.now() - startedAt);
    const assertCount = Math.max(
      1,
      ((testCasesCode || "").match(/\bassert\b/g) || []).length
    );

    const combinedOutput = [stdoutStr, stderrStr, errorMsg]
      .filter((s) => s && String(s).trim())
      .join("\n")
      .trim();

    self.postMessage({
      id,
      ok: true,
      testsPassed: Boolean(passed),
      passedCount: passed ? assertCount : 0,
      totalCount: assertCount,
      output: combinedOutput || (passed ? "Tests passed." : "Execution failed."),
      execTimeMs,
    });
  } catch (err) {
    self.postMessage({
      id,
      ok: false,
      testsPassed: false,
      passedCount: 0,
      totalCount: 1,
      output: `Pyodide 初始化或执行异常: ${err?.message || String(err)}`,
      execTimeMs: Math.round(performance.now() - startedAt),
    });
  }
};
