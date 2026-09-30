import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from working directory if present
load_dotenv()


class Config:
    # Mattermost Configuration
    MM_URL: str = os.environ.get("MM_URL", "").rstrip("/")
    MM_TOKEN: str = os.environ.get("MM_TOKEN", "")
    MM_CHANNEL_NAME: str = os.environ.get("MM_CHANNEL_NAME", "Daily Task Update")
    MM_CHANNEL_ID: str = os.environ.get("MM_CHANNEL_ID", "")

    # Target Branch Gate
    TARGET_BRANCH: str = os.environ.get("TARGET_BRANCH", "pre-main")

    # State & Persistence
    STATE_FILE: Path = Path(os.environ.get("STATE_FILE", "data/state.json"))
    LOOKBACK_HOURS: float = float(os.environ.get("LOOKBACK_HOURS", "24.0"))

    # Scheduler Settings
    SCHEDULE_TIME: str = os.environ.get("SCHEDULE_TIME", "20:00")
    SCHEDULE_TIMEZONE: str = os.environ.get("SCHEDULE_TIMEZONE", "Asia/Kolkata")

    # GitLab Configuration
    GITLAB_URL: str = os.environ.get("GITLAB_URL", "https://gitlab.com").rstrip("/")
    GITLAB_TOKEN: str = os.environ.get("GITLAB_TOKEN", "")

    # GitHub Configuration
    GITHUB_URL: str = os.environ.get("GITHUB_URL", "https://api.github.com").rstrip("/")
    GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

    # LLM Settings
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "auto").lower()  # auto, gemini, anthropic, openai
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY") or os.environ.get("CURSOR_API_KEY", "")
    OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o")

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
