from unittest.mock import Mock, call, patch

import pytest
from githubapp.events import IssueEditedEvent

from src.managers.issue_manager import handle_close_tasklist, handle_tasklist


@pytest.fixture(autouse=True)
def get_repository(repo_batata):
    def mocked_get_repository(_gh, repository_name, _owner):
        if repository_name == "repo_batata":
            return repo_batata
        return None

    with patch(
        "src.managers.issue_manager.get_repository", side_effect=mocked_get_repository
    ) as mock:
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
def handle_issue_state():
    with patch("src.managers.issue_manager.handle_issue_state") as handle_issue_state:
        yield handle_issue_state


def test_handle_tasklist_when_there_is_no_task_list(event, issue, repository):
    handle_tasklist(event)
    repository.create_issue.assert_not_called()
    issue.edit.assert_not_called()


def test_handle_tasklist_when_there_is_a_task_list(
    event, issue, repository, created_issue
):
    issue.body = "- [ ] batata"
    created_issue.number = 123
    handle_tasklist(event)
    repository.create_issue.assert_called_once_with(
        title="batata", milestone="milestone"
    )
    issue.edit.assert_called_once_with(
        body="- [ ] heitorpolidoro/bartholomew-smith#123"
    )


def test_handle_tasklist_with_just_repository_name(
    event, issue, repo_batata, created_issue
):
    issue.body = "- [ ] repo_batata"
    created_issue.number = 123
    created_issue.repository = repo_batata
    handle_tasklist(event)
    repo_batata.create_issue.assert_called_once_with(
        title="Issue Title", milestone="milestone"
    )
    issue.edit.assert_called_once_with(body="- [ ] heitorpolidoro/repo_batata#123")


def test_handle_tasklist_with_repository_name_and_title(
    event, issue, repo_batata, created_issue
):
    issue.body = "- [ ] [repo_batata] Batata"
    created_issue.number = 123
    created_issue.repository = repo_batata
    handle_tasklist(event)
    repo_batata.create_issue.assert_called_once_with(
        title="Batata", milestone="milestone"
    )
    issue.edit.assert_called_once_with(body="- [ ] heitorpolidoro/repo_batata#123")


def test_handle_tasklist_close_issue_in_tasklist(
    event, issue, repository, handle_issue_state
):
    issue.body = "- [x] #123"
    issue.changes = {"body": {"from": "- [ ] #123"}}
    repository.get_issue.return_value = issue
    handle_tasklist(event)
    handle_issue_state.assert_called_once_with(True, issue)
    repository.get_issue.assert_called_once_with(123)
    repository.create_issue.assert_not_called()


def test_handle_tasklist_only_handle_changed_checked_issues(
    event, issue, repository, handle_issue_state
):
    issue1 = Mock(state="open")
    issue2 = Mock(state="open")
    issue3 = Mock(state="close")
    event.__class__ = IssueEditedEvent

    def get_issue(issue_number):
        return {1: issue1, 2: issue2, 3: issue3}[issue_number]

    issue.body = "- [x] #1\r\n- [ ] #2\r\n- [ ] #3"
    event.changes = {"body": {"from": "- [ ] #1\r\n- [ ] #2\r\n- [x] #3"}}
    repository.get_issue.side_effect = get_issue

    handle_tasklist(event)
    handle_issue_state.assert_has_calls([call(True, issue1), call(False, issue3)])
    repository.get_issue.assert_has_calls([call(1), call(2), call(3)])
    repository.create_issue.assert_not_called()
    issue.edit.assert_not_called()


def test_handle_tasklist_when_all_tasks_are_done(
    event, issue, repository, handle_issue_state
):
    issue.body = "- [x] #123\r\n- [x] #321"
    repository.get_issue.return_value = issue
    handle_tasklist(event)
    handle_issue_state.assert_has_calls([call(True, issue), call(True, issue)])
    repository.get_issue.assert_has_calls([call(123), call(321)])
    repository.create_issue.assert_not_called()
    issue.edit.assert_called_once_with(state="closed")


def test_handle_tasklist_when_issue_has_not_milestone(event, issue, repository):
    issue.body = "- [ ] batata"
    issue.milestone = None
    handle_tasklist(event)
    repository.create_issue.assert_called_once_with(title="batata")


def test_handle_close_tasklist(event, issue, repository):
    issue123 = Mock(state="closed")
    issue321 = Mock(state="open")

    def get_issue(issue_number):
        return {123: issue123, 321: issue321}[issue_number]

    issue.state = "closed"
    issue.state_reason = "completed"
    issue.body = "- [x] #123\r\n- [ ] #321\r\n- [ ] not a issue"
    repository.get_issue.side_effect = get_issue
    handle_close_tasklist(event)
    issue123.edit.assert_not_called()
    issue321.edit.assert_called_once_with(state="closed", state_reason="completed")


def test_dont_handle_is_checked(event, issue, repository):
    issue.body = "- [ ] #123\r\n- [x] batata"
    handle_tasklist(event)
    repository.create_issue.assert_not_called()
    issue.edit.assert_not_called()


def test_correct_replace(event, issue, repository, created_issue):
    issue.body = (
        "- [ ] heitorpolidoro/bartholomew-smith#10\r\n"
        "- [ ] 10\r\n"
        "- [ ] 10 something"
    )
    created_issue.number = 123
    handle_tasklist(event)
    issue.edit.assert_called_once_with(
        body="- [ ] heitorpolidoro/bartholomew-smith#10\r\n"
             "- [ ] heitorpolidoro/bartholomew-smith#123\r\n"
             "- [ ] 10 something"
    )
