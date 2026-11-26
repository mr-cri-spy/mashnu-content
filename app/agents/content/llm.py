"""Thin LLM wrapper. Swap provider here only; the graph never imports an SDK."""
import re
import time
from typing import Protocol

from app.config import settings


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class AnthropicLLM:
    def __init__(self):
        import anthropic

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def complete(self, system: str, user: str) -> str:
        r = self.client.messages.create(
            model=settings.llm_model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in r.content if b.type == "text")


RETRY = (404, 429, 403, 500, 502, 503, 504)


class OpenAICompatLLM:
    """Any OpenAI-compatible chat endpoint (xAI Grok, Gemini, Groq, OpenRouter...)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        import httpx

        self.model = model
        self.http = httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=45
        )

    def _candidates(self) -> list[str]:
        """Stable numbered flash models first (newest version first), then other text models."""
        r = self.http.get("/models")
        r.raise_for_status()
        ids = [m["id"].removeprefix("models/") for m in r.json().get("data", [])]
        bad = ("lite", "image", "tts", "live", "audio", "embed", "thinking", "exp", "vision", "omni", "robotics")

        def ver(i: str):
            m = re.match(r"gemini-(\d+)(?:\.(\d+))?", i)
            return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)

        ok = [i for i in ids if i.startswith("gemini") and not any(b in i for b in bad)]
        flash = sorted([i for i in ok if "flash" in i and "preview" not in i], key=ver, reverse=True)
        rest = sorted([i for i in ok if i not in flash], key=ver, reverse=True)
        return flash + rest

    def _post(self, system: str, user: str, model: str):
        import httpx

        try:
            return self._raw_post(system, user, model)
        except httpx.TransportError as e:  # timeout / network blip: treat as retryable 504
            print(f"[llm] {model} transport error: {e!r}")
            return httpx.Response(504, text=repr(e), request=httpx.Request("POST", "http://llm"))

    def _raw_post(self, system: str, user: str, model: str):
        return self.http.post(
            "/chat/completions",
            json={
                "model": model,
                "max_tokens": 4096,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )

    def complete(self, system: str, user: str) -> str:
        r = self._post(system, user, self.model)
        for wait in (15, 30):  # transient overload: back off and retry the same model first
            if r.status_code not in (429, 503):
                break
            print(f"[llm] {r.status_code}, retrying in {wait}s")
            time.sleep(wait)
            r = self._post(system, user, self.model)
        if r.status_code in RETRY:  # model gone or no quota: walk other models
            if r.status_code in (429, 504):
                time.sleep(5)
                r = self._post(system, user, self.model)
            if r.status_code in RETRY:
                tried = [self.model]
                for m in self._candidates():
                    if m in tried:
                        continue
                    tried.append(m)
                    r = self._post(system, user, m)
                    if r.is_success:
                        self.model = m
                        print(f"[llm] using {m}")
                        break
                    if len(tried) >= 9:
                        break
                    time.sleep(2)
        if not r.is_success:
            print(f"[llm] failed {r.status_code}: {r.text[:300]}")
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class FakeLLM:
    """Deterministic offline stub for tests and key-less local runs."""

    def complete(self, system: str, user: str) -> str:
        if "SCORE" in system:
            return "SCORE: 8\nFEEDBACK: ok"
        if "INSIGHT" in system:
            return "Insight: " + user[:120]
        return "DRAFT: " + user[:200]


def get_llm() -> LLM:
    p = settings.llm_provider
    if p == "auto":
        p = ("gemini" if settings.gemini_api_key else "xai" if settings.xai_api_key
             else "anthropic" if settings.anthropic_api_key else "fake")
    if p == "gemini":
        return OpenAICompatLLM(settings.gemini_base_url, settings.gemini_api_key, settings.gemini_model)
    if p == "xai":
        return OpenAICompatLLM(settings.xai_base_url, settings.xai_api_key, settings.xai_model)
    return {"anthropic": AnthropicLLM, "fake": FakeLLM}[p]()
