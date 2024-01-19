from githubapp.events import CheckSuiteRequestedEvent

from src.helpers.command import get_command
from src.helpers.pull_request import get_existing_pull_request


def handle_release(event: CheckSuiteRequestedEvent):
    repository = event.repository

    head_sha = event.check_suite.head_sha
    head_branch = event.check_suite.head_branch

    event.start_check_run(
        "Bartholomew - Releaser", head_sha, title="Checking for release command"
    )

    version_to_release = None
    check_suite = event.check_suite
    is_default_branch = head_branch == repository.default_branch
    if is_default_branch:
        commits = reversed(
            repository.compare(check_suite.before, check_suite.after).commits
        )
    else:
        if pull_request := get_existing_pull_request(repository, head_branch):
            commits = pull_request.get_commits().reversed
        else:
            return

    for commit in commits:
        if version_to_release := get_command(commit.commit.message, "release"):
            break

    if not version_to_release:
        event.update_check_run(title="No release command found", conclusion="success")
        return

    if is_default_branch:
        event.update_check_run(
            title=f"Releasing {version_to_release}",
            summary="",
        )
        repository.create_git_release(
            tag=version_to_release, generate_release_notes=True
        )
    else:
        event.update_check_run(
            title=f"Ready to release {version_to_release}",
            summary="Release command found ✅",
        )

    # try:
    #     last_release = repository.get_latest_release()
    # except UnknownObjectException:
    #     last_release = "0"
    # if commit.message.startswith("release"):
    #     event.create_check_run(
    #         "Releaser", head_sha, title="Found release command", conclusion="success"
    #     )
    #     return
    # while True:
    #     head_commit = repository.get_commit(head_sha)
    #     commit
