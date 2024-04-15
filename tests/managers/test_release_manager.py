from unittest.mock import Mock, call

import pytest

from src.managers import release_manager


@pytest.mark.parametrize("branch", ["default", "not default"])
def test_manage_without_command_default_branch(event, repository, branch):
    commit = Mock(commit=Mock(message="no command"))
    if branch == "default":
        event.check_suite.head_branch = repository.default_branch
        repository.compare().commits.reversed = [commit]
    elif branch == "not default":
        event.check_suite.head_branch = "not default"
        pull_request = Mock(state="open")
        pull_request.get_commits().reversed = [commit]
        repository.get_pulls.return_value = [pull_request]

    release_manager.manage(event)

    event.test_check_run.update.assert_called_once_with(
        title="No release command found", conclusion="success"
    )
    repository.create_git_release.assert_not_called()


def test_manage_without_pull_request(event, repository):
    event.check_suite.head_branch = "not default"
    repository.get_pulls.return_value = []

    release_manager.manage(event)

    event.test_check_run.update.assert_called_once_with(
        title="No Pull Request found", conclusion="success"
    )
    repository.create_git_release.assert_not_called()


@pytest.mark.parametrize(
    "branch,version",
    [
        ("default", "minor"),
        ("default", "2.0.0"),
        ("not default", "minor"),
        ("not default", "2.0.0"),
    ],
)
def test_manage_with_command_default_branch(event, repository, branch, version):
    commit = Mock(commit=Mock(message=f"[release:{version}]"))
    repository.get_latest_release().tag_name = "1.2.3"
    if branch == "default":
        event.check_suite.head_branch = repository.default_branch
        repository.compare().commits.reversed = [commit]
    elif branch == "not default":
        event.check_suite.head_branch = "not default"
        pull_request = Mock(state="open")
        pull_request.get_commits().reversed = [commit]
        repository.get_pulls.return_value = [pull_request]

    release_manager.manage(event)

    if version == "minor":
        version = "1.3.0"

    if branch == "default":
        event.test_check_run.update.assert_has_calls(
            [
                call(title=f"Releasing {version}", summary=""),
                call(title=f"{version} released ✅", summary="", conclusion="success"),
            ]
        )
        repository.create_git_release.assert_called_once_with(
            tag=version, generate_release_notes=True
        )
    elif branch == "not default":
        event.test_check_run.update.assert_has_calls(
            [
                call(
                    title=f"Ready to release {version}",
                    summary="Release command found ✅",
                    conclusion="success",
                ),
            ]
        )
        repository.create_git_release.assert_not_called()


def test_manage_with_invalid_version(event, repository):
    commit = Mock(commit=Mock(message=f"[release:invalid]"))

    event.check_suite.head_branch = repository.default_branch
    repository.compare().commits.reversed = [commit]

    release_manager.manage(event)

    event.test_check_run.update.assert_called_once_with(
        title="Invalid release invalid",
        summary="Invalid release ❌",
        conclusion="failure",
    )
    repository.create_git_release.assert_not_called()
