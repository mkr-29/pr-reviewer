import pytest
from unittest.mock import MagicMock, patch
from app.reviewer.llm import LLMReviewer
from app.git_providers.base import PullRequestDetails


def test_llm_reviewer_fallback_retry():
    reviewer = LLMReviewer()

    pr = PullRequestDetails(
        provider="gitlab",
        url="https://gitlab.com/acme/backend/-/merge_requests/10",
        id="10",
        title="feat: backend update",
        description="test",
        author="alice",
        source_branch="feat",
        target_branch="pre-main",
        diff="--- a/test.py\n+++ b/test.py\n+x = 1"
    )

    # Mock get_providers to return [("primary", fail_fn), ("secondary", success_fn)]
    fail_fn = MagicMock(side_effect=RuntimeError("Primary provider 429 Rate Limit"))
    success_fn = MagicMock(return_value="## Review Verdict: GOOD\nAll tests pass.")

    with patch.object(reviewer, "get_providers", return_value=[("primary", fail_fn), ("secondary", success_fn)]):
        result = reviewer.review_pr(pr)
        assert "Verdict: GOOD" in result
        fail_fn.assert_called_once()
        success_fn.assert_called_once()


def test_llm_reviewer_all_fail():
    reviewer = LLMReviewer()

    pr = PullRequestDetails(
        provider="gitlab",
        url="https://gitlab.com/acme/backend/-/merge_requests/10",
        id="10",
        title="feat: backend update",
        description="test",
        author="alice",
        source_branch="feat",
        target_branch="pre-main",
        diff="--- a/test.py\n+++ b/test.py\n+x = 1"
    )

    fail1 = MagicMock(side_effect=RuntimeError("Provider 1 Timeout"))
    fail2 = MagicMock(side_effect=RuntimeError("Provider 2 500 Internal Error"))

    with patch.object(reviewer, "get_providers", return_value=[("p1", fail1), ("p2", fail2)]):
        with pytest.raises(RuntimeError) as exc_info:
            reviewer.review_pr(pr)
        assert "All configured LLM providers failed" in str(exc_info.value)
        assert "Provider 1 Timeout" in str(exc_info.value)
        assert "Provider 2 500 Internal Error" in str(exc_info.value)
