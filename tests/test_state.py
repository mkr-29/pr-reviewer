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


def test_state_manager_reviewed_urls(tmp_path: Path):
    state_file = tmp_path / "test_state_urls.json"
    manager = StateManager(state_file=state_file)
    state = manager.load()

    url = "https://gitlab.com/acme/backend/-/merge_requests/42"
    head_sha = "abc123456789"

    # Initially not reviewed
    assert manager.is_url_reviewed(state, url) is False
    assert manager.is_url_reviewed(state, url, head_sha) is False

    # Record review
    manager.record_reviewed(state, "post_999", url, head_sha=head_sha, status="reviewed")
    manager.save(state)

    # Check match with correct sha
    assert manager.is_url_reviewed(state, url, head_sha) is True
    # Check match with different sha (new commits pushed)
    assert manager.is_url_reviewed(state, url, "different_sha") is False

    # Reload from disk
    reloaded = manager.load()
    assert manager.is_url_reviewed(reloaded, url, head_sha) is True
    assert "post_999|" + url in reloaded["done"]
