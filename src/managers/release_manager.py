from githubapp import Config
from githubapp.events import CheckSuiteRequestedEvent

from src.helpers.command_helper import get_command
from src.helpers.pull_request_helper import get_existing_pull_request
from src.helpers.release_helper import (
    get_absolute_release,
    get_last_release,
    is_relative_release,
    is_valid_release,
)


@Config.call_if("release_manager.enabled")
def manage(event: CheckSuiteRequestedEvent):
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
        if pull_request := get_existing_pull_request(repository, head_branch):
            commits = pull_request.get_commits().reversed
        else:
            check_run.update(title="No Pull Request found", conclusion="success")
            return

    for commit in commits:
        if version_to_release := get_command(commit.commit.message, "release"):
            break

    if not version_to_release:
        check_run.update(title="No release command found", conclusion="success")
        return

    if is_relative_release(version_to_release):
        last_version = get_last_release(repository)
        version_to_release = get_absolute_release(last_version, version_to_release)

    if not is_valid_release(version_to_release):
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
