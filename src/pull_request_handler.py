"""
This module contains functions for handling pull requests from GitHub webhooks.

It provides functions to get existing PRs, create new PRs, and handle errors from the GitHub API.
"""

# rest of module

import logging

from github.PullRequest import PullRequest

logger = logging.getLogger(__name__)


def enable_auto_merge(pr: PullRequest) -> None:
    """
    Enables auto merge for the given PR.
    :param pr: The PR to enable auto merge for.
    """
    pr.enable_automerge(merge_method="SQUASH")


