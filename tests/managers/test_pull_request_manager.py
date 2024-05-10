from unittest.mock import Mock, call, patch

import pytest
from github.PullRequest import PullRequest
from githubapp import Config

from src.managers.pull_request_manager import (
    auto_approve,
    auto_update_pull_requests,
    enable_auto_merge,
    get_or_create_pull_request,
    get_title_and_body_from_issue,
    manage,
)


@pytest.fixture
def pull_request_helper():
    with patch("src.managers.pull_request_manager.pull_request_helper") as pull_request_helper_mock:
        yield pull_request_helper_mock


@pytest.mark.parametrize(
    "head_branch, pull_request_user_login, auto_merge_error, create_pull_request",
    [
        ["master", "heitorpolidoro", "", True],
        ["branch", "heitorpolidoro", "", True],
        ["branch", Config.BOT_NAME, "", True],
        ["branch", "heitorpolidoro", "Some error", True],
        ["branch", "heitorpolidoro", "", False],
    ],
)
def test_manage(
    event,
    check_run,
    head_branch,
    pull_request_user_login,
    auto_merge_error,
    create_pull_request,
    pull_request,
    pull_request_helper,
):
    event.check_suite.head_branch = head_branch
    pull_request.user.login = pull_request_user_login
    if not create_pull_request:
        pull_request = None
    with (
        patch(
            "src.managers.pull_request_manager.get_or_create_pull_request",
            return_value=pull_request,
        ),
        patch(
            "src.managers.pull_request_manager.enable_auto_merge",
            return_value=auto_merge_error,
        ) as enable_auto_merge,
    ):
        manage(event)
        if head_branch == "master":
            check_run.assert_not_called()
        elif create_pull_request:
            if pull_request_user_login == Config.BOT_NAME:
                summary = "Pull Request #123 created"
            else:
                summary = "Pull Request for 'heitorpolidoro:branch' into 'master' (PR#123) already exists"
            if auto_merge_error:
                summary += f"\nAuto-merge failure: {auto_merge_error}"
            else:
                summary += "\nAuto-merge enabled"
            check_run.update.assert_called_once_with(title="Done", summary=summary, conclusion="success")
            enable_auto_merge.assert_called_once()
        else:
            enable_auto_merge.assert_not_called()


@pytest.mark.parametrize(
    "pull_request,pull_request_user_login,error_creating_pull_request",
    [
        (None, None, False),
        (None, None, True),
        (Mock(user=Mock(login=Config.BOT_NAME)), None, None),
        (Mock(user=Mock(login="other")), None, None),
    ],
    ids=[
        "Creating Pull Request",
        "Error in creating Pull Request",
        "Pull Request by Bartholomew",
        "Pull Request by other",
    ],
)
def test_get_or_create_pull_request(
    pull_request, pull_request_user_login, error_creating_pull_request, repository, pull_request_helper
):
    check_run = Mock()
    if error_creating_pull_request:
        pull_request_helper.get_existing_pull_request.return_value = None
        pull_request_helper.create_pull_request.return_value = "Error in creating Pull Request"
    else:
        pull_request_helper.get_existing_pull_request.return_value = pull_request
        pull_request_helper.create_pull_request.return_value = PullRequest(None, None, {}, None)
    get_or_create_pull_request(repository, "head_branch", check_run)
    if pull_request:
        pull_request_helper.create_pull_request.assert_not_called()
    else:
        pull_request_helper.create_pull_request.assert_called_once_with(repository, "head_branch", "head_branch", "")

    if error_creating_pull_request:
        check_run.update.assert_called_with(
            title="Pull Request creation failure", summary="Error in creating Pull Request", conclusion="failure"
        )
    elif pull_request is None or pull_request.user.login == Config.BOT_NAME:
        check_run.update.assert_called_with(title="Pull Request created")
    else:
        check_run.update.assert_not_called()


@pytest.mark.parametrize(
    "branch,expected_title_and_body,get_issue_returns",
    [
        [
            "issue-123",
            (
                "Title 123",
                "### [Title 123](https://github.com/heitorpolidoro/bartholomew_smith/issues/123)\n\n"
                "Body 123\n\nCloses #123\n\n",
            ),
            [Mock(title="Title 123", body="Body 123")],
        ],
        [
            "issue-123",
            (
                "Title 123",
                "### [Title 123](https://github.com/heitorpolidoro/bartholomew_smith/issues/123)\n\n"
                "\n\nCloses #123\n\n",
            ),
            [Mock(title="Title 123", body="")],
        ],
        [
            "issue-123-issue-321",
            (
                "Title 123",
                "### [Title 123](https://github.com/heitorpolidoro/bartholomew_smith/issues/123)\n\n"
                "Body 123\n\nCloses #123\n\n"
                "### [Title 321](https://github.com/heitorpolidoro/bartholomew_smith/issues/321)\n\n"
                "Body 321\n\nCloses #321\n\n",
            ),
            [
                Mock(title="Title 123", body="Body 123"),
                Mock(title="Title 321", body="Body 321"),
            ],
        ],
        [
            "no-issue",
            (
                "no-issue",
                "",
            ),
            [Mock(title="Title 123", body="Body 123")],
        ],
    ],
    ids=[
        "One issue in branch name with body",
        "One issue in branch name with body",
        "Two issues in branch name with body",
        "No issues in branch name",
    ],
)
def test_get_title_and_body_from_issue(branch, repository, expected_title_and_body, get_issue_returns):
    repository.get_issue.side_effect = get_issue_returns
    assert get_title_and_body_from_issue(repository, branch) == expected_title_and_body


def test_enable_auto_merge(pull_request):
    enable_auto_merge(pull_request, Mock())
    pull_request.enable_automerge.assert_called_once_with(merge_method=Config.pull_request_manager.merge_method)


def test_dont_enable_auto_merge_when_mergeable_state_is_unstable(pull_request):
    pull_request.mergeable_state = "unstable"
    enable_auto_merge(pull_request, Mock())
    pull_request.enable_automerge.assert_not_called()


def test_auto_approve(event, repository, pull_request_helper):
    pulls = [Mock() for _ in range(3)]
    event.repository.get_pulls.return_value = pulls
    Config.AUTO_APPROVE_PAT = "AUTO_APPROVE_PAT"
    auto_approve(event)
    assert pull_request_helper.approve.call_count == len(pulls)
    pull_request_helper.approve.assert_has_calls([call(Config.AUTO_APPROVE_PAT, repository, p) for p in pulls])


def test_auto_update_pull_requests(event, pull_request_helper, repository):
    auto_update_pull_requests(event)
    pull_request_helper.update_pull_requests.assert_called_once_with(event.repository, event.check_suite.head_branch)
