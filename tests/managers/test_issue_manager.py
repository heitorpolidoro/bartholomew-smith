from collections import defaultdict
from unittest.mock import Mock, call, patch

import pytest

from src.managers.issue_manager import parse_issue_and_create_tasks, process_jobs
from src.models import Job, JobStatus
from src.services import JobService


@pytest.fixture(autouse=True)
def get_repository_mock(repo_batata, repository):
    def mocked_get_repository(_gh, repository_name, _owner=None):
        return {
            "heitorpolidoro/repo_batata": repo_batata,
            "heitorpolidoro/bartholomew-smith": repository,
        }.get(repository_name, None)

    with (
        patch(
            "src.managers.issue_manager.get_repository",
            side_effect=mocked_get_repository,
        ) as mock,
        patch(
            "src.helpers.issue_helper.get_repository",
            side_effect=mocked_get_repository,
        ),
    ):
        yield mock


@pytest.fixture
def repo_batata(created_issue):
    """
    This fixture returns a mock repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock(full_name="heitorpolidoro/repo_batata")
    repository.create_issue.return_value = created_issue
    return repository


@pytest.fixture
def created_issue(repository):
    created_issue = Mock(repository=repository)
    repository.create_issue.return_value = created_issue
    yield created_issue


@pytest.fixture
def issue_helper_mock(issue_comment, issue, repository):
    with patch("src.managers.issue_manager.issue_helper") as issue_helper:
        from src.helpers.issue_helper import get_issue_ref, get_tasklist

        issue_helper.get_issue_ref = get_issue_ref
        issue_helper.get_tasklist = get_tasklist
        issue_helper.update_issue_comment_status.return_value = issue_comment
        issue_helper.get_issue = lambda _, _2, task: issue if "#" in task else None
        yield issue_helper


def test_parse_issue_and_create_tasks_when_no_task_list(issue, issue_helper_mock):
    parse_issue_and_create_tasks(issue, 123, 321)
    issue_helper_mock.update_issue_comment_status.assert_called_once()
    assert JobService.all() == []


def test_parse_issue_and_create_tasks_when_has_task_list(issue, issue_helper_mock):
    issue.body = """- [ ] batata1
