from unittest.mock import Mock, patch

from githubapp import Config

from src.managers import pull_request_manager


def test_manage_create_pull_request_and_automerge(
    event, repository, pull_request_helper_mock
):
    pull_request = Mock()
    pull_request_helper_mock.get_existing_pull_request.return_value = None
    pull_request_helper_mock.create_pull_request.return_value = pull_request

    pull_request_manager.manage(event)

    pull_request_helper_mock.create_pull_request.assert_called_once_with(
        repository, "branch", "", ""
    )
    pull_request.enable_automerge.assert_called_once_with(merge_method="SQUASH")


def test_manage_create_pull_request_and_not_automerge(
    event, repository, pull_request_helper_mock
):
    pull_request = Mock()
    pull_request_helper_mock.get_existing_pull_request.return_value = None
    pull_request_helper_mock.create_pull_request.return_value = pull_request
    Config.pull_request_manager.enable_auto_merge = False

    pull_request_manager.manage(event)

    pull_request_helper_mock.create_pull_request.assert_called_once_with(
        repository, "branch", "", ""
    )
    pull_request.enable_automerge.assert_not_called()


def test_manage_existing_pull_request(repository, pull_request_helper_mock, event):
    pull_request = Mock()
    pull_request_helper_mock.get_existing_pull_request.return_value = pull_request

    pull_request_manager.manage(event)

    pull_request_helper_mock.create_pull_request.assert_not_called()
    pull_request.enable_automerge.assert_called_once_with(
        merge_method=pull_request_manager.Config.pull_request_manager.merge_method
    )


def test_manage_existing_pull_request_created_by_bartholomew(
    repository, pull_request_helper_mock, event
):
    pull_request = Mock(user=Mock(login=Config.BOT_NAME), number=1)
    pull_request_helper_mock.get_existing_pull_request.return_value = pull_request

    check_run = Mock()
    event.start_check_run.return_value = check_run

    pull_request_manager.manage(event)

    pull_request_helper_mock.create_pull_request.assert_not_called()
    pull_request.enable_automerge.assert_called_once_with(
        merge_method=pull_request_manager.Config.pull_request_manager.merge_method
    )
    check_run.update.assert_called_with(
        title="Done",
        summary="Pull Request #1 created\nAuto-merge enabled",
        conclusion="success",
    )


def test_create_pull_request(repository, pull_request_helper_mock, event):
    pull_request_manager.create_pull_request(repository, "branch", Mock())
    pull_request_helper_mock.create_pull_request.assert_called_once_with(
        repository, "branch", "", ""
    )


def test_create_pull_request_with_title_and_body(
    repository, pull_request_helper_mock, event
):
    with patch(
        "src.managers.pull_request_manager.get_title_and_body_from_issue",
        return_value=("title", "body"),
    ):
        pull_request_manager.create_pull_request(repository, "branch", Mock())
        pull_request_helper_mock.create_pull_request.assert_called_once_with(
            repository, "branch", "title", "body"
        )


def test_get_title_and_body_from_issue(repository):
    issue = Mock(
        title="Issue 42",
        body="The answer to the ultimate question of life, the universe and everything",
    )
    repository.get_issue.return_value = issue
    title, body = pull_request_manager.get_title_and_body_from_issue(
        repository, "issue-42"
    )
    assert title == "Issue 42"
    assert (
        body
        == """### [Issue 42](https://github.com/heitorpolidoro/bartholomew-smith/issues/42)

The answer to the ultimate question of life, the universe and everything

Closes #42

"""
    )


def test_call_auto_update(event, repository, pull_request_helper_mock):
    event.check_suite.head_branch = repository.default_branch
    pull_request_manager.manage(event)


def test_auto_approve(repository, pull_request_helper_mock, monkeypatch):
    pull_request = Mock()
    monkeypatch.setenv("AUTO_APPROVE_PAT", "PAT")
    pull_request_manager.auto_approve(repository, [pull_request])

    pull_request_helper_mock.approve.assert_called_once_with(
        "PAT", repository, pull_request
    )


def test_auto_approve_without_pat(repository, pull_request_helper_mock, monkeypatch):
    pull_request = Mock()
    pull_request_manager.auto_approve(repository, [pull_request])

    pull_request_helper_mock.approve.assert_not_called()


