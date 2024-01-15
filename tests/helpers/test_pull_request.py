from unittest.mock import Mock, patch

from github import GithubException

from src.helpers.pull_request import (
    get_existing_pull_request,
    create_pull_request,
    get_or_create_pull_request,
    enable_auto_merge,
)

import pytest


def test_get_existing_pull_request_when_there_is_none(repository):
    repository.get_pulls.return_value = []
    assert get_existing_pull_request(repository, "branch") is None
    repository.get_pulls.assert_called_once_with(state="open", head="branch")


def test_get_existing_pull_request_when_exists(repository):
    pull_request = Mock()
    repository.get_pulls.return_value = [pull_request]
    assert get_existing_pull_request(repository, "branch") == pull_request
    repository.get_pulls.assert_called_once_with(state="open", head="branch")


def test_create_pull_request(repository):
    create_pull_request(repository, "branch")
    repository.create_pull.assert_called_once_with(
        repository.default_branch,
        "branch",
        title="branch",
        body="PR automatically created",
        draft=False,
    )


def test_create_pull_request_with_issue_in_branch_name_github(repository):
    issue = Mock(title="issue title", body="issue body\n2nd line")
    repository.get_issue.return_value = issue
    create_pull_request(repository, "issue-42")
    repository.create_pull.assert_called_once_with(
        repository.default_branch,
        "issue-42",
        title="issue title",
        body="""### [issue title](https://github.com/heitorpolidoro/bartholomew-smith/issues/42)

issue body
2nd line

Closes #42

""",
        draft=False,
    )


def test_create_pull_request_when_there_is_no_commits(repository):
    repository.create_pull.side_effect = GithubException(
        status=400, message="No commits between 'master' and 'branch'"
    )
    assert create_pull_request(repository, "branch") is None


def test_create_pull_request_when_other_errors(repository):
    repository.create_pull.side_effect = GithubException(
        status=400, message="other error"
    )
    with pytest.raises(GithubException) as err:
        create_pull_request(repository, "branch")
    assert err.value.message == "other error"


def test_get_or_create_pull_request_when_there_is_no_pull_request(repository):
    pull_request = Mock()
    with (
        patch(
            "src.helpers.pull_request.get_existing_pull_request", return_value=None
        ) as get_existing_pull_request_mock,
        patch(
            "src.helpers.pull_request.create_pull_request", return_value=pull_request
        ) as create_pull_request_mock,
    ):
        assert get_or_create_pull_request(repository, "branch") == pull_request
        get_existing_pull_request_mock.assert_called_once_with(
            repository, "heitorpolidoro:branch"
        )
        create_pull_request_mock.assert_called_once_with(repository, "branch")


def test_get_or_create_pull_request_when_there_is_a_pull_request(repository):
    pull_request = Mock()
    with (
        patch(
            "src.helpers.pull_request.get_existing_pull_request",
            return_value=pull_request,
        ) as get_existing_pull_request_mock,
        patch(
            "src.helpers.pull_request.create_pull_request"
        ) as create_pull_request_mock,
    ):
        assert get_or_create_pull_request(repository, "branch") == pull_request
        get_existing_pull_request_mock.assert_called_once_with(
            repository, "heitorpolidoro:branch"
        )
        create_pull_request_mock.assert_not_called()


def test_enable_auto_merge():
    pull_request = Mock()
    enable_auto_merge(pull_request)
    pull_request.enable_automerge.assert_called_once_with(merge_method="SQUASH")
