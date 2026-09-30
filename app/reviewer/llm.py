import os
import sys
import time
import requests
from typing import Optional, List, Tuple, Callable
from app.config import Config
from app.git_providers.base import PullRequestDetails
from app.reviewer.rubric import SYSTEM_RUBRIC_PROMPT, build_review_prompt


def log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    print(f"{timestamp} [LLM] {msg}", file=sys.stderr, flush=True)


class LLMReviewer:
    def __init__(self, provider: Optional[str] = None):
        self.preferred_provider = (provider or Config.LLM_PROVIDER).lower()

    def get_providers(self) -> List[Tuple[str, Callable[[str], str]]]:
        """Returns prioritized list of (provider_name, call_fn) for automatic fallback."""
        all_available: dict[str, Callable[[str], str]] = {}

        if Config.GEMINI_API_KEY:
            all_available["gemini"] = self._call_gemini
        if Config.GROQ_API_KEY:
            all_available["groq"] = self._call_groq
        if Config.AZURE_OPENAI_API_KEY and Config.AZURE_OPENAI_ENDPOINT:
            all_available["azure"] = self._call_azure
        if Config.INCEPTION_API_KEY:
            all_available["inception"] = self._call_inception
        if Config.OPENAI_API_KEY:
            all_available["openai"] = self._call_openai
        if Config.ANTHROPIC_API_KEY:
            all_available["anthropic"] = self._call_anthropic

        if not all_available:
            raise ValueError(
                "No LLM API keys configured. Please configure at least one in .env "
                "(GEMINI_API_KEY, GROQ_API_KEY, AZURE_OPENAI_API_KEY, INCEPTION_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)"
            )

        ordered: List[Tuple[str, Callable[[str], str]]] = []
        preferred = self.preferred_provider
        if preferred in all_available:
            ordered.append((preferred, all_available[preferred]))

        for name, fn in all_available.items():
            if name != preferred:
                ordered.append((name, fn))

        return ordered

    def review_pr(self, pr: PullRequestDetails) -> str:
        """
        Executes the review for a given PullRequestDetails and returns markdown response.
        If a provider fails (e.g. rate limit, 404, or timeout), it automatically retries
        with the next available provider in the chain.
        """
        prompt = build_review_prompt(pr)
        providers = self.get_providers()
        errors: List[str] = []

        for name, call_fn in providers:
            try:
                log(f"Attempting review with LLM provider: '{name}'...")
                res = call_fn(prompt)
                if res and res.strip():
                    log(f"Successfully generated review with provider '{name}'.")
                    return res.strip()
            except Exception as e:
                log(f"Provider '{name}' failed: {e}. Retrying next available provider...")
                errors.append(f"{name}: {e}")

        raise RuntimeError(f"All configured LLM providers failed to generate review. Errors: {'; '.join(errors)}")

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

    def _call_groq(self, user_prompt: str) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {Config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": Config.GROQ_MODEL,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_RUBRIC_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=Config.LLM_TIMEOUT)
        if not res.ok:
            raise RuntimeError(f"Groq API error ({res.status_code}): {res.text}")
        data = res.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise RuntimeError("Groq API returned an empty response.")
        return content.strip()

    def _call_azure(self, user_prompt: str) -> str:
        endpoint = Config.AZURE_OPENAI_ENDPOINT.rstrip("/")
        url = f"{endpoint}/openai/deployments/{Config.AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={Config.AZURE_OPENAI_API_VERSION}"
        headers = {
            "api-key": Config.AZURE_OPENAI_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_RUBRIC_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=Config.LLM_TIMEOUT)
        if not res.ok:
            raise RuntimeError(f"Azure OpenAI error ({res.status_code}): {res.text}")
        data = res.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise RuntimeError("Azure OpenAI returned an empty response.")
        return content.strip()

    def _call_inception(self, user_prompt: str) -> str:
        url = "https://api.inceptionlabs.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {Config.INCEPTION_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": Config.INCEPTION_MODEL,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_RUBRIC_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=Config.LLM_TIMEOUT)
        if not res.ok:
            raise RuntimeError(f"Inception API error ({res.status_code}): {res.text}")
        data = res.json()
        content = data["choices"][0]["message"]["content"]
        if not content:
            raise RuntimeError("Inception API returned an empty response.")
        return content.strip()

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
