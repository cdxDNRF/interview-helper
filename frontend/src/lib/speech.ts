export function speakWithWebSpeech(
  text: string,
  onStart?: () => void,
  onEnd?: () => void
): () => void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    onEnd?.();
    return () => {};
  }

  let finished = false;
  let started = false;
  const finishOnce = () => {
    if (finished) return;
    finished = true;
    clearTimeout(watchdogId);
    onEnd?.();
  };

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 1.05;
  utterance.onstart = () => {
    started = true;
    onStart?.();
  };
  utterance.onend = finishOnce;
  utterance.onerror = finishOnce;

  // Guard against headless/muted environments where SpeechSynthesis never fires start/end
  const watchdogId = window.setTimeout(() => {
    if (!started) {
      finishOnce();
    }
  }, 2500);

  try {
    window.speechSynthesis.speak(utterance);
  } catch {
    finishOnce();
  }

  return () => {
    finished = true;
    clearTimeout(watchdogId);
    try {
      window.speechSynthesis.cancel();
    } catch {
      // ignore
    }
  };
}

export interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((ev: unknown) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

export function getBrowserSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}
