from collections import defaultdict
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

import pytest

from config import default_configs


@pytest.fixture(autouse=True)
def setup():
    TableMock._items = defaultdict(list)
    default_configs()


@pytest.fixture
def pull_request_manager_mock():
    with patch("app.pull_request_manager") as mock:
        yield mock


@pytest.fixture
def release_manager_mock():
    with patch("app.release_manager") as mock:
        yield mock


@pytest.fixture
def pull_request_helper_mock():
    with patch("src.managers.pull_request_manager.pull_request_helper") as mock:
        yield mock


@pytest.fixture
def repository():
    # def repository(head_commit, pull_request):
    """
    This fixture returns a mock repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock(
        default_branch="master",
        full_name="heitorpolidoro/bartholomew-smith",
        owner=Mock(login="heitorpolidoro"),
        url="https://api.github.com/repos/heitorpolidoro/bartholomew-smith",
    )
    # repository.get_pulls.return_value = [pull_request]
    # repository.get_commit.return_value = head_commit
    return repository


class TableMock:
    _items = defaultdict(list)

    def __init__(self, table_name=None, **kwargs: Any):
        super().__init__(**kwargs)
        self.table_name = table_name
        self.creation_date_time = True

    @property
    def items(self):
        return TableMock._items[self.table_name]

    def scan(self, ExpressionAttributeValues=None, **kwargs):
        ExpressionAttributeValues = {
            k[1:] if k[0] == ":" else k: v
            for k, v in (ExpressionAttributeValues or {}).items()
        }
        return {
            "Items": list(
                filter(
                    lambda d: all(
                        d[fk] == fv for fk, fv in ExpressionAttributeValues.items()
                    ),
                    self.items,
                )
            )
        }

    @contextmanager
    def batch_writer(self):
        yield self

    def put_item(self, Item=None):
        if Item:
            self.items.append(Item)

    def update_item(self, Key=None, ExpressionAttributeValues=None, **kwargs):
        item = self.scan(Key)["Items"][0]
        item.update(
            {
                k[1:] if k[0] == ":" else k: v
                for k, v in ExpressionAttributeValues.items()
            }
        )
        return item


@pytest.fixture
def event(repository):
    check_run = Mock()
    event = Mock(repository=repository, check_suite=Mock(head_branch="branch"))
    event.start_check_run.return_value = check_run
    event.test_check_run = check_run

    return event


# @pytest.fixture(autouse=True)
# def base_model_service_mock():
#     with (patch("src.helpers.db_helper.BaseModelService") as base_model_service_mock,):
#         base_model_service_mock.resource.Table = lambda table_name: TableMock(
#             table_name=table_name
#         )
#
#         yield base_model_service_mock
#
#
# @pytest.fixture
# def head_commit():
#     """
#     This fixture returns a mock Commit object with default values for the attributes.
#     :return: Mocked Commit
#     """
#     commit = Mock()
#     commit.sha = "sha"
#     commit.commit.message = "message"
#     return commit
#
#
#
#
#
#
# @pytest.fixture
# def issue_comment():
#     return Mock(id=111)
#
#
# @pytest.fixture
# def issue(repository, issue_comment):
#     """
#     This fixture returns a mock Issue object with default values for the attributes.
#     :return: Mocked Issue
#     """
#     issue = Mock(
#         title="Issue Title",
#         number=1,
#         body="Issue Body",
#         milestone=Mock(
#             url="https://github.com/heitorpolidoro/bartholomew-smith/milestone/1"
#         ),
#         state_reason=None,
#         state="open",
#         repository=repository,
#         url="https://api.github.com/repos/heitorpolidoro/bartholomew-smith/issues/1",
#     )
#     issue.get_comments.return_value = [issue_comment]
#     issue.create_comment.return_value = issue_comment
#     return issue
#
#
# @pytest.fixture
# def event(repository, head_commit, issue):
#     """
#     This fixture returns a mock event object with default values for the attributes.
#     :return: Mocked Event
#     """
#     event = Mock(
#         repository=repository,
#         ref="issue-42",
#         issue=issue,
#         check_suite=Mock(head_sha=head_commit.sha),
#         hook_installation_target_id="11111",
#         installation_id="22222",
#     )
#     return event
#
#
# @pytest.fixture
# def parse_issue_and_create_jobs_mock():
#     with patch("app.parse_issue_and_create_jobs") as handle_tasklist_mock:
#         yield handle_tasklist_mock
#
#
# @pytest.fixture
# def handle_close_tasklist_mock():
#     with patch("app.handle_close_tasklist") as handle_close_tasklist_mock:
#         yield handle_close_tasklist_mock
#
#
# @pytest.fixture(autouse=True)
# def _get_auth_mock():
#     with patch("src.managers.issue_manager._get_auth") as _get_auth:
#         yield _get_auth
#
#
# @pytest.fixture(autouse=True)
# def github_mock():
#     with patch("src.managers.issue_manager.Github") as Github:
#         yield Github
#
#
#
