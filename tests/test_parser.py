import pytest
from app.mattermost import MattermostClient
from app.git_providers.resolver import GitResolver


def test_mention_regex_exact_match():
    regex = MattermostClient.build_mention_regex("mayank")

    assert regex.search("Hey @mayank, please check this MR") is not None
    assert regex.search("@mayank check this out") is not None
    assert regex.search("cc: @mayank: done") is not None
    assert regex.search("Hello @MAYANK please review") is not None

    # Negative matches
    assert regex.search("Hey @mayank27, check this") is None
    assert regex.search("Email is mayank@example.com") is None
    assert regex.search("Hey @notmayank please review") is None


def test_git_url_extraction():
    resolver = GitResolver()

    sample_text = """
    Hi @mayank, here is the update:
    1. GitLab MR: https://gitlab.internal.net/team-core/platform-api/-/merge_requests/452
    2. Another GitLab MR: https://gitlab.com/acme/project/-/merge_requests/89
    3. GitHub PR: https://github.com/my-org/web-service/pull/1204
    4. Duplicate of first: https://gitlab.internal.net/team-core/platform-api/-/merge_requests/452
    Thanks!
    """

    urls = resolver.extract_pr_urls(sample_text)
    assert len(urls) == 3
    assert urls[0] == "https://gitlab.internal.net/team-core/platform-api/-/merge_requests/452"
    assert urls[1] == "https://gitlab.com/acme/project/-/merge_requests/89"
    assert urls[2] == "https://github.com/my-org/web-service/pull/1204"

    assert resolver.detect_provider(urls[0]) == "gitlab"
    assert resolver.detect_provider(urls[2]) == "github"
