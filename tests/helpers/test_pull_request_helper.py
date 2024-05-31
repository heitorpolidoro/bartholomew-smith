from unittest.mock import Mock, patch

import pytest
from github import GithubException
from githubapp import Config

from src.helpers.pull_request_helper import (
    approve,
    get_existing_pull_request,
    update_pull_requests,
)


@pytest.mark.parametrize(
    "pull_requests,expected_result_index",
    [
        (0, None),
        (1, 0),
        (2, 0),
    ],
    ids=[
        "No pull requests",
        "1 pull request",
        "2 pull requests",
    ],
)
def test_get_existing_pull_request(
    repository_mock, expected_result_index, pull_requests
):
    pull_requests = [Mock() for _ in range(pull_requests)]

    repository_mock.get_pulls.return_value = pull_requests

    expected_result = (
        pull_requests[expected_result_index]
        if expected_result_index is not None
        else None
    )
    assert get_existing_pull_request(repository_mock, "head_branch") == expected_result


@pytest.mark.parametrize("mergeable_state", ["behind", "other"])
def test_update_pull_request(repository_mock, mergeable_state):
    pull_request = Mock(mergeable_state=mergeable_state)
    repository_mock.get_pulls.return_value = [pull_request]
    update_pull_requests(repository_mock, "branch")
    if mergeable_state == "behind":
        pull_request.update_branch.assert_called_once()
    else:
        pull_request.update_branch.assert_not_called()


@pytest.mark.parametrize(
    "first_commit_author,should_approve,approved",
    [
        ("heitorpolidoro", True, False),
        ("allowed_user", True, False),
        ("other_user", False, False),
        ("heitorpolidoro", False, True),
    ],
    ids=[
        "Approve when the first commit owner is the same repository owner",
        "Approve when the first commit owner is in the auto approve login list",
        "Don't Approve when the first commit owner is not in the auto approve login list nether the repository owner",
        "Don't Approve if already approved",
    ],
)
def test_approve(
    repository_mock, pull_request, first_commit_author, should_approve, approved
):
    pull_request.get_commits.return_value = [
        Mock(author=Mock(login=first_commit_author))
    ]
    if approved:
        pull_request.get_reviews.return_value = [Mock(state="APPROVED")]
    else:
        pull_request.get_reviews.return_value = []

    if first_commit_author == "allowed_user":
        Config.pull_request_manager.auto_approve_logins = [first_commit_author]
    with patch(
        "src.helpers.pull_request_helper.repository_helper"
    ) as repository_helper:
        repository_helper.get_repo_cached.return_value.get_pull.return_value = (
            pull_request
        )
        approve("pat", repository_mock, pull_request)

    if should_approve:
        pull_request.create_review.assert_called_once_with(event="APPROVE")
    else:
        pull_request.create_review.assert_not_called()
