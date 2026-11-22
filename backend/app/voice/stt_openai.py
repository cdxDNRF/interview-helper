from app.llm.client import _build_httpx_client
from app.voice.interfaces import BaseSTTProvider, STTResult


class OpenAICompatSTTProvider(BaseSTTProvider):
    """Calls OpenAI-compatible /audio/transcriptions endpoint with optional hotword prompt."""

    name = "openai_stt"

    def __init__(self, base_url: str, api_key: str, model: str = "whisper-1"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "sk-local"
        self.model = model

    async def transcribe(
        self, audio_bytes: bytes, filename: str, *, hotwords: list[str] | None = None
    ) -> STTResult:
        if not audio_bytes:
            raise ValueError("音频文件为空，无法转写")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "model": self.model,
            "response_format": "verbose_json",
        }
        if hotwords:
            data["prompt"] = "Technical terms: " + ", ".join(hotwords[:25])

        files = {"file": (filename or "recording.webm", audio_bytes, "audio/webm")}
        async with _build_httpx_client(self.base_url, timeout=45.0) as client:
            resp = await client.post(
                f"{self.base_url}/audio/transcriptions",
                headers=headers,
                data=data,
                files=files,
            )
            resp.raise_for_status()
            payload = resp.json()

        word_ts: list[dict] = []
        for w in payload.get("words") or []:
            if isinstance(w, dict) and "word" in w:
                word_ts.append(
                    {
                        "word": w["word"],
                        "start_ms": int(float(w.get("start", 0)) * 1000),
                        "end_ms": int(float(w.get("end", 0)) * 1000),
                    }
                )

        duration_ms = int(float(payload.get("duration") or 0) * 1000)
        return STTResult(
            text=str(payload.get("text") or "").strip(),
            provider_used=self.name,
            word_timestamps=word_ts,
            duration_ms=duration_ms,
        )
