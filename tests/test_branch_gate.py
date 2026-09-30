import pytest
from app.git_providers.base import PullRequestDetails
from app.git_providers.resolver import GitResolver


def test_target_branch_gate():
    resolver = GitResolver()

    # Case 1: Target branch matches pre-main
    valid_pr = PullRequestDetails(
        provider="gitlab",
        url="https://gitlab.com/org/repo/-/merge_requests/10",
        id="10",
        title="Feat: new feature",
        description="Fixes #10",
        author="alice",
        source_branch="feat/new-ui",
        target_branch="pre-main"
    )

    is_valid, branch = resolver.validate_target_branch(valid_pr, "pre-main")
    assert is_valid is True
    assert branch == "pre-main"

    # Case 2: Target branch does NOT match pre-main (e.g. main)
    invalid_pr = PullRequestDetails(
        provider="github",
        url="https://github.com/org/repo/pull/42",
        id="42",
        title="Fix bug",
        description="Fixes #42",
        author="bob",
        source_branch="fix/bug-42",
        target_branch="main"
    )

    is_valid, branch = resolver.validate_target_branch(invalid_pr, "pre-main")
    assert is_valid is False
    assert branch == "main"
