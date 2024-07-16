"""This module contains the logic for managing releases."""

import re
from string import Template
from typing import NoReturn

from github import UnknownObjectException
from github.Repository import Repository
from githubapp import Config
from githubapp.event_check_run import CheckRunConclusion, CheckRunStatus, EventCheckRun
from githubapp.events import CheckSuiteRequestedEvent

from src.helpers import command_helper, pull_request_helper, release_helper


@Config.call_if("release_manager.enabled")
def manage(event: CheckSuiteRequestedEvent) -> None:
    """Create a release if there is a command in the commit message"""
    repository = event.repository

    head_branch = event.check_suite.head_branch

    check_run = event.start_check_run(
        "Release Manager",
        event.check_suite.head_sha,
        "Initializing...",
        status=CheckRunStatus.IN_PROGRESS,
    )

    version_to_release = None
    check_suite = event.check_suite
    is_default_branch = head_branch == repository.default_branch
    if check_suite.before == "0000000000000000000000000000000000000000":
        check_run.update(title="First commit", conclusion=CheckRunConclusion.SUCCESS)
        return
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
            check_run.update(
                title="No Pull Request found", conclusion=CheckRunConclusion.SUCCESS
            )
            return

    check_run.update(title="Checking for release command...")
    for commit in commits:
        if version_to_release := command_helper.get_command(
            commit.commit.message, "release"
        ):
            break

    if not version_to_release:
        check_run.update(
            title="No release command found", conclusion=CheckRunConclusion.SUCCESS
        )
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
            conclusion=CheckRunConclusion.FAILURE,
        )
        return

    if is_default_branch:
        check_run.update(title=f"Releasing {version_to_release}...")
        repository.create_git_release(
            tag=version_to_release, generate_release_notes=True
        )
        check_run.update(
            title=f"{version_to_release} released ✅",
            conclusion=CheckRunConclusion.SUCCESS,
        )
    else:
        check_run.update(
            title=f"Ready to release {version_to_release}",
            summary="Release command found ✅",
            conclusion=CheckRunConclusion.SUCCESS,
        )
        update_in_file(
            repository,
            event.check_suite.head_sha,
            head_branch,
            version_to_release,
            check_run,
        )


@Config.call_if("release_manager.update_in_file")
def update_in_file(
    repository: Repository,
    sha: str,
    branch: str,
    version_to_release: str,
    check_run: EventCheckRun,
) -> None:  # pragma: no cover
    """Update the version in the file"""
    # TODO validations
    # config format: must have a file_path and a pattern
    # pattern format: must have a $version variable

    update_in_file_config = Config.release_manager.update_in_file
    file_path = update_in_file_config["file_path"]
    pattern = update_in_file_config["pattern"]
    pattern_regex = Template(pattern).substitute(version=".*")

    check_run.update(title="Updating release file")
    try:
        content = repository.get_contents(
            file_path, ref=repository.default_branch
        ).decoded_content
        if re.search(pattern_regex, content):
            version_to_release = Template(pattern).substitute(
                version=version_to_release
            )
            content = re.sub(pattern_regex, version_to_release, content)
            repository.update_file(
                file_path,
                f"Updating file '{file_path}' for release",
                content,
                sha,
                branch=branch,
            )
            check_run.update(
                title=f"Ready to release {version_to_release}",
                summary="Release command found ✅\nVersion file updated ✅",
                conclusion=CheckRunConclusion.SUCCESS,
            )
        else:
            check_run.update(
                title=f"Pattern {pattern} not found in file '{file_path}'",
                conclusion=CheckRunConclusion.FAILURE,
            )
    except UnknownObjectException:
        check_run.update(
            title=f"File '{file_path}' not found", conclusion=CheckRunConclusion.FAILURE
        )
