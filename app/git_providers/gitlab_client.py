import re
import urllib.parse
import requests
from typing import Optional, Dict, Any, List, Tuple
from app.config import Config
from app.git_providers.base import PullRequestDetails


class GitLabClient:
    URL_PATTERN = re.compile(r"https?://([^/]+)/(.+?)/-/merge_requests/(\d+)")

    def __init__(self, default_token: str = Config.GITLAB_TOKEN):
        self.default_token = default_token
        self.session = requests.Session()

    def parse_url(self, url: str) -> Optional[Tuple[str, str, str]]:
        """Parses a GitLab MR URL into (host, project_path, iid)."""
        match = self.URL_PATTERN.match(url)
        if match:
            return match.group(1), match.group(2), match.group(3)
        return None

    def get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        t = token or self.default_token
        headers = {"User-Agent": "Mattermost-PR-Reviewer"}
        if t:
            headers["PRIVATE-TOKEN"] = t
        return headers

    def get_mr_details(self, url: str, token: Optional[str] = None) -> PullRequestDetails:
        parsed = self.parse_url(url)
        if not parsed:
            raise ValueError(f"Invalid GitLab MR URL: {url}")

        host, project_path, iid = parsed
        api_base = f"https://{host}/api/v4"
        project_enc = urllib.parse.quote(project_path, safe="")
        headers = self.get_headers(token)

        # 1. Fetch MR metadata
        meta_url = f"{api_base}/projects/{project_enc}/merge_requests/{iid}"
        resp = self.session.get(meta_url, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"GitLab API request failed ({resp.status_code}): {resp.text}")
        meta = resp.json()

        # 2. Fetch diff
        diff_text = self._fetch_diff(api_base, project_enc, iid, url, headers)

        # 3. Fetch changed files
        files_resp = self.session.get(f"{meta_url}/diffs?per_page=100", headers=headers, timeout=30)
        changed_files = []
        if files_resp.ok:
            diffs = files_resp.json()
            changed_files = [d.get("new_path") or d.get("old_path") for d in diffs if isinstance(d, dict)]

        # 4. Fetch linked issues
        linked_issues = self._fetch_linked_issues(meta_url, meta.get("description", ""), headers)

        pipeline = meta.get("head_pipeline") or {}
        pipeline_status = pipeline.get("status")

        # 5. Fetch approval status
        is_approved = False
        try:
            appr_resp = self.session.get(f"{meta_url}/approvals", headers=headers, timeout=10)
            if appr_resp.ok:
                appr_data = appr_resp.json()
                approved_by = appr_data.get("approved_by", [])
                if approved_by and len(approved_by) > 0:
                    is_approved = True
                elif appr_data.get("approvals_required", 0) > 0 and appr_data.get("approvals_left", 1) == 0:
                    is_approved = True
        except Exception:
            pass

        return PullRequestDetails(
            provider="gitlab",
            url=url,
            id=str(iid),
            title=meta.get("title", ""),
            description=meta.get("description", "") or "",
            author=meta.get("author", {}).get("username", "unknown"),
            source_branch=meta.get("source_branch", ""),
            target_branch=meta.get("target_branch", ""),
            is_draft=bool(meta.get("draft") or meta.get("work_in_progress")),
            has_conflicts=bool(meta.get("has_conflicts", False)),
            pipeline_status=pipeline_status,
            diff=diff_text,
            changed_files=changed_files,
            linked_issues=linked_issues,
            extra_metadata=meta,
            state=meta.get("state", "opened"),
            head_sha=meta.get("sha", ""),
            is_approved=is_approved
        )

    def _fetch_diff(self, api_base: str, project_enc: str, iid: str, web_url: str, headers: Dict[str, str]) -> str:
        # Try raw diff endpoint
        raw_diff_url = f"{api_base}/projects/{project_enc}/merge_requests/{iid}/raw_diff"
        try:
            resp = self.session.get(raw_diff_url, headers=headers, timeout=45)
            if resp.ok and resp.text.strip():
                return resp.text
        except Exception:
            pass

        # Try .diff suffix on web URL
        try:
            diff_url = f"{web_url}.diff"
            resp = self.session.get(diff_url, headers=headers, timeout=45)
            if resp.ok and resp.text.strip():
                return resp.text
        except Exception:
            pass

        # Fallback: assemble from /diffs endpoint
        try:
            diffs_url = f"{api_base}/projects/{project_enc}/merge_requests/{iid}/diffs?per_page=100"
            resp = self.session.get(diffs_url, headers=headers, timeout=45)
            if resp.ok:
                diffs = resp.json()
                chunks = []
                for d in diffs:
                    path = d.get("new_path") or d.get("old_path", "unknown")
                    diff_content = d.get("diff", "")
                    chunks.append(f"--- a/{path}\n+++ b/{path}\n{diff_content}")
                return "\n".join(chunks)
        except Exception:
            pass

        return ""

    def _fetch_linked_issues(self, mr_url: str, description: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        issues = []
        try:
            resp = self.session.get(f"{mr_url}/closes_issues", headers=headers, timeout=20)
            if resp.ok:
                issues = resp.json()
        except Exception:
            pass

        # Fallback to description regex if empty
        if not issues and description:
            nums = set(re.findall(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|implement[sd]?)\s*:?\s*#(\d+)", description, re.I))
            for num in nums:
                issues.append({"iid": num, "title": f"Issue #{num} (referenced in description)"})

        return issues
