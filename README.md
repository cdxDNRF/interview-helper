# interview-helper (P0)

面向程序员与技术候选人的 **AI 模拟面试系统**（P0 最小可用闭环）。
摒弃粗糙 2D/3D 数字人与浅层题库问答，聚焦 **GitHub 源码级深挖、确定性四级追问阶梯、静态前缀缓存、思考缓冲友好交互、证据锚定复盘台**。

## 核心架构特性（P0 已交付）

1. **上下文准备台**
   - `MarkItDown` 解析 PDF / Markdown 简历；
   - `Repomix`（`--compress` AST 骨架提取）压缩公开 GitHub 仓库并严格控制 `≤ 20,000` Tokens；
   - 支持 **温和引导** 与 **大厂高压拷打** 两档风格切换。
2. **Prep 预规划 & 确定性四级追问状态机（LangGraph）**
   - 开场前一次性生成「简历-JD 差距点 + 4~5 个核心考点题纲（含源码切入点与二元核查清单）」；
   - **静态前缀缓存铁律**：将 `系统人设 → 固定序列化的工具定义 → 简历 Markdown → JD 与题纲 → Repomix 源码` 锁死在 Prompt 最前端，禁止混入时间戳/UUID/轮次数字；
   - 确定性追问阶梯：**L1 概念原理 → L2 个人实战 → L3 底层细节/代码实现 → L4 极端边界与故障排查**（达标 `≥0.65` 自动升级施压，连续两轮不达标记错切题）。
3. **极简语音 / 文本双模面试房**
   - 极简声波 + 四态指示灯（`倾听中` / `检测到思考停顿，继续等你` / `AI 思考中` / `AI 发言中`）；
   - 支持 **按住空格暂缓提交**、**手动结束发言** 与 **纯文本无麦克风调试模式**；
   - 可插拔 TTS（`edge-tts >= 7.3.1` 含 0 字节检测与异常降级 + 浏览器 `Web Speech API` 兜底，预留 `Kokoro-82M`）与 STT（浏览器语音识别 / OpenAI `/audio/transcriptions`，预留 `LiveKit WebRTC + Smart Turn v3.2`）。
4. **证据锚定复盘台**
   - 独立裁判输出结构化 JSON（Pydantic v2 校验 + 最多 2 次报错自动重试）；
   - 强制先输出 `evidence_quotes` 与 `reasoning`，最后输出可空 `score`（未考维度诚实标 `N/A`）；
   - 纯确定性 Python 统计语速、最长冷场停顿秒数与填充词频次；
   - 三栏式诊断台：带时间戳与填充词高亮的逐字稿 / 原话 vs 满分重构版对比 / 原子核查清单。
5. **BYOK + 零 Key Mock 模式 + SQLite WAL 持久化**
   - `.env` 与设置页均支持分别配置 Prep / Live / Judge 三阶段 `base_url`、`api_key` 与 `model`；
   - 实时统计单场 Token、Prompt Cache 命中率与预估费用；
   - 内置零 API Key 的离线 `MockAdapter`，开箱即用跑通完整链路。

## 快速启动

### 1. 启动后端（FastAPI + LangGraph + SQLite WAL）
```powershell
cd D:\AIagent\interview-helper\backend
$env:UV_CACHE_DIR="D:\code_program\uv_cache"
uv sync --python 3.12
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. 启动前端（Next.js + Tailwind + shadcn/ui）
```powershell
cd D:\AIagent\interview-helper\frontend
npm install
npm run dev
```
访问 `http://127.0.0.1:3000`。如无可用模型密钥，可在右上角「BYOK & 语音设置」打开 **离线 Mock 模式** 直接体验完整流程。

### 3. 运行回归测试（含 5 份固定样本）
```powershell
cd D:\AIagent\interview-helper\backend
.\.venv\Scripts\python.exe -m pytest -v
```
