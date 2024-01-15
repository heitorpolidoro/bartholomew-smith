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
    repository.full_name = "heitorpolidoro/bartholomew-smith"
    repository.owner.login = "heitorpolidoro"
    repository.get_pulls.return_value = []
    return repository


@pytest.fixture
def event(repository):
    """
    This fixture returns a mock event object with default values for the attributes.
    :return: Mocked Event
    """
    event = Mock()
    event.repository = repository
    event.ref = "issue-42"
    return event
