from unittest.mock import Mock

from src.managers.release import handle_release

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
    )


def test_handle_release_when_head_branch_is_the_default_branch(event, repository, pull_request):
    event.check_suite.head_branch = repository.default_branch
    commit = Mock(commit=Mock(message="[release:1.2.3]"))
    pull_request.get_commits.return_value.reversed = [commit]
    assert handle_release(event) is True
    repository.create_git_release.assert_called_once_with(tag="1.2.3", generate_release_notes=True)


def test_handle_release_when_there_is_no_pull_request(event, repository):
    repository.get_pulls.return_value = []
    handle_release(event)
    event.start_check_run.assert_called_once_with(
        BARTHOLOMEW_RELEASER, "sha", title=CHECKING_RELEASE_COMMAND
    )
    event.update_check_run.assert_not_called()
