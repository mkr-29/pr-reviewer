from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class PullRequestDetails:
    provider: str  # "gitlab" or "github"
    url: str
    id: str  # MR iid or PR number
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    is_draft: bool = False
    has_conflicts: bool = False
    pipeline_status: Optional[str] = None
    diff: str = ""
    changed_files: List[str] = field(default_factory=list)
    linked_issues: List[Dict[str, Any]] = field(default_factory=list)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)
    state: str = "opened"  # "opened" / "open", "merged", "closed"
    head_sha: str = ""
    is_approved: bool = False

    @property
    def is_open(self) -> bool:
        """Returns True if the MR/PR is in an active open state."""
        return self.state.lower() in ("opened", "open")

    def summary(self) -> str:
        return (
            f"[{self.provider.upper()} #{self.id}] {self.title}\n"
            f"Branches: {self.source_branch} -> {self.target_branch}\n"
            f"Status: {self.state} | Draft: {self.is_draft} | Files changed: {len(self.changed_files)}"
        )
