from unittest.mock import Mock, patch

import pytest

from src.handlers.create_pull_request import handle_create_pull_request


@pytest.fixture()
def pull_request_helper():
    with patch("src.handlers.create_pull_request.pull_request") as mock:
        yield mock


def test_handle_create_pull_request(pull_request_helper):
    repository = Mock()
    handle_create_pull_request(repository, "branch")
    pull_request_helper.get_or_create_pull_request.assert_called_once_with(
        repository, "branch"
    )
    pr = pull_request_helper.get_or_create_pull_request.return_value
    pull_request_helper.enable_auto_merge.assert_called_once_with(pr)


def test_handle_create_pull_request_ignore_when_head_branch_is_the_default_branch(
    pull_request_helper,
):
    repository = Mock(default_branch="branch")
    handle_create_pull_request(repository, "branch")
    pull_request_helper.get_or_create_pull_request.assert_not_called()