- [x] batata2
- [ ] batata3
- [ ] heitorpolidoro/bartholomew-smith#321
- [x] heitorpolidoro/bartholomew-smith#123
"""
    parse_issue_and_create_tasks(issue, 123, 321)
    issue_helper_mock.update_issue_comment_status.assert_called_once()
    tasks = JobService.all()
    assert len(tasks) == 5

    checks = defaultdict(int)
    status_set = set()
    for t in tasks:
        status_set.add(t.job_status)
        checks[t.checked] += 1
    assert status_set == {JobStatus.PENDING}
    assert checks[True] == 2
    assert checks[False] == 3


def test_process_tasks(github_mock, issue, repository, repo_batata):
    tasks = [
        Job(
            task=task,
            original_issue_ref="heitorpolidoro/bartholomew-smith#1",
            checked=False,
            issue_comment_id=1,
            hook_installation_target_id=2,
            installation_id=3,
        )
        for task in [
            "#123",
            "heitorpolidoro/repo_batata#123",
            "[heitorpolidoro/repo_batata]",
            "[heitorpolidoro/repo_batata] title",
            "[repo_batata] title2",
            "repo_batata",
            "just the title",
            "title3",
        ]
    ]
    JobService.insert_many(tasks)

    repository.get_issue = lambda _: issue
    closed_issue = Mock(state="closed")
    repo_batata.get_issue = lambda _: closed_issue

    process_jobs()
    closed_issue.edit.assert_called_once_with(state="open")
    repo_batata.create_issue.assert_has_calls(
        [
            call(title="Issue Title", milestone="milestone"),
            call(title="title", milestone="milestone"),
            call(title="title2", milestone="milestone"),
            call(title="Issue Title", milestone="milestone"),
        ]
    )
    repository.create_issue.assert_has_calls(
        [
            call(title="just the title", milestone="milestone"),
            call(title="title3", milestone="milestone"),
        ]
    )

    status_set = set()
    tasks = JobService.all()
    for t in tasks:
        status_set.add(t.job_status)
    assert status_set == {JobStatus.DONE}


# Create more unit teste
# create a test with a list
# def test_parse_issue_and_create_tasks(
#     issue,
#     issue_comment,
#     issue_helper_mock,
#     build_context_mock,
#     send_sqs_message_mock,
# ):
#     issue.body = """- [ ] batata1
# - [x] batata2
# - [ ] batata3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """
#     parse_issue_and_create_tasks(
#         issue,
#         123,
#         321,
#     )
#
#     issue_helper_mock.update_issue_comment_status.assert_called_once_with(
#         issue,
#         "I'll manage the issues in the next minutes (sorry, free server :disappointed: )",
#     )
#
#     build_context_mock.assert_called_once_with(issue)
#
#     send_sqs_message_mock.assert_called_once_with(
#         {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("batata1", False),
#                 ("batata2", True),
#                 ("batata3", False),
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] batata1
# - [x] batata2
# - [ ] batata3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "total": 5,
#         },
#         123,
#         321,
#         issue_comment,
#     )
#
#
# def test_handle_tasklist_create_issue(
#     issue,
#     repository,
#     send_sqs_message_mock,
#     issue_helper_mock,
#     issue_comment,
# ):
#     issue_helper_mock.get_issue.return_value = issue
#     issue_helper_mock.create_issue.return_value = Mock(repository=repository, number=1)
#     body = {
#         "hook_installation_target_id": 123,
#         "installation_id": 321,
#         "context": {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("batata1", False),
#                 ("batata2", True),
#                 ("batata3", False),
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] batata1
# - [x] batata2
# - [ ] batata3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "total": 5,
#         },
#         "issue_comment_id": 111,
#     }
#     handle_tasklist_step(**body)
#
#     issue_helper_mock.create_issue.assert_called_once_with(ANY, repository, "batata1")
#
#     issue_helper_mock.update_issue_comment_status.assert_called_once_with(
#         issue,
#         f"""Analyzing the tasklist
# {markdown_progress(1, 5)}
# Created 1 issues""",
#     )
#
#     send_sqs_message_mock.assert_called_once_with(
#         {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("batata2", True),
#                 ("batata3", False),
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] batata3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 1},
#             "total": 5,
#         },
#         123,
#         321,
#         issue_comment,
#     )
#
#
# def test_handle_tasklist_dont_create_issue(
#     issue,
#     repository,
#     send_sqs_message_mock,
#     issue_helper_mock,
#     issue_comment,
# ):
#     issue_helper_mock.get_issue.return_value = issue
#     body = {
#         "hook_installation_target_id": 123,
#         "installation_id": 321,
#         "context": {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("batata2", True),
#                 ("batata3", False),
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] batata3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 1},
#             "total": 5,
#         },
#         "issue_comment_id": 111,
#     }
#     handle_tasklist_step(**body)
#
#     issue_helper_mock.create_issue.assert_not_called()
#
#     issue_helper_mock.update_issue_comment_status.assert_called_once_with(
#         issue,
#         f"""Analyzing the tasklist
# {markdown_progress(2, 5)}
# Created 1 issues""",
#     )
#
#     send_sqs_message_mock.assert_called_once_with(
#         {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("batata3", False),
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] batata3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 1},
#             "total": 5,
#         },
#         123,
#         321,
#         issue_comment,
#     )
#
#
# def test_handle_tasklist_create_other_issue(
#     issue,
#     repository,
#     send_sqs_message_mock,
#     issue_helper_mock,
#     issue_comment,
# ):
#     issue_helper_mock.get_issue.return_value = issue
#     issue_helper_mock.create_issue.return_value = Mock(repository=repository, number=3)
#     body = {
#         "hook_installation_target_id": 123,
#         "installation_id": 321,
#         "context": {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("batata3", False),
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] batata3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 1},
#             "total": 5,
#         },
#         "issue_comment_id": 111,
#     }
#     handle_tasklist_step(**body)
#
#     issue_helper_mock.create_issue.assert_called_once_with(ANY, repository, "batata3")
#
#     issue_helper_mock.update_issue_comment_status.assert_called_once_with(
#         issue,
#         f"""Analyzing the tasklist
# {markdown_progress(3, 5)}
# Created 2 issues""",
#     )
#
#     send_sqs_message_mock.assert_called_once_with(
#         {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] heitorpolidoro/bartholomew-smith#3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 2},
#             "total": 5,
#         },
#         123,
#         321,
#         issue_comment,
#     )
#
#
# def test_handle_tasklist_update_issue(
#     issue,
#     repository,
#     send_sqs_message_mock,
#     issue_helper_mock,
#     issue_comment,
# ):
#     issue_helper_mock.get_issue.return_value = issue
#     body = {
#         "hook_installation_target_id": 123,
#         "installation_id": 321,
#         "context": {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("heitorpolidoro/bartholomew-smith#321", False),
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] heitorpolidoro/bartholomew-smith#3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 2},
#             "total": 5,
#         },
#         "issue_comment_id": 111,
#     }
#     handle_tasklist_step(**body)
#
#     issue_helper_mock.create_issue.assert_not_called()
#     issue_helper_mock.handle_issue_state.assert_called_once_with(False, issue)
#
#     issue_helper_mock.update_issue_comment_status.assert_called_once_with(
#         issue,
#         f"""Analyzing the tasklist
# {markdown_progress(4, 5)}
# Updated 1 issues
# Created 2 issues""",
#     )
#
#     send_sqs_message_mock.assert_called_once_with(
#         {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] heitorpolidoro/bartholomew-smith#3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 2, "issues_updated": 1},
#             "total": 5,
#         },
#         123,
#         321,
#         issue_comment,
#     )
#
#
# def test_handle_tasklist_update_other_issue(
#     issue,
#     repository,
#     send_sqs_message_mock,
#     issue_helper_mock,
#     issue_comment,
# ):
#     issue_helper_mock.get_issue.return_value = issue
#     body = {
#         "hook_installation_target_id": 123,
#         "installation_id": 321,
#         "context": {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [
#                 ("heitorpolidoro/bartholomew-smith#123", True),
#             ],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] heitorpolidoro/bartholomew-smith#3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 2, "issues_updated": 1},
#             "total": 5,
#         },
#         "issue_comment_id": 111,
#     }
#     handle_tasklist_step(**body)
#
#     issue_helper_mock.create_issue.assert_not_called()
#     issue_helper_mock.handle_issue_state.assert_called_once_with(True, issue)
#
#     issue_helper_mock.update_issue_comment_status.assert_called_once_with(
#         issue,
#         f"""Analyzing the tasklist
# {markdown_progress(5, 5)}
# Updated 2 issues
# Created 2 issues""",
#     )
#
#     send_sqs_message_mock.assert_called_once_with(
#         {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] heitorpolidoro/bartholomew-smith#3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 2, "issues_updated": 2},
#             "total": 5,
#         },
#         123,
#         321,
#         issue_comment,
#     )
#
#
# def test_handle_tasklist_finish(
#     issue,
#     repository,
#     send_sqs_message_mock,
#     issue_helper_mock,
#     issue_comment,
# ):
#     issue_helper_mock.get_issue.return_value = issue
#     body = {
#         "hook_installation_target_id": 123,
#         "installation_id": 321,
#         "context": {
#             "issue": "heitorpolidoro/bartholomew-smith#123",
#             "tasks": [],
#             "issue_body": """- [ ] heitorpolidoro/bartholomew-smith#1
# - [x] batata2
# - [ ] heitorpolidoro/bartholomew-smith#3
# - [ ] heitorpolidoro/bartholomew-smith#321
# - [x] heitorpolidoro/bartholomew-smith#123
# """,
#             "summary": {"issues_created": 2, "issues_updated": 2},
#             "total": 5,
#         },
#         "issue_comment_id": 111,
#     }
#     handle_tasklist_step(**body)
#
#     issue_helper_mock.create_issue.assert_not_called()
#     issue_helper_mock.handle_issue_state.assert_called_once_with(False, issue)
#
#     issue_helper_mock.update_issue_comment_status.assert_called_once_with(
#         issue,
#         f"""Tasklist analysis completed
# Updated 2 issues
# Created 2 issues""",
#     )
#
#     send_sqs_message_mock.assert_not_called()
#
#
# # def test_handle_tasklist_when_there_is_no_task_list(event, issue, repository):
# #     handle_opened_or_edited_event(event)
# #     issue.create_comment.assert_not_called()
#
#
# # def test_handle_tasklist_when_there_is_a_task_list(
# #     event, issue, repository, created_issue, boto_sqs, monkeypatch
# # ):
# #     monkeypatch.setenv("TASKLIST_QUEUE", "sqs_queue")
# #     issue.body = "- [ ] batata"
# #     handle_opened_or_edited_event(event)
# #     issue.create_comment.assert_called_once_with(
# #         "I'll manage the issues in the next minutes (sorry, free server :disappointed: )"
# #     )
# #     boto_sqs.send_message.assert_called_once_with(
# #         QueueUrl="sqs_queue", MessageBody="heitorpolidoro/bartholomew-smith#123"
# #     )
# # created_issue.number = 123
# # repository.create_issue.assert_called_once_with(
# #     title="batata", milestone="milestone"
# # )
# # issue.edit.assert_called_once_with(
# #     body="- [ ] heitorpolidoro/bartholomew-smith#123"
# # )
#
#
# # def test_handle_tasklist_with_just_repository_name(
# #     event, issue, repo_batata, created_issue
# # ):
# #     issue.body = "- [ ] repo_batata"
# #     created_issue.number = 123
# #     created_issue.repository = repo_batata
# #     handle_tasklist(event)
# #     repo_batata.create_issue.assert_called_once_with(
# #         title="Issue Title", milestone="milestone"
# #     )
# #     issue.edit.assert_called_once_with(body="- [ ] heitorpolidoro/repo_batata#123")
#
#
# # def test_handle_tasklist_with_repository_name_and_title(
# #     event, issue, repo_batata, created_issue
# # ):
# #     issue.body = "- [ ] [repo_batata] Batata"
# #     created_issue.number = 123
# #     created_issue.repository = repo_batata
# #     handle_tasklist(event)
# #     repo_batata.create_issue.assert_called_once_with(
# #         title="Batata", milestone="milestone"
# #     )
# #     issue.edit.assert_called_once_with(body="- [ ] heitorpolidoro/repo_batata#123")
#
#
# # def test_handle_tasklist_close_issue_in_tasklist(
# #     event, issue, repository, handle_issue_state
# # ):
# #     issue.body = "- [x] #123"
# #     issue.changes = {"body": {"from": "- [ ] #123"}}
# #     repository.get_issue.return_value = issue
# #     handle_tasklist(event)
# #     handle_issue_state.assert_called_once_with(True, issue)
# #     repository.get_issue.assert_called_once_with(123)
# #     repository.create_issue.assert_not_called()
#
#
# # def test_handle_tasklist_only_handle_changed_checked_issues(
# #     event, issue, repository, handle_issue_state
# # ):
# #     issue1 = Mock(state="open")
# #     issue2 = Mock(state="open")
# #     issue3 = Mock(state="close")
# #     event.__class__ = IssueEditedEvent
# #
# #     def get_issue(issue_number):
# #         return {1: issue1, 2: issue2, 3: issue3}[issue_number]
# #
# #     issue.body = "- [x] #1\r\n- [ ] #2\r\n- [ ] #3"
# #     event.changes = {"body": {"from": "- [ ] #1\r\n- [ ] #2\r\n- [x] #3"}}
# #     repository.get_issue.side_effect = get_issue
# #
# #     handle_tasklist(event)
# #     handle_issue_state.assert_has_calls([call(True, issue1), call(False, issue3)])
# #     repository.get_issue.assert_has_calls([call(1), call(2), call(3)])
# #     repository.create_issue.assert_not_called()
# #     issue.edit.assert_not_called()
#
#
# # def test_handle_tasklist_when_all_tasks_are_done(
# #     event, issue, repository, handle_issue_state
# # ):
# #     issue.body = "- [x] #123\r\n- [x] #321"
# #     repository.get_issue.return_value = issue
# #     handle_tasklist(event)
# #     handle_issue_state.assert_has_calls([call(True, issue), call(True, issue)])
# #     repository.get_issue.assert_has_calls([call(123), call(321)])
# #     repository.create_issue.assert_not_called()
# #     issue.edit.assert_called_once_with(state="closed")
#
#
# # def test_handle_tasklist_when_issue_has_not_milestone(event, issue, repository):
# #     issue.body = "- [ ] batata"
# #     issue.milestone = None
# #     handle_tasklist(event)
# #     repository.create_issue.assert_called_once_with(title="batata")
#
#
# # def test_dont_handle_is_checked(event, issue, repository):
# #     issue.body = "- [ ] #123\r\n- [x] batata"
# #     handle_tasklist(event)
# #     repository.create_issue.assert_not_called()
# #     issue.edit.assert_not_called()
#
#
# # def test_correct_replace(event, issue, repository, created_issue):
# #     issue.body = (
# #         "- [ ] heitorpolidoro/bartholomew-smith#10\r\n"
# #         "- [ ] 10\r\n"
# #         "- [ ] 10 something"
# #     )
# #     created_issue.number = 123
# #     handle_tasklist(event)
# #     issue.edit.assert_called_once_with(
# #         body="- [ ] heitorpolidoro/bartholomew-smith#10\r\n"
# #              "- [ ] heitorpolidoro/bartholomew-smith#123\r\n"
# #              "- [ ] 10 something"
# #     )
#
#
# # def test_handle_close_tasklist(event, issue, repository):
# #     issue123 = Mock(state="closed")
# #     issue321 = Mock(state="open")
# #
# #     def get_issue(issue_number):
# #         return {123: issue123, 321: issue321}[issue_number]
# #
# #     issue.state = "closed"
# #     issue.state_reason = "completed"
# #     issue.body = "- [x] #123\r\n- [ ] #321\r\n- [ ] not a issue"
# #     repository.get_issue.side_effect = get_issue
# #     handle_close_tasklist(event)
# #     issue123.edit.assert_not_called()
# #     issue321.edit.assert_called_once_with(state="closed", state_reason="completed")
