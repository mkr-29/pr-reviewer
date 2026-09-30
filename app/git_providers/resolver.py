import re
from typing import List, Tuple, Optional
from app.config import Config
from app.git_providers.base import PullRequestDetails
from app.git_providers.gitlab_client import GitLabClient
from app.git_providers.github_client import GitHubClient


class GitResolver:
    # URL patterns for GitLab MRs and GitHub PRs
    GITLAB_MR_RE = re.compile(r"https?://[^\s<>()\[\]\"']+?/-/merge_requests/\d+")
    GITHUB_PR_RE = re.compile(r"https?://github\.com/[^\s<>()\[\]\"']+?/[^\s<>()\[\]\"']+?/pull/\d+")

    def __init__(self, gitlab_client: Optional[GitLabClient] = None, github_client: Optional[GitHubClient] = None):
        self.gitlab = gitlab_client or GitLabClient()
        self.github = github_client or GitHubClient()

    def extract_pr_urls(self, text: str) -> List[str]:
        """Extracts unique GitLab MR and GitHub PR URLs from freeform text in order of appearance."""
        urls = []
        seen = set()

        for match in re.finditer(rf"{self.GITLAB_MR_RE.pattern}|{self.GITHUB_PR_RE.pattern}", text):
            url = match.group(0)
            if url not in seen:
                seen.add(url)
                urls.append(url)

        return urls

    def detect_provider(self, url: str) -> str:
        """Determines whether a URL belongs to GitLab or GitHub."""
        if "/-/merge_requests/" in url:
            return "gitlab"
        if "github.com" in url and "/pull/" in url:
            return "github"
        raise ValueError(f"Unsupported Git provider URL: {url}")

    def get_details(self, url: str) -> PullRequestDetails:
        """Fetches full details and diff from the appropriate provider."""
        provider = self.detect_provider(url)
        if provider == "gitlab":
            return self.gitlab.get_mr_details(url)
        elif provider == "github":
            return self.github.get_pr_details(url)
        raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def validate_target_branch(pr: PullRequestDetails, required_branch: str = Config.TARGET_BRANCH) -> Tuple[bool, str]:
        """
        Validates if PR targets the required branch (supports single branch or comma-separated list like pre-main,staging).
        Returns (is_valid, actual_branch).
        """
        actual = pr.target_branch.strip()
        allowed = [b.strip() for b in required_branch.split(",") if b.strip()]
        return (actual in allowed, actual)
