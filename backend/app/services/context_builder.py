import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from markitdown import MarkItDown

from app.config import DATA_DIR, env_settings

GITHUB_REPO_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


def count_tokens_accurate(text: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
    except Exception:
        # Deterministic fallback when BPE vocab cannot be loaded offline
        cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
        other = max(0, len(text) - cjk)
        return int(cjk * 1.3 + other / 3.6)


def parse_resume_bytes(filename: str, content: bytes) -> tuple[str, list[str]]:
    warnings: list[str] = []
    suffix = Path(filename or "resume.md").suffix.lower() or ".md"

    if suffix in {".md", ".markdown", ".txt"}:
        text = content.decode("utf-8", errors="replace").strip()
        if not text:
            warnings.append("上传的简历文件为空。")
        return text, warnings

    uploads_dir = DATA_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = uploads_dir / f"{uuid4().hex}{suffix}"
    try:
        tmp_path.write_bytes(content)
        md = MarkItDown()
        result = md.convert(str(tmp_path))
        text = (result.text_content or "").strip()
        if len(text) < 40 and suffix == ".pdf":
            warnings.append(
                "检测到 PDF 提取文本极少，可能是纯图片扫描件。建议导出可选中文本的 PDF 或直接粘贴 Markdown 简历。"
            )
        return text, warnings
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def validate_github_repo_url(url: str) -> str:
    clean = url.strip()
    if not GITHUB_REPO_URL_RE.match(clean):
        raise ValueError(
            "仅支持公开 GitHub 仓库 HTTPS 地址，格式如 https://github.com/owner/repo"
        )
    return clean.rstrip("/")


def _truncate_to_token_budget(text: str, max_tokens: int) -> tuple[str, int, bool]:
    tokens = count_tokens_accurate(text)
    if tokens <= max_tokens:
        return text, tokens, False

    # Binary search character cut to keep strictly <= max_tokens
    low, high = 0, len(text)
    best = text[: min(len(text), max_tokens * 2)]
    while low <= high:
        mid = (low + high) // 2
        candidate = text[:mid] + "\n\n... [Truncated by interview-helper to fit <=20K token budget]"
        c_tokens = count_tokens_accurate(candidate)
        if c_tokens <= max_tokens:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    return best, count_tokens_accurate(best), True


def _run_subprocess_sync(cmd: list[str], cwd: Path, env: dict[str, str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


async def pack_github_repo_with_repomix(
    repo_url: str, max_tokens: int | None = None
) -> tuple[str, int, list[str]]:
    clean_url = validate_github_repo_url(repo_url)
    budget = max_tokens or env_settings.repomix_max_tokens
    warnings: list[str] = []

    tmp_root = DATA_DIR / "tmp_repos"
    tmp_root.mkdir(parents=True, exist_ok=True)
    work_dir = tmp_root / uuid4().hex
    clone_dir = work_dir / "repo"
    out_file = work_dir / "repomix-output.md"

    env = os.environ.copy()
    if env_settings.github_proxy:
        env.setdefault("HTTP_PROXY", env_settings.github_proxy)
        env.setdefault("HTTPS_PROXY", env_settings.github_proxy)

    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        clone_cmd = ["git", "clone", "--depth", "1", clean_url, str(clone_dir)]
        clone_res = await asyncio.to_thread(_run_subprocess_sync, clone_cmd, work_dir, env, 90)
        if clone_res.returncode != 0:
            raise RuntimeError(f"GitHub 仓库克隆失败: {clone_res.stderr.strip()[:300]}")

        npx_exe = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
        base_ignore = "node_modules/**,.git/**,dist/**,build/**,.next/**,*.lock,package-lock.json,uv.lock"
        repomix_cmd = [
            npx_exe,
            "--yes",
            "repomix",
            "--compress",
            "--style",
            "markdown",
            "--ignore",
            base_ignore,
            "--output",
            str(out_file),
        ]
        rm_res = await asyncio.to_thread(_run_subprocess_sync, repomix_cmd, clone_dir, env, 120)
        if rm_res.returncode != 0 or not out_file.exists():
            raise RuntimeError(
                f"Repomix 压缩失败: {(rm_res.stderr or rm_res.stdout).strip()[:300]}"
            )

        digest = out_file.read_text(encoding="utf-8", errors="replace")
        tokens = count_tokens_accurate(digest)

        if tokens > budget:
            strict_ignore = (
                base_ignore
                + ",tests/**,test/**,__tests__/**,docs/**,*.md,*.png,*.jpg,*.svg,*.css,*.map"
            )
            rm_strict = await asyncio.to_thread(
                _run_subprocess_sync,
                [
                    npx_exe,
                    "--yes",
                    "repomix",
                    "--compress",
                    "--style",
                    "markdown",
                    "--ignore",
                    strict_ignore,
                    "--output",
                    str(out_file),
                ],
                clone_dir,
                env,
                120,
            )
            if rm_strict.returncode == 0 and out_file.exists():
                digest = out_file.read_text(encoding="utf-8", errors="replace")
                tokens = count_tokens_accurate(digest)
                warnings.append("仓库 AST 体积较大，已自动过滤 tests/docs/静态资源以控制静态前缀预算。")

        digest, final_tokens, truncated = _truncate_to_token_budget(digest, budget)
        if truncated:
            warnings.append(f"源码压缩后仍超过 {budget} Tokens 上限，已按预算安全截断。")
        return digest, final_tokens, warnings
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
