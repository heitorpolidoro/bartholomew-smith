from unittest.mock import Mock, patch

import pytest

from src.managers import pull_request_manager
import app


def test_manage_create_pull_request_and_automerge(repository, pull_request_helper_mock):
    pull_request = Mock()
    pull_request_helper_mock.get_existing_pull_request.return_value = None
    pull_request_helper_mock.create_pull_request.return_value = pull_request

    pull_request_manager.manage(repository, "branch")

    pull_request_helper_mock.create_pull_request.assert_called_once_with(
        repository, "branch", "", ""
    )
    pull_request.enable_automerge.assert_called_once_with(merge_method="SQUASH")


def test_manage_existing_pull_request(repository, pull_request_helper_mock):
    pull_request = Mock()
    pull_request_helper_mock.get_existing_pull_request.return_value = pull_request

    pull_request_manager.manage(repository, "branch")

    pull_request_helper_mock.create_pull_request.assert_not_called()
    pull_request.enable_automerge.assert_called_once_with(
        merge_method=pull_request_manager.Config.pull_request_manager.merge_method
    )


def test_create_pull_request(repository, pull_request_helper_mock):
    pull_request_manager.create_pull_request(repository, "branch")
    pull_request_helper_mock.create_pull_request.assert_called_once_with(
        repository, "branch", "", ""
    )


def test_create_pull_request_with_title_and_body(repository, pull_request_helper_mock):
    with patch(
        "src.managers.pull_request_manager.get_title_and_body_from_issue",
        return_value=("title", "body"),
    ):
        pull_request_manager.create_pull_request(repository, "branch")
        pull_request_helper_mock.create_pull_request.assert_called_once_with(
            repository, "branch", "title", "body"
        )


def test_get_title_and_body_from_issue(repository):
    issue = Mock(
        title="Issue 42",
        body="The answer to the ultimate question of life, the universe and everything",
    )
    repository.get_issue.return_value = issue
    title, body = pull_request_manager.get_title_and_body_from_issue(
        repository, "issue-42"
    )
    assert title == "Issue 42"
    assert (
        body
        == """### [Issue 42](https://github.com/heitorpolidoro/bartholomew-smith/issues/42)

The answer to the ultimate question of life, the universe and everything

Closes #42

"""
    )


def test_auto_update_pull_requests(repository):
    pull_behind = Mock(mergeable_state="behind")
    other_pull = Mock(mergeable_state="not behind")
    pulls = [pull_behind, other_pull]
    repository.get_pulls.return_value = pulls
    pull_request_manager.auto_update_pull_requests(repository)

    pull_behind.update_branch.assert_called_once()
    other_pull.update_branch.assert_not_called()
# @pytest.fixture
# def pull_request_helper():
#     with patch("src.managers.pull_request_manager.pull_request_helper") as mock:
#         yield mock
#
#
# @pytest.fixture
# def github(repository, pull_request):
#     with patch("src.managers.pull_request_manager.Github") as mock:
#         repository.get_pull.return_value = pull_request
#         mock.return_value.get_repo.return_value = repository
#         yield mock
#
#
# def test_handle_create_pull_request(pull_request_helper):
#     repository = Mock()
#     handle_create_pull_request(repository, "branch")
#     pull_request_helper.get_or_create_pull_request.assert_called_once_with(
#         repository, "branch"
#     )
#     pr = pull_request_helper.get_or_create_pull_request.return_value
#     pr.enable_automerge.assert_called_once_with(merge_method="SQUASH")
#
#
# def test_handle_self_approver(repository, pull_request, github):
#     pull_request.get_commits.return_value = [Mock(author=Mock(login="heitorpolidoro"))]
#     pull_request.get_reviews.return_value = []
#     handle_self_approver("gh_AUTO_APPROVE_PAT", repository, pull_request)
#     pull_request.create_review.assert_called_once_with(event="APPROVE")
#
#
# def test_handle_self_approver_when_not_same_owner(repository, pull_request, github):
#     pull_request.get_commits.return_value = [Mock(author=Mock(login="other"))]
#     pull_request.get_reviews.return_value = []
#     handle_self_approver("gh_AUTO_APPROVE_PAT", repository, pull_request)
#     pull_request.create_review.assert_not_called()
#
#
# def test_handle_self_approver_when_already_approved(repository, pull_request, github):
#     author = Mock(login="heitorpolidoro")
#     pull_request.get_commits.return_value = [Mock(author=author)]
#     pull_request.get_reviews.return_value = [Mock(user=author, state="APPROVED")]
#     handle_self_approver("gh_AUTO_APPROVE_PAT", repository, pull_request)
#     pull_request.create_review.assert_not_called()
#
#
# def test_handle_self_approver_when_review_dismissed(repository, pull_request, github):
#     author = Mock(login="heitorpolidoro")
#     pull_request.get_commits.return_value = [Mock(author=author)]
#     pull_request.get_reviews.return_value = [Mock(user=author, state="DISMISSED")]
#     handle_self_approver("gh_AUTO_APPROVE_PAT", repository, pull_request)
#     pull_request.create_review.assert_called_once_with(event="APPROVE")
#
#
# def test_handle_self_approver_when_approved_by_other(repository, pull_request, github):
#     pull_request.get_commits.return_value = [Mock(author=Mock(login="heitorpolidoro"))]
#     pull_request.get_reviews.return_value = [
#         Mock(user=Mock(login="other"), state="APPROVED")
#     ]
#     handle_self_approver("gh_AUTO_APPROVE_PAT", repository, pull_request)
#     pull_request.create_review.assert_called_once_with(event="APPROVE")
