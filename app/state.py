import json
import time
from pathlib import Path
from typing import Dict, Any, Set
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
        try:
            if self.state_file.exists():
                return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[StateManager] Warning: could not parse state file ({e}). Initializing fresh state.")

        initial_timestamp = int((time.time() - self.lookback_hours * 3600) * 1000)
        return {
            "last_run_ms": initial_timestamp,
            "done": []
        }

    def save(self, state: Dict[str, Any], dry_run: bool = False):
        """Saves state to disk (skips if dry_run)."""
        if dry_run:
            return
        # Keep recent 5000 items to avoid file bloating over years
        state["done"] = state.get("done", [])[-5000:]
        self._ensure_dir()
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    @staticmethod
    def make_key(post_id: str, url: str) -> str:
        return f"{post_id}|{url}"
