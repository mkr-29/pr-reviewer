"""
Git providers package for GitLab and GitHub pull/merge requests.
"""

from app.git_providers.base import PullRequestDetails
from app.git_providers.resolver import GitResolver

__all__ = ["PullRequestDetails", "GitResolver"]
