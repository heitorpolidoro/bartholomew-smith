"""This module contains the logic to create and update Pull Requests."""

import logging
import re
from string import Template

from github import GithubException
from github.Repository import Repository
from githubapp import Config, EventCheckRun
from githubapp.event_check_run import CheckRunConclusion, CheckRunStatus
from githubapp.events import CheckSuiteRequestedEvent
from githubapp.exceptions import GithubAppRuntimeException

from src.helpers import pull_request_helper
from src.helpers.exception_helper import extract_github_error

logger = logging.getLogger(__name__)

BODY_ISSUE_TEMPLATE = """### [$title](https://github.com/$repo_full_name/issues/$issue_num)

$body

Closes #$issue_num

"""


@Config.call_if("pull_request_manager.enabled")
def manage(event: CheckSuiteRequestedEvent) -> None:
    """
    Create a Pull Request, if the config is enabled and no Pull Request for the same head branch exists
    Enable auto-merge for the Pull Request, if the config is enabled
    Update all Pull Requests with the base branch is the event head branch
    Auto approve, if the config is enabled
    """
    repository = event.repository
    head_branch = event.check_suite.head_branch
    check_run = event.start_check_run(
        "Pull Request Manager",
        event.check_suite.head_sha,
        "Initializing...",
        status=CheckRunStatus.IN_PROGRESS,
    )
    create_pull_request_sub_run = check_run.create_sub_run("Create Pull Request")
    enable_auto_merge_sub_run = check_run.create_sub_run("Enable auto-merge")
    auto_update_pull_requests_sub_run = check_run.create_sub_run(
        "Auto Update Pull Requests"
    )
    try:
        if head_branch != repository.default_branch:
            create_pull_request(repository, head_branch, create_pull_request_sub_run)
            enable_auto_merge(repository, head_branch, enable_auto_merge_sub_run)
        else:
            ignoring_title = f"In the default branch '{head_branch}', ignoring."
            create_pull_request_sub_run.update(
                title=ignoring_title, conclusion=CheckRunConclusion.SKIPPED
            )
            enable_auto_merge_sub_run.update(
                title=ignoring_title, conclusion=CheckRunConclusion.SKIPPED
            )
    finally:
        auto_update_pull_requests(
            repository, head_branch, auto_update_pull_requests_sub_run
        )
    check_run.finish()


"""TODO return a ManagerResult
ManagerResult
- success
- error
- method_return

Return True if the pr was created
when creates put the pr in some kind of pull_request_helper.cache
"""


def create_pull_request(
    repository: Repository, branch: str, sub_run: EventCheckRun.SubRun
) -> bool:
    """Try to create a Pull Request"""
    if Config.pull_request_manager.create_pull_request:
        sub_run.update(title="Creating Pull Request", status=CheckRunStatus.IN_PROGRESS)
        title, body = get_title_and_body_from_issue(repository, branch)
        try:
            pull_request_helper.create_pull_request(
                repository,
                branch,
                title=title,
                body=body,
            )
            sub_run.update(
                title="Pull Request created", conclusion=CheckRunConclusion.SUCCESS
            )
            return True
        except GithubException as ghe:
            error = extract_github_error(ghe)
            if (
                error
                == f"A pull request already exists for {repository.owner.login}:{branch}."
            ):
                sub_run.update(
                    title="Pull Request already exists",
                    conclusion=CheckRunConclusion.SUCCESS,
                )
                return False
            sub_run.update(
                title="Pull Request creation failure",
                summary=error,
                conclusion=CheckRunConclusion.FAILURE,
            )
            raise GithubAppRuntimeException from ghe
    else:
        sub_run.update(title="Disabled", conclusion=CheckRunConclusion.SKIPPED)


def enable_auto_merge(
    repository: Repository, branch_name: str, sub_run: EventCheckRun.SubRun
) -> bool:
    """Enable the auto merge"""
    if Config.pull_request_manager.enable_auto_merge:
        sub_run.update(title="Enabling auto-merge", status=CheckRunStatus.IN_PROGRESS)
        default_branch = repository.get_branch(repository.default_branch)
        if default_branch.protected:
            if pull_request := pull_request_helper.get_existing_pull_request(
                repository, branch_name
            ):
                try:
                    pull_request.enable_automerge(
                        merge_method=Config.pull_request_manager.merge_method
                    )
                    sub_run.update(
                        title="Auto-merge enabled",
                        conclusion=CheckRunConclusion.SUCCESS,
                    )
                    return True
                except GithubException as ghe:
                    error = extract_github_error(ghe)
                    sub_run.update(
                        title="Enabling auto-merge failure",
                        summary=error,
                        conclusion=CheckRunConclusion.FAILURE,
                    )
                    return False
            else:
                sub_run.update(
                    title="Enabling auto-merge failure",
                    summary=f"There is no Pull Request for the head branch {branch_name}",
                    conclusion=CheckRunConclusion.FAILURE,
                )

        else:
            sub_run.update(
                title="Cannot enable auto-merge in a repository with no protected branch.",
                summary="Check [Enabling auto-merge](https://docs.github.com/en/pull-requests/"
                "collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/"
                "automatically-merging-a-pull-request#enabling-auto-merge) for more information",
                conclusion=CheckRunConclusion.FAILURE,
            )
    else:
        sub_run.update(title="Disabled", conclusion=CheckRunConclusion.SKIPPED)
    return False


def auto_update_pull_requests(
    repository: Repository, branch_name: str, sub_run: EventCheckRun.SubRun
) -> bool:
    """Updates all the pull requests in the given branch if is updatable."""
    if Config.pull_request_manager.auto_update:
        sub_run.update("Updating Pull Requests", status=CheckRunStatus.IN_PROGRESS)
        if updated_pull_requests := pull_request_helper.update_pull_requests(
            repository, branch_name
        ):
            sub_run.update(
                "Pull Requests Updated",
                summary="\n".join(
                    f"#{pr.number} {pr.title}" for pr in updated_pull_requests
                ),
                conclusion=CheckRunConclusion.SUCCESS,
            )
        else:
            sub_run.update(
                "No Pull Requests Updated",
                conclusion=CheckRunConclusion.SUCCESS,
            )
        return True
    else:
        sub_run.update(title="Disabled", conclusion=CheckRunConclusion.SKIPPED)
    return False


@Config.call_if("pull_request_manager.link_issue", return_on_not_call=("", ""))
def get_title_and_body_from_issue(repository: Repository, branch: str) -> (str, str):
    """Get title and body from Issue title and body respectively"""
    title = body = ""
    for issue_num in re.findall(r"issue-(\d+)", branch, re.IGNORECASE):
        issue = repository.get_issue(int(issue_num))
        title = title or issue.title.strip()
        body += Template(BODY_ISSUE_TEMPLATE).substitute(
            title=issue.title,
            repo_full_name=repository.full_name,
            issue_num=issue_num,
            body=issue.body or "",
        )

    return title, body


@Config.call_if("pull_request_manager.auto_approve")
def auto_approve(repository: Repository, branch_name: str) -> None:
    """Approve the Pull Request if the branch creator is the same of the repository owner"""
    pull_requests = repository.get_pulls(
        state="open",
        base=repository.default_branch,
        head=f"{repository.owner.login}:{branch_name}",
    )
    for pull_request in pull_requests:
        pull_request_helper.approve(Config.AUTO_APPROVE_PAT, repository, pull_request)
