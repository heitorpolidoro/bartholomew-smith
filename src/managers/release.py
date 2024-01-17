from github import UnknownObjectException
from githubapp.events import CheckSuiteRequestedEvent

from src.helpers.command import get_command
from src.helpers.pull_request import get_existing_pull_request


def handle_release(event: CheckSuiteRequestedEvent):
    repository = event.repository

    head_sha = event.check_suite.head_sha
    head_branch = event.check_suite.head_branch

    event.start_check_run("Releaser", head_sha, title="Checking for release command")

    if head_branch == repository.default_branch:
        repository.create_git_release(
            tag=version_to_release, generate_release_notes=True
        )
        return
    else:
        if pull_request := get_existing_pull_request(repository, head_branch):
            version_to_release = None
            for commit in pull_request.get_commits().reversed:
                if version_to_release := get_command(commit.commit.message, "release"):
                    break

            if not version_to_release:
                event.update_check_run(
                    title="No release command found", conclusion="success"
                )
                return

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
