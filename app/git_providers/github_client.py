import re
import requests
from typing import Optional, Dict, Any, List, Tuple
from app.config import Config
from app.git_providers.base import PullRequestDetails


class GitHubClient:
    URL_PATTERN = re.compile(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)")

    def __init__(self, default_token: str = Config.GITHUB_TOKEN):
        self.default_token = default_token
        self.session = requests.Session()

    def parse_url(self, url: str) -> Optional[Tuple[str, str, str]]:
        """Parses a GitHub PR URL into (owner, repo, number)."""
        match = self.URL_PATTERN.match(url)
        if match:
            return match.group(1), match.group(2), match.group(3)
        return None

    def get_headers(self, token: Optional[str] = None, accept: str = "application/vnd.github+json") -> Dict[str, str]:
        t = token or self.default_token
        headers = {
            "Accept": accept,
            "User-Agent": "Mattermost-PR-Reviewer",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if t:
            headers["Authorization"] = f"Bearer {t}"
        return headers

    def get_pr_details(self, url: str, token: Optional[str] = None) -> PullRequestDetails:
        parsed = self.parse_url(url)
        if not parsed:
            raise ValueError(f"Invalid GitHub PR URL: {url}")

        owner, repo, number = parsed
        api_base = f"{Config.GITHUB_URL}/repos/{owner}/{repo}/pulls/{number}"
        headers = self.get_headers(token)

        # 1. Fetch PR metadata
        resp = self.session.get(api_base, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"GitHub API request failed ({resp.status_code}): {resp.text}")
        meta = resp.json()

        # 2. Fetch unified diff
        diff_headers = self.get_headers(token, accept="application/vnd.github.v3.diff")
        diff_resp = self.session.get(api_base, headers=diff_headers, timeout=45)
        diff_text = diff_resp.text if diff_resp.ok else ""

        # 3. Fetch changed files
        files_resp = self.session.get(f"{api_base}/files?per_page=100", headers=headers, timeout=30)
        changed_files = []
        if files_resp.ok:
            files_data = files_resp.json()
            changed_files = [f.get("filename") for f in files_data if isinstance(f, dict)]

        # 4. Extract linked issues from body
        body = meta.get("body", "") or ""
        linked_issues = []
        issue_nums = set(re.findall(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)", body, re.I))
        for num in issue_nums:
            linked_issues.append({"number": num, "title": f"GitHub Issue #{num}"})

        # 5. Check if PR is merged or approved
        state = "merged" if meta.get("merged_at") else meta.get("state", "open")
        is_approved = False
        try:
            rev_resp = self.session.get(f"{api_base}/reviews", headers=headers, timeout=10)
            if rev_resp.ok:
                reviews = rev_resp.json()
                if any(r.get("state") == "APPROVED" for r in reviews if isinstance(r, dict)):
                    is_approved = True
        except Exception:
            pass

        return PullRequestDetails(
            provider="github",
            url=url,
            id=str(number),
            title=meta.get("title", ""),
            description=body,
            author=meta.get("user", {}).get("login", "unknown"),
            source_branch=meta.get("head", {}).get("ref", ""),
            target_branch=meta.get("base", {}).get("ref", ""),
            is_draft=bool(meta.get("draft", False)),
            has_conflicts=meta.get("mergeable") is False,
            pipeline_status=meta.get("mergeable_state"),
            diff=diff_text,
            changed_files=changed_files,
            linked_issues=linked_issues,
            extra_metadata=meta,
            state=state,
            head_sha=meta.get("head", {}).get("sha", ""),
            is_approved=is_approved
        )
