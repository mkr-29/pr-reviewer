import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from working directory if present
load_dotenv()


def _clean_env(key: str, default: str = "") -> str:
    val = os.environ.get(key, default)
    if val is None:
        return ""
    val = str(val).strip()
    if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
        val = val[1:-1].strip()
    return val


class Config:
    # Mattermost Configuration
    MM_URL: str = _clean_env("MM_URL", "").rstrip("/")
    MM_TOKEN: str = _clean_env("MM_TOKEN", "")
    MM_CHANNEL_NAME: str = _clean_env("MM_CHANNEL_NAME", "Daily Task Update")
    MM_CHANNEL_ID: str = _clean_env("MM_CHANNEL_ID", "")
    MM_TARGET_USERNAME: str = _clean_env("MM_TARGET_USERNAME", "")
    MM_TARGET_USER_IDS: str = _clean_env("MM_TARGET_USER_IDS", "")

    # Target Branch Gate & Project Filtering
    TARGET_BRANCH: str = _clean_env("TARGET_BRANCH", "pre-main")
    REPO_FILTER: str = _clean_env("REPO_FILTER", "").lower()

    # State & Persistence
    STATE_FILE: Path = Path(_clean_env("STATE_FILE", "data/state.json"))
    LOOKBACK_HOURS: float = float(_clean_env("LOOKBACK_HOURS", "24.0"))

    # Scheduler Settings
    POLL_INTERVAL_HOURS: int = int(_clean_env("POLL_INTERVAL_HOURS", "1"))
    SCHEDULE_TIME: str = _clean_env("SCHEDULE_TIME", "20:00")
    SCHEDULE_TIMEZONE: str = _clean_env("SCHEDULE_TIMEZONE", "Asia/Kolkata")

    # GitLab Configuration
    GITLAB_URL: str = _clean_env("GITLAB_URL", "https://gitlab.com").rstrip("/")
    GITLAB_TOKEN: str = _clean_env("GITLAB_TOKEN", "")

    # GitHub Configuration
    GITHUB_URL: str = _clean_env("GITHUB_URL", "https://api.github.com").rstrip("/")
    GITHUB_TOKEN: str = _clean_env("GITHUB_TOKEN", "")

    # LLM Settings & Multi-Provider Fallback
    LLM_PROVIDER: str = _clean_env("LLM_PROVIDER", "auto").lower()

    # Google Gemini
    GEMINI_API_KEY: str = _clean_env("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = _clean_env("GEMINI_MODEL", "gemini-2.5-flash")

    # Groq API
    GROQ_API_KEY: str = _clean_env("GROQ_API_KEY", "")
    GROQ_MODEL: str = _clean_env("GROQ_MODEL", "openai/gpt-oss-120b")

    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str = _clean_env("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT: str = _clean_env("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    AZURE_OPENAI_DEPLOYMENT: str = _clean_env("AZURE_OPENAI_DEPLOYMENT", "gpt-5.5")
    AZURE_OPENAI_API_VERSION: str = _clean_env("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    # Inception Labs API
    INCEPTION_API_KEY: str = _clean_env("INCEPTION_API_KEY", "")
    INCEPTION_MODEL: str = _clean_env("INCEPTION_MODEL", "mercury-2")

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = _clean_env("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = _clean_env("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # OpenAI / Cursor compatible
    OPENAI_API_KEY: str = _clean_env("OPENAI_API_KEY") or _clean_env("CURSOR_API_KEY", "")
    OPENAI_BASE_URL: str = _clean_env("OPENAI_BASE_URL", "").rstrip("/")
    OPENAI_MODEL: str = _clean_env("OPENAI_MODEL", "gpt-4o")

    # Additional Providers
    THINKING_MACHINE_API_KEY: str = _clean_env("THINKING_MACHINE_API_KEY", "")
    SARVAM_API_KEY: str = _clean_env("SARVAM_API_KEY", "")
    ARCEE_API_KEY: str = _clean_env("ARCEE_API_KEY", "")
    LONGCAT_API_KEY: str = _clean_env("LONGCAT_API_KEY", "")

    LLM_TIMEOUT: int = int(os.environ.get("LLM_TIMEOUT", "600"))

    @classmethod
    def validate_for_live_run(cls):
        """Validates that necessary environment variables are provided for a live run."""
        missing = []
        if not cls.MM_URL:
            missing.append("MM_URL")
        if not cls.MM_TOKEN:
            missing.append("MM_TOKEN")
        has_any_llm = any([
            cls.GEMINI_API_KEY,
            cls.GROQ_API_KEY,
            cls.AZURE_OPENAI_API_KEY,
            cls.INCEPTION_API_KEY,
            cls.ANTHROPIC_API_KEY,
            cls.OPENAI_API_KEY
        ])
        if not has_any_llm:
            missing.append("At least one LLM key: GEMINI_API_KEY, GROQ_API_KEY, AZURE_OPENAI_API_KEY, INCEPTION_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
