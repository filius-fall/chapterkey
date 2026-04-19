"""Provider adapters for embeddings, chat, and OCR."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class ProviderConfig:
    """Decrypted provider settings."""

    id: int
    name: str
    provider_type: str
    api_key: str
    base_url: str | None
    default_embedding_model: str | None
    default_chat_model: str | None
    default_ocr_model: str | None


class ProviderError(RuntimeError):
    """Provider request error."""


class BaseProvider:
    """Provider interface."""

    def embed_texts(
        self,
        config: ProviderConfig,
        model: str,
        texts: list[str],
        purpose: str = "document",
    ) -> list[list[float]]:
        raise NotImplementedError

    def chat(
        self,
        config: ProviderConfig,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        raise NotImplementedError

    def ocr_images(
        self,
        config: ProviderConfig,
        model: str,
        images: list[tuple[str, bytes]],
    ) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseProvider):
    """Generic OpenAI-compatible provider."""

    default_base_url = "https://openrouter.ai/api/v1"

    def _base_url(self, config: ProviderConfig) -> str:
        return (config.base_url or self.default_base_url).rstrip("/")

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return headers

    def embed_texts(
        self,
        config: ProviderConfig,
        model: str,
        texts: list[str],
        purpose: str = "document",
    ) -> list[list[float]]:
        """Generate embeddings with batching to handle large inputs."""
        del purpose
        batch_size = 50
        all_embeddings: list[list[float]] = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = requests.post(
                f"{self._base_url(config)}/embeddings",
                headers=self._headers(config),
                json={"model": model, "input": batch, "encoding_format": "float"},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            if "data" not in payload:
                raise ProviderError(f"Unexpected API response: {payload}")
            batch_embeddings = [item["embedding"] for item in payload["data"]]
            all_embeddings.extend(batch_embeddings)
        
        return all_embeddings

    def chat(
        self,
        config: ProviderConfig,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        response = requests.post(
            f"{self._base_url(config)}/chat/completions",
            headers=self._headers(config),
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def ocr_images(
        self,
        config: ProviderConfig,
        model: str,
        images: list[tuple[str, bytes]],
    ) -> str:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Extract the readable text from these book pages. Preserve chapter/page order. "
                    "If this is manga, comics, or image-heavy content, describe panel text faithfully "
                    "without adding summaries."
                ),
            }
        ]
        for mime_type, image_bytes in images:
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                }
            )
        return self.chat(
            config,
            model,
            [{"role": "user", "content": content}],
            temperature=0.0,
            max_tokens=4000,
        )


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama OpenAI-compatible provider."""

    default_base_url = "http://127.0.0.1:11434/v1"

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if config.api_key and config.api_key not in {"", "ollama"}:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return headers


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter provider."""

    default_base_url = "https://openrouter.ai/api/v1"


class AnthropicProvider(BaseProvider):
    """Anthropic chat and vision provider."""

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        return {
            "x-api-key": config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def embed_texts(
        self,
        config: ProviderConfig,
        model: str,
        texts: list[str],
        purpose: str = "document",
    ) -> list[list[float]]:
        del config, model, texts, purpose
        raise ProviderError("Anthropic does not provide embeddings in this application")

    def chat(
        self,
        config: ProviderConfig,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        anthropic_messages: list[dict[str, Any]] = []
        system_parts: list[str] = []
        for message in messages:
            if message["role"] == "system":
                system_parts.append(str(message["content"]))
                continue
            anthropic_messages.append(message)
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        response = requests.post(
            (config.base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages",
            headers=self._headers(config),
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        parts = [item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"]
        return "\n".join(parts).strip()

    def ocr_images(
        self,
        config: ProviderConfig,
        model: str,
        images: list[tuple[str, bytes]],
    ) -> str:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": "Extract all readable text from these book pages in order."}
        ]
        for mime_type, image_bytes in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(image_bytes).decode("utf-8"),
                    },
                }
            )
        return self.chat(
            config,
            model,
            [{"role": "user", "content": content}],
            temperature=0.0,
            max_tokens=4000,
        )


class GoogleProvider(BaseProvider):
    """Google Gemini REST provider."""

    def _url(self, config: ProviderConfig, suffix: str) -> str:
        base = (config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        return f"{base}/{suffix}?key={config.api_key}"

    def embed_texts(
        self,
        config: ProviderConfig,
        model: str,
        texts: list[str],
        purpose: str = "document",
    ) -> list[list[float]]:
        del purpose
        embeddings: list[list[float]] = []
        for text in texts:
            response = requests.post(
                self._url(config, f"models/{model}:embedContent"),
                headers={"Content-Type": "application/json"},
                json={"content": {"parts": [{"text": text}]}},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            embeddings.append(payload["embedding"]["values"])
        return embeddings

    def chat(
        self,
        config: ProviderConfig,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        prompt_parts: list[str] = []
        for message in messages:
            role = message["role"]
            content = message["content"]
            if isinstance(content, str):
                prompt_parts.append(f"{role.upper()}: {content}")
            else:
                prompt_parts.append(f"{role.upper()}: {json.dumps(content)}")
        response = requests.post(
            self._url(config, f"models/{model}:generateContent"),
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": "\n\n".join(prompt_parts)}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["candidates"][0]["content"]["parts"][0]["text"]

    def ocr_images(
        self,
        config: ProviderConfig,
        model: str,
        images: list[tuple[str, bytes]],
    ) -> str:
        parts: list[dict[str, Any]] = [{"text": "Extract all readable text from these book pages in order."}]
        for mime_type, image_bytes in images:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(image_bytes).decode("utf-8"),
                    },
                }
            )
        response = requests.post(
            self._url(config, f"models/{model}:generateContent"),
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": parts}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 4000},
            },
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["candidates"][0]["content"]["parts"][0]["text"]


class NvidiaNimProvider(BaseProvider):
    """NVIDIA NIM provider with retriever-aware embedding intent."""

    def _base_url(self, config: ProviderConfig) -> str:
        return (config.base_url or "https://integrate.api.nvidia.com/v1").rstrip("/")

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

    def embed_texts(
        self,
        config: ProviderConfig,
        model: str,
        texts: list[str],
        purpose: str = "document",
    ) -> list[list[float]]:
        """Generate embeddings with batching to handle large inputs and rate limits."""
        import time
        batch_size = 50  # NVIDIA rate limit friendly batch size
        all_embeddings: list[list[float]] = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = requests.post(
                f"{self._base_url(config)}/embeddings",
                headers=self._headers(config),
                json={
                    "model": model,
                    "input": batch,
                    "input_type": "query" if purpose == "query" else "passage",
                    "encoding_format": "float",
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            if "data" not in payload:
                raise ProviderError(f"Unexpected API response: {payload}")
            batch_embeddings = [item["embedding"] for item in payload["data"]]
            all_embeddings.extend(batch_embeddings)
            
            # Rate limiting: small delay between batches
            if i + batch_size < len(texts):
                time.sleep(0.5)
        
        return all_embeddings

    def chat(
        self,
        config: ProviderConfig,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        response = requests.post(
            f"{self._base_url(config)}/chat/completions",
            headers=self._headers(config),
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def ocr_images(
        self,
        config: ProviderConfig,
        model: str,
        images: list[tuple[str, bytes]],
    ) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": "Extract all readable text from these book pages in order."}]
        for mime_type, image_bytes in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}",
                    },
                }
            )
        return self.chat(
            config,
            model,
            [{"role": "user", "content": content}],
            temperature=0.0,
            max_tokens=4000,
        )


class ProviderRegistry:
    """Map provider types to implementations."""

    def __init__(self):
        self.providers = {
            "openai_compatible": OpenAICompatibleProvider(),
            "openrouter": OpenRouterProvider(),
            "ollama": OllamaProvider(),
            "anthropic": AnthropicProvider(),
            "google": GoogleProvider(),
            "nvidia_nim": NvidiaNimProvider(),
        }

    def get(self, provider_type: str) -> BaseProvider:
        try:
            return self.providers[provider_type]
        except KeyError as exc:
            raise ProviderError(f"Unsupported provider type: {provider_type}") from exc
