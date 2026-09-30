import os
from typing import Optional
from app.config import Config
from app.git_providers.base import PullRequestDetails
from app.reviewer.rubric import SYSTEM_RUBRIC_PROMPT, build_review_prompt


class LLMReviewer:
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or Config.LLM_PROVIDER).lower()
        self._active_provider = self._resolve_provider()

    def _resolve_provider(self) -> str:
        if self.provider in ["gemini", "google"]:
            return "gemini"
        if self.provider in ["anthropic", "claude"]:
            return "anthropic"
        if self.provider in ["openai", "cursor"]:
            return "openai"

        # Auto detection based on available API keys
        if Config.GEMINI_API_KEY:
            return "gemini"
        if Config.ANTHROPIC_API_KEY:
            return "anthropic"
        if Config.OPENAI_API_KEY:
            return "openai"

        raise ValueError(
            "No LLM API keys configured. Please provide GEMINI_API_KEY, "
            "ANTHROPIC_API_KEY, or OPENAI_API_KEY / CURSOR_API_KEY in .env"
        )

    def review_pr(self, pr: PullRequestDetails) -> str:
        """Executes the review for a given PullRequestDetails and returns the markdown response."""
        prompt = build_review_prompt(pr)

        if self._active_provider == "gemini":
            return self._call_gemini(prompt)
        elif self._active_provider == "anthropic":
            return self._call_anthropic(prompt)
        elif self._active_provider == "openai":
            return self._call_openai(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self._active_provider}")

    def _call_gemini(self, user_prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=Config.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            system_instruction=SYSTEM_RUBRIC_PROMPT
        )
        response = model.generate_content(
            user_prompt,
            generation_config={"temperature": 0.2}
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        return response.text.strip()

    def _call_anthropic(self, user_prompt: str) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=Config.ANTHROPIC_MODEL,
            max_tokens=4096,
            temperature=0.2,
            system=SYSTEM_RUBRIC_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )
        # Extract text content
        text_parts = [block.text for block in message.content if getattr(block, "text", None)]
        result = "".join(text_parts).strip()
        if not result:
            raise RuntimeError("Anthropic returned an empty response.")
        return result

    def _call_openai(self, user_prompt: str) -> str:
        from openai import OpenAI

        client_kwargs = {"api_key": Config.OPENAI_API_KEY}
        if Config.OPENAI_BASE_URL:
            client_kwargs["base_url"] = Config.OPENAI_BASE_URL

        client = OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_RUBRIC_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            timeout=Config.LLM_TIMEOUT
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI/Cursor API returned an empty response.")
        return content.strip()
