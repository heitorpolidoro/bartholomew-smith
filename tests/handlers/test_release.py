from unittest.mock import Mock, patch

from src.handlers.release import handle_release


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
        title="Prepared to release 1.2.3",
        summary="Release command found ✅\nReleasing 1.2.3",
    )
