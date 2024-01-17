from unittest.mock import Mock

import pytest


@pytest.fixture
def head_commit():
    """
    This fixture returns a mock Commit object with default values for the attributes.
    :return: Mocked Commit
    """
    commit = Mock()
    commit.sha = "sha"
    commit.commit.message = "message"
    return commit


@pytest.fixture
def pull_request(head_commit):
    """
    This fixture returns a mock PullRequest object with default values for the attributes.
    :return: Mocked PullRequest
    """
    pull_request = Mock()
    pull_request.get_commits.return_value.reversed = [head_commit]
    return pull_request


@pytest.fixture
def repository(head_commit, pull_request):
    """
    This fixture returns a mock repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock(
        default_branch="master",
        full_name="heitorpolidoro/bartholomew-smith",
        owner=Mock(login="heitorpolidoro"),
    )
    repository.get_pulls.return_value = [pull_request]
    repository.get_commit.return_value = head_commit
    return repository


@pytest.fixture
def issue():
    """
    This fixture returns a mock Issue object with default values for the attributes.
    :return: Mocked Issue
    """
    issue = Mock()
    issue.title = "Issue Title"
    issue.body = "Issue Body"
    return issue


@pytest.fixture
def event(repository, head_commit, issue):
    """
    This fixture returns a mock event object with default values for the attributes.
    :return: Mocked Event
    """
    event = Mock()
    event.repository = repository
    event.ref = "issue-42"
    event.check_suite.head_sha = head_commit.sha
    event.issue = issue
    return event
