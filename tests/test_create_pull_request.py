"""This file contains test cases for the Pull Request Generator application."""
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
import sentry_sdk
from github import GithubException

from src.app import create_branch_handler


def test_create_pr(event, repository):
    """
    This test case tests the create_branch_handler function when there are commits between the new branch and the
    default branch. It checks that the function creates a pull request with the correct parameters.

    Expected behavior:
    - The function should create a pull request with the title "feature".
    - The pull request body should include a link to the issue with the title "feature" and the body "feature body".
    - The pull request body should include the text "Closes #42".
    - The pull request should not be a draft.

    """
    expected_body = """### [feature](https://github.com/heitorpolidoro/pull-request-generator/issues/42)

feature body

Closes #42

"""
    create_branch_handler(event)
    repository.create_pull.assert_called_once_with(
        "master",
        "issue-42",
        title="feature",
        body=expected_body,
        draft=False,
    )
    repository.create_pull.return_value.enable_automerge.assert_called_once_with(
        merge_method="SQUASH"
    )


def test_create_pr_no_commits(event, repository):
    """
    This test case tests the create_branch_handler function when there are no commits between the new branch and the
    default branch. It checks that the function handles this situation correctly by not creating a pull request.
    """
    repository.create_pull.side_effect = GithubException(
        422, message="No commits between 'master' and 'issue-42'"
    )
    create_branch_handler(event)


def test_create_pr_other_exceptions(event, repository):
    """
    This test case tests the create_branch_handler function when an exception other than 'No commits between master and
    feature' is raised. It checks that the function raises the exception as expected.

    Expected behavior:
    - The function should raise a GithubException with the message "Other exception".

    """
    repository.create_pull.side_effect = GithubException(422, message="Other exception")
    with pytest.raises(GithubException):
        create_branch_handler(event)


def test_enable_just_automerge_on_existing_pr(event, repository):
    """
    This test case tests the create_branch_handler function when a pull request already exists for the new branch.
    It checks that the function enables auto-merge for the existing pull request and does not create a new pull request.

    Expected behavior:
    - The function should not create a new pull request.
    - The function should enable auto-merge for the existing pull request with the merge method "SQUASH".

    """
    existing_pr = Mock()
    repository.get_pulls.return_value = [existing_pr]
    create_branch_handler(event)
    repository.create_pull.assert_not_called()
    existing_pr.enable_automerge.assert_called_once_with(merge_method="SQUASH")
