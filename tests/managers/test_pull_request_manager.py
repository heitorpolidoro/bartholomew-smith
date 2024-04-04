from unittest.mock import Mock, patch

import pytest

from src.managers.pull_request_manager import (
    handle_create_pull_request,
    handle_self_approver,
)


@pytest.fixture
def pull_request_helper():
    with patch("src.managers.pull_request_manager.pull_request_helper") as mock:
        yield mock


@pytest.fixture
def github(repository, pull_request):
    with patch("src.managers.pull_request_manager.Github") as mock:
        repository.get_pull.return_value = pull_request
        mock.return_value.get_repo.return_value = repository
        yield mock


def test_handle_create_pull_request(pull_request_helper):
    repository = Mock()
    handle_create_pull_request(repository, "branch")
    pull_request_helper.get_or_create_pull_request.assert_called_once_with(
        repository, "branch"
    )
    pr = pull_request_helper.get_or_create_pull_request.return_value
    pr.enable_automerge.assert_called_once_with(merge_method="SQUASH")


def test_handle_self_approver(repository, pull_request, github):
    pull_request.get_commits.return_value = [Mock(author=Mock(login="heitorpolidoro"))]
    pull_request.get_reviews.return_value = []
    handle_self_approver("gh_owner_pat", repository, pull_request)
    pull_request.create_review.assert_called_once_with(event="APPROVE")


def test_handle_self_approver_when_not_same_owner(repository, pull_request, github):
    pull_request.get_commits.return_value = [Mock(author=Mock(login="other"))]
    pull_request.get_reviews.return_value = []
    handle_self_approver("gh_owner_pat", repository, pull_request)
    pull_request.create_review.assert_not_called()


def test_handle_self_approver_when_already_approved(repository, pull_request, github):
    author = Mock(login="heitorpolidoro")
    pull_request.get_commits.return_value = [Mock(author=author)]
    pull_request.get_reviews.return_value = [Mock(user=author, state="APPROVED")]
    handle_self_approver("gh_owner_pat", repository, pull_request)
    pull_request.create_review.assert_not_called()


def test_handle_self_approver_when_review_dismissed(repository, pull_request, github):
    author = Mock(login="heitorpolidoro")
    pull_request.get_commits.return_value = [Mock(author=author)]
    pull_request.get_reviews.return_value = [Mock(user=author, state="DISMISSED")]
    handle_self_approver("gh_owner_pat", repository, pull_request)
    pull_request.create_review.assert_called_once_with(event="APPROVE")


def test_handle_self_approver_when_approved_by_other(repository, pull_request, github):
    pull_request.get_commits.return_value = [Mock(author=Mock(login="heitorpolidoro"))]
    pull_request.get_reviews.return_value = [
        Mock(user=Mock(login="other"), state="APPROVED")
    ]
    handle_self_approver("gh_owner_pat", repository, pull_request)
    pull_request.create_review.assert_called_once_with(event="APPROVE")
