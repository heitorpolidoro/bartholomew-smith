from unittest.mock import Mock

import pytest


@pytest.fixture
def repository():
    """
    This fixture returns a mock repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock()
    repository.default_branch = "master"
    repository.full_name = "heitorpolidoro/pull-request-generator"
    repository.get_pulls.return_value = []
    return repository


@pytest.fixture
def issue():
    """
    This fixture returns a mock issue object with default values for the attributes.
    :return: Mocked Issue
    """
    issue = Mock()
    issue.title = "feature"
    issue.body = "feature body"
    issue.number = 42
    return issue


@pytest.fixture
def event(repository, issue):
    """
    This fixture returns a mock event object with default values for the attributes.
    :return: Mocked Event
    """
    event = Mock()
    event.repository = repository
    repository.get_issue.return_value = issue
    event.ref = "issue-42"
    return event
