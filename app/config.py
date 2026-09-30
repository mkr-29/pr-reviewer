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

    # Target Branch Gate
    TARGET_BRANCH: str = _clean_env("TARGET_BRANCH", "pre-main")

    # State & Persistence
    STATE_FILE: Path = Path(_clean_env("STATE_FILE", "data/state.json"))
    LOOKBACK_HOURS: float = float(_clean_env("LOOKBACK_HOURS", "24.0"))

    # Scheduler Settings
    SCHEDULE_TIME: str = _clean_env("SCHEDULE_TIME", "20:00")
    SCHEDULE_TIMEZONE: str = _clean_env("SCHEDULE_TIMEZONE", "Asia/Kolkata")

    # GitLab Configuration
    GITLAB_URL: str = _clean_env("GITLAB_URL", "https://gitlab.com").rstrip("/")
    GITLAB_TOKEN: str = _clean_env("GITLAB_TOKEN", "")

    # GitHub Configuration
    GITHUB_URL: str = _clean_env("GITHUB_URL", "https://api.github.com").rstrip("/")
    GITHUB_TOKEN: str = _clean_env("GITHUB_TOKEN", "")

    # LLM Settings
    LLM_PROVIDER: str = _clean_env("LLM_PROVIDER", "auto").lower()  # auto, gemini, anthropic, openai
    GEMINI_API_KEY: str = _clean_env("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = _clean_env("GEMINI_MODEL", "gemini-2.5-flash")

    ANTHROPIC_API_KEY: str = _clean_env("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = _clean_env("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    OPENAI_API_KEY: str = _clean_env("OPENAI_API_KEY") or _clean_env("CURSOR_API_KEY", "")
    OPENAI_BASE_URL: str = _clean_env("OPENAI_BASE_URL", "").rstrip("/")
    OPENAI_MODEL: str = _clean_env("OPENAI_MODEL", "gpt-4o")

    LLM_TIMEOUT: int = int(os.environ.get("LLM_TIMEOUT", "600"))

    @classmethod
    def validate_for_live_run(cls):
        """Validates that necessary environment variables are provided for a live run."""
        missing = []
        if not cls.MM_URL:
            missing.append("MM_URL")
        if not cls.MM_TOKEN:
            missing.append("MM_TOKEN")
        if not any([cls.GEMINI_API_KEY, cls.ANTHROPIC_API_KEY, cls.OPENAI_API_KEY]):
            missing.append("At least one LLM key: GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY/CURSOR_API_KEY")
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
