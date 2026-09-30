import json
import pytest
from pathlib import Path
from app.state import StateManager


def test_state_manager_save_and_load(tmp_path: Path):
    state_file = tmp_path / "test_state.json"
    manager = StateManager(state_file=state_file, lookback_hours=12)

    # Load from non-existent file returns default
    initial_state = manager.load()
    assert "last_run_ms" in initial_state
    assert initial_state["done"] == []

    # Save state with some entries
    key1 = manager.make_key("post_123", "https://gitlab.com/mr/1")
    key2 = manager.make_key("post_456", "https://github.com/pr/2")
    initial_state["done"].append(key1)
    initial_state["done"].append(key2)
    manager.save(initial_state)

    # Reload state
    reloaded = manager.load()
    assert len(reloaded["done"]) == 2
    assert key1 in reloaded["done"]
    assert key2 in reloaded["done"]
