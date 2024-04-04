from unittest.mock import Mock

import pytest

import app
from app import handle_issue
from src.models import IssueJobStatus


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    request = Mock(url="url")
    app.request = request
    make_thread_request = Mock()
    app.make_thread_request = make_thread_request
    return locals()


@pytest.fixture
def make_thread_request_mock(setup):
    return setup.get("make_thread_request")


def test_handle_issue_opened_or_edited(
    event, issue, parse_issue_and_create_jobs_mock, make_thread_request_mock
):
    issue_job_mock = Mock(issue_url="issue_url")
    parse_issue_and_create_jobs_mock.return_value = issue_job_mock
    handle_issue(event)
    parse_issue_and_create_jobs_mock.assert_called_once_with(
        issue, event.hook_installation_target_id, event.installation_id
    )
    make_thread_request_mock.assert_called_once_with("url/process_jobs", "issue_url")


def test_handle_issue_opened_or_edited_when_job_is_running(
    event, issue, parse_issue_and_create_jobs_mock, make_thread_request_mock
):
    issue_job_mock = Mock(
        issue_url="issue_url", issue_job_status=IssueJobStatus.RUNNING
    )
    parse_issue_and_create_jobs_mock.return_value = issue_job_mock
    handle_issue(event)
    parse_issue_and_create_jobs_mock.assert_called_once_with(
        issue, event.hook_installation_target_id, event.installation_id
    )
    make_thread_request_mock.assert_not_called()


def test_handle_issue_opened_or_edited_when_issue_has_no_body(
    event, issue, parse_issue_and_create_jobs_mock
):
    issue.body = None
    handle_issue(event)
    parse_issue_and_create_jobs_mock.assert_not_called()


# def test_handle_issue_full_workflow(event, issue, sqs_mock):
#     issue.body = """
# - [ ] task1
# - [x] task2
# - [ ] repo#3
# - [x] repo#4
# """
#     handle_issue(event)
#     messages = sqs_mock.messages[Config.task_queue]
#     message = json.loads(messages[0])
#     assert message["context"] == {
#         "issue": "heitorpolidoro/bartholomew-smith#123",
#         "tasks": [
#             ["task1", False],
#             ["task2", True],
#             ["repo#3", False],
#             ["repo#4", True],
#         ],
#         "total": 4,
#     }
#
#     handle_tasklist_step(**message)
