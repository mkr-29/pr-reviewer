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
    mock_mm.has_bot_replied_for_url.return_value = False

    # Pre-configure regex builder to match mock username
    from app.mattermost import MattermostClient
    mock_mm.build_mention_regex.side_effect = MattermostClient.build_mention_regex

    # Posts in channel:
    # Post 1: has backend MR with branch mismatch ('dev')
    # Post 2: has backend PR targeting 'pre-main'
    # Post 3: has frontend PR (should be skipped by REPO_FILTER='backend')
    mock_mm.get_posts_since.return_value = [
        {
            "id": "post_1",
            "user_id": "other_user",
            "message": "Hey @mayank, please check this MR: https://gitlab.com/acme/backend-service/-/merge_requests/10",
            "delete_at": 0
        },
        {
            "id": "post_2",
            "user_id": "other_user",
            "message": "@mayank review this PR please https://github.com/acme/backend-api/pull/20",
            "delete_at": 0
        },
        {
            "id": "post_3",
            "user_id": "other_user",
            "message": "@mayank frontend PR https://github.com/acme/frontend-app/pull/99",
            "delete_at": 0
        }
    ]

    # 2. Setup mock Git resolver
    mock_resolver = MagicMock()
    mock_resolver.extract_pr_urls.side_effect = lambda msg: [
        u for u in [
            "https://gitlab.com/acme/backend-service/-/merge_requests/10",
            "https://github.com/acme/backend-api/pull/20",
            "https://github.com/acme/frontend-app/pull/99"
        ] if u in msg
    ]

    mr_details = PullRequestDetails(
        provider="gitlab",
        url="https://gitlab.com/acme/backend-service/-/merge_requests/10",
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
        url="https://github.com/acme/backend-api/pull/20",
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
    assert "**Automated review for** https://github.com/acme/backend-api/pull/20" in call2[0][2]
    assert "## Verdict: GOOD" in call2[0][2]

    # Verify state saved both keys
    state = state_manager.load()
    assert len(state["done"]) == 2
    assert "post_1|https://gitlab.com/acme/backend-service/-/merge_requests/10" in state["done"]
    assert "post_2|https://github.com/acme/backend-api/pull/20" in state["done"]

    # 6. Run again - should skip both because they are in state!
    mock_mm.reply_in_thread.reset_mock()
    bot.run_once()
    assert mock_mm.reply_in_thread.call_count == 0


def test_reviews_merged_and_approved_mrs(tmp_path):
    mock_mm = MagicMock()
    mock_mm.base_url = "https://mattermost.test"
    mock_mm.token = "mock-pat"
    mock_mm.get_me.return_value = {"id": "uid_1", "username": "mayank"}
    mock_mm.find_channel_id.return_value = "ch_1"
    mock_mm.has_bot_replied_for_url.return_value = False

    from app.mattermost import MattermostClient
    mock_mm.build_mention_regex.side_effect = MattermostClient.build_mention_regex

    mock_mm.get_posts_since.return_value = [
        {"id": "p_merged", "user_id": "u2", "message": "@mayank merged: https://gitlab.com/acme/backend/-/merge_requests/100", "delete_at": 0},
        {"id": "p_approved", "user_id": "u2", "message": "@mayank approved: https://gitlab.com/acme/backend/-/merge_requests/300", "delete_at": 0},
    ]

    mock_resolver = MagicMock()
    mock_resolver.extract_pr_urls.side_effect = lambda msg: [u for u in [
        "https://gitlab.com/acme/backend/-/merge_requests/100",
        "https://gitlab.com/acme/backend/-/merge_requests/300",
    ] if u in msg]

    def mock_get_details(url):
        if "100" in url:
            return PullRequestDetails(
                provider="gitlab", url=url, id="100", title="MR merged", description="",
                author="dev", source_branch="b", target_branch="staging", state="merged", head_sha="sha100"
            )
        else:
            return PullRequestDetails(
                provider="gitlab", url=url, id="300", title="MR approved", description="",
                author="dev", source_branch="b", target_branch="pre-main", state="opened", is_approved=True, head_sha="sha300"
            )

    mock_resolver.get_details.side_effect = mock_get_details
    from app.git_providers.resolver import GitResolver
    mock_resolver.validate_target_branch.side_effect = GitResolver.validate_target_branch

    mock_reviewer = MagicMock()
    mock_reviewer.review_pr.return_value = "Verdict: GOOD"

    state_file = tmp_path / "state_skip.json"
    state_manager = StateManager(state_file=state_file)
    bot = PRReviewBot(
        mm_client=mock_mm,
        state_manager=state_manager,
        git_resolver=mock_resolver,
        reviewer=mock_reviewer,
        dry_run=False,
        target_username="mayank"
    )

    # First run: Both merged and approved MRs SHOULD be reviewed!
    bot.run_once()
    assert mock_mm.reply_in_thread.call_count == 2

    # Check reviews were recorded in state
    state = state_manager.load()
    assert "https://gitlab.com/acme/backend/-/merge_requests/100" in state["reviewed_urls"]
    assert state["reviewed_urls"]["https://gitlab.com/acme/backend/-/merge_requests/100"]["status"] == "reviewed"
    assert "https://gitlab.com/acme/backend/-/merge_requests/300" in state["reviewed_urls"]
    assert state["reviewed_urls"]["https://gitlab.com/acme/backend/-/merge_requests/300"]["status"] == "reviewed"

    # Second run: Since they are already reviewed at those commit SHAs, they should be skipped!
    mock_mm.reply_in_thread.reset_mock()
    bot.run_once()
    assert mock_mm.reply_in_thread.call_count == 0

def test_skips_when_thread_already_replied(tmp_path):
    mock_mm = MagicMock()
    mock_mm.base_url = "https://mattermost.test"
    mock_mm.token = "mock-pat"
    mock_mm.get_me.return_value = {"id": "uid_1", "username": "mayank"}
    mock_mm.find_channel_id.return_value = "ch_1"
    # Thread ALREADY has a reply
    mock_mm.has_bot_replied_for_url.return_value = True

    from app.mattermost import MattermostClient
    mock_mm.build_mention_regex.side_effect = MattermostClient.build_mention_regex

    mock_mm.get_posts_since.return_value = [
        {"id": "p_exist", "user_id": "u2", "message": "@mayank please check: https://gitlab.com/acme/backend/-/merge_requests/400", "delete_at": 0},
    ]

    mock_resolver = MagicMock()
    mock_resolver.extract_pr_urls.return_value = ["https://gitlab.com/acme/backend/-/merge_requests/400"]

    state_file = tmp_path / "state_thread.json"
    state_manager = StateManager(state_file=state_file)
    bot = PRReviewBot(
        mm_client=mock_mm,
        state_manager=state_manager,
        git_resolver=mock_resolver,
        reviewer=MagicMock(),
        dry_run=False,
        target_username="mayank"
    )

    bot.run_once()

    # Should not call git resolver or reply in thread
    assert mock_resolver.get_details.call_count == 0
    assert mock_mm.reply_in_thread.call_count == 0
