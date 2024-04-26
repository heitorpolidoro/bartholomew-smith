from unittest.mock import Mock

import pytest
from githubapp import Config

from src.helpers.issue_helper import (
    get_issue_ref,
    get_tasklist,
    handle_issue_state,
    has_tasklist,
    update_issue_comment_status,
)


def _task_list_data():
    return {
        "argvalues": [
            ("", [], "Empty string should not have a tasklist"),
            (
                "This is a sample issue description.",
                [],
                "Text without a tasklist should not be detected",
            ),
            (
                "- [ ] Task 1\nThis is an issue with a tasklist.",
                [("Task 1", False)],
                "Text with a tasklist should be detected",
            ),
            (
                "- [ ] Task 1\n- [x] Completed task 2",
                [("Task 1", False), ("Completed task 2", True)],
                "Text with multiple tasks should be detected",
            ),
            (
                "- Task 3 (missing checkbox)",
                [],
                "Incomplete tasklist should not be detected",
            ),
        ],
        "ids": [
            "Empty body",
            "Without a tasklist",
            "With a tasklist with 1 item",
            "With a tasklist with 2 items",
            "With a list that is not a tasklist",
        ],
    }


@pytest.mark.parametrize(
    "issue_body, expected, assert_fail_message",
    **_task_list_data(),
)
def test_has_tasklist(issue_body, expected, assert_fail_message):
    result = has_tasklist(issue_body)
    assert result is bool(expected), assert_fail_message


@pytest.mark.parametrize(
    "issue_body, expected_tasks, assert_fail_message",
    **_task_list_data(),
)
def test_get_tasklist(issue_body, expected_tasks, assert_fail_message):
    """Test get_tasklist with various inputs using parametrize"""
    result = get_tasklist(issue_body)
    assert result == expected_tasks, assert_fail_message


@pytest.mark.parametrize(
    "repository_full_name, number, expected_ref",
    [
        ("owner/repo", 123, "owner/repo#123"),
        ("another-owner/different-repo", 456, "another-owner/different-repo#456"),
        ("very/long/repo/name", 789, "very/long/repo/name#789"),
    ],
)
def test_get_issue_ref(repository_full_name, number, expected_ref, issue, repository):
    """Test get_issue_ref with various inputs using parametrize"""
    repository.full_name = repository_full_name
    issue.number = number
    result = get_issue_ref(issue)
    assert result == expected_ref


@pytest.mark.parametrize(
    "checked, initial_state, expected_state",
    [
        (True, "open", "closed"),  # Checked, open issue -> close
        (True, "closed", "closed"),  # Checked, closed issue -> open
        (False, "open", "open"),  # Unchecked, open issue -> no change
        (False, "closed", "open"),  # Unchecked, closed issue -> no change
    ],
    ids=lambda value: (
        (("not " if value is False else "") + "checked")
        if isinstance(value, bool)
        else value
    ),
)
def test_handle_issue_state(checked, initial_state, expected_state, issue):
    """Test handle_issue_state with various inputs using parametrize"""
    issue.state = initial_state
    result = handle_issue_state(checked, issue)

    # Assert function call and state change (avoid relying on prints)
    if initial_state != expected_state:
        issue.edit.assert_called_once_with(state=expected_state)
        assert result is True
    else:
        issue.edit.assert_not_called()
        assert result is False


@pytest.mark.parametrize(
    "existing_comment, issue_comment_id, comment",
    [
        (
            False,
            None,
            "new comment created",
        ),
        (
            True,
            None,
            "existing comment edited (BOT_NAME)",
        ),
        (
            True,
            123,
            "existing comment edited (BOT_NAME)",
        ),
    ],
    ids=[
        "without existing comment",
        "with existing comment without passing the id",
        "with existing comment passing the id",
    ],
)
def test_update_issue_comment_status(
    existing_comment, issue_comment_id, comment, issue
):
    """Test update_issue_comment_status with various inputs using parametrize"""
    mock_comments = [
        Mock(user=Mock(login="user1")),
    ]  # Simulate comments

    existing_comment_mock = None
    if existing_comment:
        existing_comment_mock = Mock(user=Mock(login=Config.BOT_NAME))
        mock_comments.append(existing_comment_mock)
        issue.get_comment.return_value = existing_comment_mock

    issue.get_comments.return_value = mock_comments

    result = update_issue_comment_status(issue, comment, issue_comment_id)

    if existing_comment:
        assert result == existing_comment_mock
    else:
        issue.create_comment.assert_called_once_with(comment)
        assert result == issue.create_comment.return_value
