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
    return commit


@pytest.fixture
def repository(head_commit):
    """
    This fixture returns a mock repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock()
    repository.default_branch = "master"
    repository.full_name = "heitorpolidoro/bartholomew-smith"
    repository.owner.login = "heitorpolidoro"
    repository.get_pulls.return_value = []
    repository.get_commit.return_value = head_commit
    return repository


@pytest.fixture
def event(repository, head_commit):
    """
    This fixture returns a mock event object with default values for the attributes.
    :return: Mocked Event
    """
    event = Mock()
    event.repository = repository
    event.ref = "issue-42"
    event.check_suite.head_sha = head_commit.sha
    return event
