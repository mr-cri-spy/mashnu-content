"""Thin LLM wrapper. Swap provider here only; the graph never imports an SDK."""
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


class OpenAICompatLLM:
    """Any OpenAI-compatible chat endpoint (xAI Grok, Gemini, Groq, OpenRouter...)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        import httpx

        self.model = model
        self.http = httpx.Client(
            base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60
        )

    def _discover_model(self) -> str:
        """Pick a current text model when the configured one is gone (404). Prefers newest flash."""
        r = self.http.get("/models")
        r.raise_for_status()
        ids = [m["id"].removeprefix("models/") for m in r.json().get("data", [])]
        bad = ("lite", "image", "tts", "live", "audio", "embed", "thinking", "preview", "exp", "vision")
        pool = [i for i in ids if "flash" in i and not any(b in i for b in bad)] or \
               [i for i in ids if i.startswith("gemini") and not any(b in i for b in bad)] or ids
        if not pool:
            raise RuntimeError(f"no usable models returned: {ids[:10]}")
        return sorted(pool, reverse=True)[0]

    def _post(self, system: str, user: str):
        return self.http.post(
            "/chat/completions",
            json={
                "model": self.model,
                "max_tokens": 1500,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )

    def complete(self, system: str, user: str) -> str:
        r = self._post(system, user)
        if r.status_code == 404:  # configured model unavailable: discover one and retry once
            self.model = self._discover_model()
            print(f"[llm] model not found, using {self.model}")
            r = self._post(system, user)
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
