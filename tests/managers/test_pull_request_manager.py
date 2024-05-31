from unittest.mock import Mock, patch

from github.Repository import Repository
from githubapp import Config

from src.managers.pull_request_manager import (
    auto_approve,
    get_title_and_body_from_issue,
)


def test_get_title_and_body_from_issue_without_issue_in_branch(repository_mock):
    assert get_title_and_body_from_issue(repository_mock, "feature_branch") == ("", "")


def test_get_title_and_body_from_issue_when_it_is_disabled(repository_mock):
    with patch.object(
        Config.pull_request_manager,
        "link_issue",
        False,
    ):
        assert get_title_and_body_from_issue(repository_mock, "issue-42") == ("", "")


def test_get_title_and_body_from_issue_with_issue_in_branch(repository_mock):
    with patch.object(
        repository_mock, "get_issue", return_value=Mock(title="Title", body="Body")
    ):
        assert get_title_and_body_from_issue(repository_mock, "issue-42") == (
            "Title",
            """### [Title](https://github.com/heitorpolidoro/bartholomew-smith/issues/42)

Body

Closes #42

""",
        )


def test_auto_approve():
    auto_approve()


def test_auto_approve_when_enabled(repository_mock):
    pull_request = Mock()
    with (
        patch.object(
            Config.pull_request_manager,
            "auto_approve",
            True,
        ),
        patch.object(
            Config,
            "AUTO_APPROVE_PAT",
            "AUTOAPPROVEPAT",
        ),
        patch.object(repository_mock, "get_pulls", return_value=[pull_request]),
        patch(
            "src.managers.pull_request_manager.pull_request_helper"
        ) as pull_request_helper,
    ):
        auto_approve(repository_mock, "branch")
        pull_request_helper.approve.assert_called_once_with(
            Config.AUTO_APPROVE_PAT, repository_mock, pull_request
        )
