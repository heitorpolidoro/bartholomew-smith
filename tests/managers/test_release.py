from unittest.mock import Mock, patch

from src.managers.release import handle_release


def test_handle_release_when_there_is_no_command(event, repository, pull_request):
    handle_release(event)
    event.start_check_run.assert_called_once_with(
        "Releaser", "sha", title="Checking for release command"
    )
    pull_request.get_commits.assert_called_once()
    event.update_check_run.assert_called_once_with(
        title="No release command found", conclusion="success"
    )


def test_handle_release_when_there_is_a_command(event, repository, pull_request):
    commit = Mock(commit=Mock(message="[release:1.2.3]"))
    pull_request.get_commits.return_value.reversed = [commit]

    handle_release(event)
    event.start_check_run.assert_called_once_with(
        "Releaser", "sha", title="Checking for release command"
    )
    pull_request.get_commits.assert_called_once()
    event.update_check_run.assert_called_once_with(
        title="Ready to release 1.2.3",
        summary="Release command found ✅",
    )


def test_handle_release_when_head_branch_is_the_default_branch(event, repository):
    event.check_suite.head_branch = repository.default_branch
    assert handle_release(event) is True


def test_handle_release_when_there_is_no_pull_request(event, repository):
    repository.get_pulls.return_value = []
    handle_release(event)
    event.start_check_run.assert_called_once_with(
        "Releaser", "sha", title="Checking for release command"
    )
    event.update_check_run.assert_not_called()