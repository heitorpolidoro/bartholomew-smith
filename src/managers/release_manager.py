"""This module contains the logic for managing releases."""

from typing import NoReturn

from githubapp import Config
from githubapp.events import CheckSuiteRequestedEvent

from src.helpers import command_helper, pull_request_helper, release_helper


@Config.call_if("release_manager.enabled")
def manage(event: CheckSuiteRequestedEvent) -> None:
    """Create a release if there is a command in the commit message"""
    repository = event.repository

    head_branch = event.check_suite.head_branch

    check_run = event.start_check_run(
        "Releaser",
        event.check_suite.head_sha,
        "Checking for release command...",
    )

    version_to_release = None
    check_suite = event.check_suite
    is_default_branch = head_branch == repository.default_branch
    if is_default_branch:
        commits = repository.compare(
            check_suite.before, check_suite.after
        ).commits.reversed
    else:
        if pull_request := pull_request_helper.get_existing_pull_request(
            repository, head_branch
        ):
            commits = pull_request.get_commits().reversed
        else:
            check_run.update(title="No Pull Request found", conclusion="success")
            return

    for commit in commits:
        if version_to_release := command_helper.get_command(
            commit.commit.message, "release"
        ):
            break

    if not version_to_release:
        check_run.update(title="No release command found", conclusion="success")
        return

    if release_helper.is_relative_release(version_to_release):
        last_version = release_helper.get_last_release(repository)
        version_to_release = release_helper.get_absolute_release(
            last_version, version_to_release
        )

    if not release_helper.is_valid_release(version_to_release):
        check_run.update(
            title=f"Invalid release {version_to_release}",
            summary="Invalid release ❌",
            conclusion="failure",
        )
        return

    if is_default_branch:
        check_run.update(
            title=f"Releasing {version_to_release}",
            summary="",
        )
        repository.create_git_release(
            tag=version_to_release, generate_release_notes=True
        )
        check_run.update(
            title=f"{version_to_release} released ✅", summary="", conclusion="success"
        )
    else:
        check_run.update(
            title=f"Ready to release {version_to_release}",
            summary="Release command found ✅",
            conclusion="success",
        )
