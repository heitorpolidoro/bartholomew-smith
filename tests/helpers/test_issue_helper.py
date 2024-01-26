from unittest.mock import Mock

from src.helpers.issue_helper import (
    get_issue,
    get_tasklist,
    handle_issue_state,
    issue_ref,
)


def test_get_tasklist_without_tasklist():
    assert get_tasklist("blabla\r\nblabla") == []


def test_get_tasklist_with_tasklist():
    assert (
        get_tasklist(
            """
before
- [ ] foo
- [ ] bar
after
- [ ] other"""
        )
        == [(False, "foo"), (False, "bar"), (False, "other")]
    )


def test_issue_ref():
    issue = Mock(repository=Mock(full_name="full_name"), number=123)
    assert issue_ref(issue) == "full_name#123"


def test_get_issue():
    assert get_issue(None, None, "foo") is None


def test_get_issue_local_repository(repository):
    issue = Mock(number=123)
    repository.get_issue.return_value = issue
    gh = Mock()
    assert get_issue(gh, repository, "#123") is issue
    gh.get_repo.assert_not_called()


def test_get_issue_other_repository():
    issue = Mock(number=123)
    other_repository = Mock()
    other_repository.get_issue.return_value = issue
    gh = Mock()
    gh.get_repo.return_value = other_repository
    assert get_issue(gh, other_repository, "other#123") is issue
    gh.get_repo.assert_called_once_with("other")


def test_handle_issue_state_when_checked_and_open():
    issue = Mock(state="open")
    handle_issue_state(True, issue)
    issue.edit.assert_called_once_with(state="closed")


def test_handle_issue_state_when_not_checked_and_open():
    issue = Mock(state="open")
    handle_issue_state(False, issue)
    issue.edit.assert_not_called()


def test_handle_issue_state_when_checked_and_closed():
    issue = Mock(state="closed")
    handle_issue_state(True, issue)
    issue.edit.assert_not_called()


def test_handle_issue_state_when_not_checked_and_closed():
    issue = Mock(state="closed")
    handle_issue_state(False, issue)
    issue.edit.assert_called_once_with(state="open")
