from unittest.mock import Mock, call, patch

from src.managers.release_manager import handle_release

CHECKING_RELEASE_COMMAND = "Checking for release command"

BARTHOLOMEW_RELEASER = "Bartholomew - Releaser"


def test_handle_release_when_there_is_no_command(event, repository, pull_request):
    handle_release(event)
    event.start_check_run.assert_called_once_with(
        BARTHOLOMEW_RELEASER, "sha", title=CHECKING_RELEASE_COMMAND
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
        BARTHOLOMEW_RELEASER, "sha", title=CHECKING_RELEASE_COMMAND
    )
    pull_request.get_commits.assert_called_once()
    event.update_check_run.assert_called_once_with(
        title="Ready to release 1.2.3",
        summary="Release command found ✅",
        conclusion="success",
    )


def test_handle_release_when_head_branch_is_the_default_branch(
    event, repository, pull_request
):
    event.check_suite.head_branch = repository.default_branch
    commit = Mock(commit=Mock(message="[release:1.2.3]"))
    repository.compare.return_value = Mock(commits=[commit])
    handle_release(event)
    repository.create_git_release.assert_called_once_with(
        tag="1.2.3", generate_release_notes=True
    )
    event.update_check_run.assert_has_calls(
        [
            call(
                title="Releasing 1.2.3",
                summary="",
            ),
            call(
                title="1.2.3 released ✅",
                summary="",
                conclusion="success",
            ),
        ]
    )


def test_handle_release_when_there_is_no_pull_request(event, repository):
    repository.get_pulls.return_value = []
    handle_release(event)
    event.start_check_run.assert_called_once_with(
        BARTHOLOMEW_RELEASER, "sha", title=CHECKING_RELEASE_COMMAND
    )
    event.update_check_run.assert_not_called()


def test_handle_release_when_is_relative_release(event, repository, pull_request):
    commit = Mock(commit=Mock(message="[release:bugfix]"))
    pull_request.get_commits.return_value.reversed = [commit]

    with patch("src.managers.release_manager.get_last_release", return_value="1.2.3"):
        handle_release(event)
    event.start_check_run.assert_called_once_with(
        BARTHOLOMEW_RELEASER, "sha", title=CHECKING_RELEASE_COMMAND
    )
    pull_request.get_commits.assert_called_once()
    event.update_check_run.assert_called_once_with(
        title="Ready to release 1.2.4",
        summary="Release command found ✅",
        conclusion="success",
    )


def test_handle_release_when_is_not_a_valid_relative(event, repository, pull_request):
    commit = Mock(commit=Mock(message="[release:invalid]"))
    pull_request.get_commits.return_value.reversed = [commit]

    handle_release(event)
    event.start_check_run.assert_called_once_with(
        BARTHOLOMEW_RELEASER, "sha", title=CHECKING_RELEASE_COMMAND
    )
    event.update_check_run.assert_called_once_with(
        title="Invalid release invalid",
        summary="Invalid release ❌",
        conclusion="failure",
    )
