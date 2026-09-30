import json
import time
from pathlib import Path
from typing import Dict, Any, Set, Optional
from app.config import Config


class StateManager:
    def __init__(self, state_file: Path = Config.STATE_FILE, lookback_hours: float = Config.LOOKBACK_HOURS):
        self.state_file = state_file
        self.lookback_hours = lookback_hours
        self._ensure_dir()

    def _ensure_dir(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Loads state from disk or initializes defaults."""
        data = {}
        try:
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[StateManager] Warning: could not parse state file ({e}). Initializing fresh state.")

        if not data:
            initial_timestamp = int((time.time() - self.lookback_hours * 3600) * 1000)
            data = {
                "last_run_ms": initial_timestamp,
                "done": [],
                "reviewed_urls": {}
            }
        if "done" not in data:
            data["done"] = []
        if "reviewed_urls" not in data:
            data["reviewed_urls"] = {}
        return data

    def save(self, state: Dict[str, Any], dry_run: bool = False):
        """Saves state to disk (skips if dry_run)."""
        if dry_run:
            return
        # Keep recent 5000 items to avoid file bloating over years
        state["done"] = state.get("done", [])[-5000:]
        reviewed = state.get("reviewed_urls", {})
        if len(reviewed) > 5000:
            recent_keys = list(reviewed.keys())[-5000:]
            state["reviewed_urls"] = {k: reviewed[k] for k in recent_keys}
        self._ensure_dir()
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    @staticmethod
    def make_key(post_id: str, url: str) -> str:
        return f"{post_id}|{url}"

    def is_url_reviewed(self, state: Dict[str, Any], url: str, head_sha: Optional[str] = None) -> bool:
        """Checks if a PR/MR URL has already been reviewed, matching head_sha if provided."""
        reviewed = state.get("reviewed_urls", {})
        if url not in reviewed:
            return False
        info = reviewed[url]
        if isinstance(info, dict):
            saved_sha = info.get("head_sha")
            if head_sha and saved_sha:
                return saved_sha == head_sha
            return True
        return True

    def record_reviewed(
        self,
        state: Dict[str, Any],
        post_id: str,
        url: str,
        head_sha: str = "",
        status: str = "reviewed"
    ):
        """Records an MR/PR as processed both per-post and globally by URL and commit SHA."""
        key = self.make_key(post_id, url)
        if "done" not in state:
            state["done"] = []
        if key not in state["done"]:
            state["done"].append(key)

        if "reviewed_urls" not in state:
            state["reviewed_urls"] = {}
        state["reviewed_urls"][url] = {
            "head_sha": head_sha,
            "status": status,
            "timestamp": int(time.time() * 1000),
            "post_id": post_id
        }
