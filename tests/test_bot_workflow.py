import pytest
from unittest.mock import MagicMock
from app.config import Config
from app.bot import PRReviewBot
from app.state import StateManager
from app.git_providers.base import PullRequestDetails


def test_bot_workflow_end_to_end(tmp_path):
    # 1. Setup mock Mattermost client
    mock_mm = MagicMock()
    mock_mm.base_url = "https://mattermost.test"
    mock_mm.token = "mock-pat-token"
    mock_mm.get_me.return_value = {"id": "user_123", "username": "mayank"}
    mock_mm.find_channel_id.return_value = "channel_456"

    # Pre-configure regex builder to match mock username
    from app.mattermost import MattermostClient
    mock_mm.build_mention_regex.side_effect = MattermostClient.build_mention_regex

    # Posts in channel:
    # Post 1: has MR with branch mismatch ('dev')
    # Post 2: has PR targeting 'pre-main'
    mock_mm.get_posts_since.return_value = [
        {
            "id": "post_1",
            "user_id": "other_user",
            "message": "Hey @mayank, please check this MR: https://gitlab.com/acme/proj/-/merge_requests/10",
            "delete_at": 0
        },
        {
            "id": "post_2",
            "user_id": "other_user",
            "message": "@mayank review this PR please https://github.com/acme/repo/pull/20",
            "delete_at": 0
        }
    ]

    # 2. Setup mock Git resolver
    mock_resolver = MagicMock()
    mock_resolver.extract_pr_urls.side_effect = lambda msg: [
        u for u in [
            "https://gitlab.com/acme/proj/-/merge_requests/10",
            "https://github.com/acme/repo/pull/20"
        ] if u in msg
    ]

    mr_details = PullRequestDetails(
        provider="gitlab",
        url="https://gitlab.com/acme/proj/-/merge_requests/10",
        id="10",
        title="MR feature",
        description="description",
        author="alice",
        source_branch="feat/test",
        target_branch="dev",  # Mismatch!
        diff="--- a/file.py\n+++ b/file.py\n+print('hello')"
    )

    pr_details = PullRequestDetails(
        provider="github",
        url="https://github.com/acme/repo/pull/20",
        id="20",
        title="PR fix",
        description="description",
        author="bob",
        source_branch="fix/bug",
        target_branch="pre-main",  # Valid!
        diff="--- a/file.py\n+++ b/file.py\n+x = 1"
    )

    def mock_get_details(url):
        if "merge_requests" in url:
            return mr_details
        return pr_details

    mock_resolver.get_details.side_effect = mock_get_details
    from app.git_providers.resolver import GitResolver
    mock_resolver.validate_target_branch.side_effect = GitResolver.validate_target_branch

    # 3. Setup mock Reviewer
    mock_reviewer = MagicMock()
    mock_reviewer.review_pr.return_value = "## Verdict: GOOD\n\nClean implementation and well-tested."

    # 4. Setup State Manager
    state_file = tmp_path / "state.json"
    state_manager = StateManager(state_file=state_file)

    # 5. Initialize Bot with dry_run=False to test calling reply_in_thread
    bot = PRReviewBot(
        mm_client=mock_mm,
        state_manager=state_manager,
        git_resolver=mock_resolver,
        reviewer=mock_reviewer,
        dry_run=False,
        target_username="mayank"
    )

    bot.run_once()

    # Verify replies
    assert mock_mm.reply_in_thread.call_count == 2

    # Call 1: Branch mismatch warning
    call1 = mock_mm.reply_in_thread.call_args_list[0]
    assert call1[0][0] == "channel_456"
    assert call1[0][1]["id"] == "post_1"
    assert ":warning:" in call1[0][2]
    assert "targets `dev`, not `pre-main`" in call1[0][2]

    # Call 2: Full review
    call2 = mock_mm.reply_in_thread.call_args_list[1]
    assert call2[0][0] == "channel_456"
    assert call2[0][1]["id"] == "post_2"
    assert "**Automated review for** https://github.com/acme/repo/pull/20" in call2[0][2]
    assert "## Verdict: GOOD" in call2[0][2]

    # Verify state saved both keys
    state = state_manager.load()
    assert len(state["done"]) == 2
    assert "post_1|https://gitlab.com/acme/proj/-/merge_requests/10" in state["done"]
    assert "post_2|https://github.com/acme/repo/pull/20" in state["done"]

    # 6. Run again - should skip both because they are in state!
    mock_mm.reply_in_thread.reset_mock()
    bot.run_once()
    assert mock_mm.reply_in_thread.call_count == 0
