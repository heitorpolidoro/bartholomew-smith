from unittest.mock import Mock, patch

import pytest
from github import GithubException

from src.helpers.pull_request_helper import (
    create_pull_request,
    get_existing_pull_request,
    update_pull_requests,
    approve,
)

OTHER_ERROR = "other error"


@pytest.fixture
def repository_helper_mock(repository, pull_request):
    with patch("src.helpers.pull_request_helper.repository_helper") as mock:
        mock.get_repo_cached.return_value = repository
        repository.get_pull.return_value = pull_request
        yield mock


@pytest.fixture
def pull_request():
    """
    This fixture returns a mock PullRequest object with default values for the attributes.
    :return: Mocked PullRequest
    """
    pull_request = Mock()
    pull_request.get_commits.return_value.reversed = [Mock(sha="sha")]
    return pull_request


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
    create_pull_request(repository, "branch", "", "")
    repository.create_pull.assert_called_once_with(
        repository.default_branch,
        "branch",
        title="branch",
        body="Pull Request automatically created",
        draft=False,
    )


def test_create_pull_request_when_there_is_no_commits(repository):
    repository.create_pull.side_effect = GithubException(
        status=400,
        data={"errors": [{"message": "No commits between master and branch"}]},
    )
    assert create_pull_request(repository, "branch", "", "") is None


def test_create_pull_request_when_other_errors(repository):
    repository.create_pull.side_effect = GithubException(
        status=400, message=OTHER_ERROR
    )
    with pytest.raises(GithubException) as err:
        create_pull_request(repository, "branch", "", "")
    assert err.value.message == OTHER_ERROR


def test_create_pull_request_when_other_errors2(repository):
    repository.create_pull.side_effect = GithubException(
        status=400, data={"errors": [{"message": OTHER_ERROR}]}
    )
    with pytest.raises(GithubException) as err:
        create_pull_request(repository, "branch", "", "")
    assert err.value.data["errors"][0]["message"] == OTHER_ERROR


def test_auto_update_pull_requests(repository):
    pull_behind = Mock(mergeable_state="behind")
    other_pull = Mock(mergeable_state="not behind")
    pulls = [pull_behind, other_pull]
    repository.get_pulls.return_value = pulls
    update_pull_requests(repository)

    pull_behind.update_branch.assert_called_once()
    other_pull.update_branch.assert_not_called()


def test_approve(repository, pull_request, repository_helper_mock):
    pull_request.get_commits.return_value = [Mock(author=Mock(login="heitorpolidoro"))]
    pull_request.get_reviews.return_value = []
    with patch("src.helpers.pull_request_helper.github"):
        approve("gh_AUTO_APPROVE_PAT", repository, pull_request)
    pull_request.create_review.assert_called_once_with(event="APPROVE")


def test_approve_when_not_same_owner(repository, pull_request, repository_helper_mock):
    pull_request.get_commits.return_value = [Mock(author=Mock(login="other"))]
    pull_request.get_reviews.return_value = []
    with patch("src.helpers.pull_request_helper.github"):
        approve("gh_AUTO_APPROVE_PAT", repository, pull_request)
    pull_request.create_review.assert_not_called()


def test_approve_when_already_approved(repository, pull_request, repository_helper_mock):
    author = Mock(login="heitorpolidoro")
    pull_request.get_commits.return_value = [Mock(author=author)]
    pull_request.get_reviews.return_value = [Mock(user=author, state="APPROVED")]
    with patch("src.helpers.pull_request_helper.github"):
        approve("gh_AUTO_APPROVE_PAT", repository, pull_request)
    pull_request.create_review.assert_not_called()


def test_approve_when_review_dismissed(repository, pull_request, repository_helper_mock):
    author = Mock(login="heitorpolidoro")
    pull_request.get_commits.return_value = [Mock(author=author)]
    pull_request.get_reviews.return_value = [Mock(user=author, state="DISMISSED")]
    with patch("src.helpers.pull_request_helper.github"):
        approve("gh_AUTO_APPROVE_PAT", repository, pull_request)
    pull_request.create_review.assert_called_once_with(event="APPROVE")


def test_approve_when_approved_by_other(repository, pull_request, repository_helper_mock):
    pull_request.get_commits.return_value = [Mock(author=Mock(login="heitorpolidoro"))]
    pull_request.get_reviews.return_value = [
        Mock(user=Mock(login="other"), state="APPROVED")
    ]
    with patch("src.helpers.pull_request_helper.github"):
        approve("gh_AUTO_APPROVE_PAT", repository, pull_request)
    pull_request.create_review.assert_called_once_with(event="APPROVE")
