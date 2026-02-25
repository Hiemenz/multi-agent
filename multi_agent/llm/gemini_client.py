from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def generate(self, prompt: str) -> str:
        """Generate text from a prompt. Runs sync SDK in a thread."""
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=prompt,
            config=self._config,
        )
        return response.text

    async def generate_json(self, prompt: str) -> Any:
        """Generate and parse JSON, stripping markdown fences."""
        raw = await self.generate(prompt)
        cleaned = _strip_markdown_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failed. Raw response:\n%s", raw)
            raise ValueError(f"Gemini returned invalid JSON: {exc}") from exc


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
