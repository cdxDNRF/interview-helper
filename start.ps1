param(
    [switch]$Mock,
    [switch]$NoBrowser,
    [switch]$SmokeTest
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"

function Test-LocalHttpReady {
    param([string]$Url)
    try {
        $wc = New-Object System.Net.WebClient
        $wc.Proxy = $null
        $null = $wc.DownloadString($Url)
        $wc.Dispose()
        return $true
    } catch {
        return $false
    }
}

Write-Host "=== interview-helper 快捷启动 ===" -ForegroundColor Cyan

# 1. 确保 .env 存在
$EnvFile = Join-Path $RootDir ".env"
$EnvExample = Join-Path $RootDir ".env.example"
if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "[Init] 已根据 .env.example 生成 .env" -ForegroundColor Yellow
}

# 2. 确保 uv 缓存落盘到 D 盘
if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = "D:\code_program\uv_cache"
}

# 3. 检查端口占用
$busyPorts = Get-NetTCPConnection -LocalPort 8000, 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort -Unique
if ($busyPorts) {
    Write-Host "[Warn] 检测到端口已被占用: $($busyPorts -join ', ')。若旧服务仍在运行，请先关闭后再启动。" -ForegroundColor Red
}

# 4. 检查后端虚拟环境
$UvicornExe = Join-Path $BackendDir ".venv\Scripts\uvicorn.exe"
if (-not (Test-Path $UvicornExe)) {
    Write-Host "[Backend] 未检测到 .venv，正在运行 uv sync --python 3.12 ..." -ForegroundColor Yellow
    Push-Location $BackendDir
    try {
        uv sync --python 3.12
        if ($LASTEXITCODE -ne 0) { throw "uv sync 失败" }
    } finally {
        Pop-Location
    }
}

# 5. 检查前端 node_modules
$NodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "[Frontend] 未检测到 node_modules，正在运行 npm install ..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    try {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
    } finally {
        Pop-Location
    }
}

$ModeLabel = if ($Mock) { "离线 Mock 演示模式 (MOCK_MODE=true，无需 API Key)" } else { "标准配置模式 (.env / SQLite 设置)" }
Write-Host "[Mode] $ModeLabel" -ForegroundColor Green

$MockEnvCmd = if ($Mock) { '$env:MOCK_MODE="true"; ' } else { '' }
$BackendCmd = "${MockEnvCmd}Set-Location '$BackendDir'; `$Host.UI.RawUI.WindowTitle='interview-helper Backend (8000)'; .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000"
$FrontendCmd = "Set-Location '$FrontendDir'; `$Host.UI.RawUI.WindowTitle='interview-helper Frontend (3000)'; npm.cmd run dev -- -H 127.0.0.1 -p 3000"

$BackendProc = $null
$FrontendProc = $null

try {
    $winStyle = if ($SmokeTest) { "Hidden" } else { "Normal" }
    $BackendProc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $BackendCmd) -WindowStyle $winStyle -PassThru
    $FrontendProc = Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCmd) -WindowStyle $winStyle -PassThru

    Write-Host "[Wait] 正在等待后端 (8000) 与前端 (3000) 就绪..." -ForegroundColor Cyan

    $Ready = $false
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 1
        $beOk = Test-LocalHttpReady -Url "http://127.0.0.1:8000/health"
        $feOk = Test-LocalHttpReady -Url "http://127.0.0.1:3000"
        if ($beOk -and $feOk) {
            $Ready = $true
            break
        }
    }

    if ($Ready) {
        Write-Host ""
        Write-Host "[Ready] 前后端服务已全部就绪！" -ForegroundColor Green
        Write-Host "  前端界面: http://127.0.0.1:3000"
        Write-Host "  后端文档: http://127.0.0.1:8000/docs"
        if (-not $NoBrowser -and -not $SmokeTest) {
            Start-Process "http://127.0.0.1:3000"
        }
    } else {
        Write-Host "[Warn] 等待超时，请检查前后端窗口日志。" -ForegroundColor Yellow
        if ($SmokeTest) { throw "SmokeTest 等待端口超时" }
    }

    if (-not $SmokeTest) {
        Write-Host ""
        Read-Host "服务运行中 — 按 Enter 键可一键关闭前后端全部进程"
    }
} finally {
    Write-Host "[Stop] 正在清理前后端进程..." -ForegroundColor Yellow
    foreach ($p in @($FrontendProc, $BackendProc)) {
        if ($p -and -not $p.HasExited) {
            try {
                & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null
            } catch {}
        }
    }
    Write-Host "[Done] 已全部停止。" -ForegroundColor Green
}
