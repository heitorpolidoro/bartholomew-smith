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
    auto_update_pull_requests_sub_run = check_run.create_sub_run("Auto Update Pull Requests")
    try:
        create_pull_request(repository, head_branch, create_pull_request_sub_run)
        enable_auto_merge(repository, head_branch, enable_auto_merge_sub_run)
    except Exception:
        if not Config.pull_request_manager.enable_auto_merge:  # pragma: no branch
            enable_auto_merge_sub_run.update(title="Disabled", conclusion=CheckRunConclusion.SKIPPED)
        raise
    finally:
        auto_update_pull_requests(repository, head_branch, auto_update_pull_requests_sub_run)  # pragma: no branch
    check_run.finish()


def create_pull_request(repository: Repository, branch: str, sub_run: EventCheckRun.SubRun) -> bool:
    """Try to create a Pull Request if is enabled and is not the default branch"""
    if Config.pull_request_manager.create_pull_request:
        if branch == repository.default_branch:
            ignoring_title = f"In the default branch '{branch}', ignoring."
            sub_run.update(
                title=ignoring_title,
                conclusion=CheckRunConclusion.SKIPPED,
                update_check_run=False,
            )
            return False
        else:
            return _create_pull_request(repository, branch, sub_run)

    else:
        sub_run.update(title="Disabled", conclusion=CheckRunConclusion.SKIPPED)
        return False


def _create_pull_request(repository: Repository, branch: str, sub_run: EventCheckRun.SubRun) -> bool:
    """Try to create a Pull Request"""
    sub_run.update(title="Creating Pull Request", status=CheckRunStatus.IN_PROGRESS)
    title, body = get_title_and_body_from_issue(repository, branch)
    try:
        pull_request_helper.create_pull_request(
            repository,
            branch,
            title=title,
            body=body,
        )
        sub_run.update(title="Pull Request created", conclusion=CheckRunConclusion.SUCCESS)
        return True
    except Exception as err:
        if isinstance(err, GithubException):
            error = extract_github_error(err)
            if error == f"A pull request already exists for {repository.owner.login}:{branch}.":
                sub_run.update(
                    title="Pull Request already exists",
                    conclusion=CheckRunConclusion.SUCCESS,
                )
                return False
        else:
            error = str(err)
        sub_run.update(
            title="Pull Request creation failure",
            summary=error,
            conclusion=CheckRunConclusion.FAILURE,
        )
        raise GithubAppRuntimeException from err


def enable_auto_merge(repository: Repository, branch: str, sub_run: EventCheckRun.SubRun) -> bool:
    """Enable the auto merge if is enabled and is not the default branch"""
    if Config.pull_request_manager.enable_auto_merge:
        if branch == repository.default_branch:
            ignoring_title = f"In the default branch '{branch}', ignoring."
            sub_run.update(
                title=ignoring_title,
                conclusion=CheckRunConclusion.SKIPPED,
                update_check_run=False,
            )
            return False
        else:
            return _enable_auto_merge(repository, branch, sub_run)
    else:
        sub_run.update(title="Disabled", conclusion=CheckRunConclusion.SKIPPED)
    return False


def _enable_auto_merge(repository: Repository, branch_name: str, sub_run: EventCheckRun.SubRun) -> bool:
    """Enable the auto merge"""
    sub_run.update(title="Enabling auto-merge", status=CheckRunStatus.IN_PROGRESS)
    default_branch = repository.get_branch(repository.default_branch)
    if default_branch.protected:
        if pull_request := pull_request_helper.get_existing_pull_request(repository, branch_name):
            try:
                pull_request.enable_automerge(merge_method=Config.pull_request_manager.merge_method)
                sub_run.update(
                    title="Auto-merge enabled",
                    conclusion=CheckRunConclusion.SUCCESS,
                )
                return True
            except Exception as err:
                if isinstance(err, GithubException):
                    summary = extract_github_error(err)
                else:
                    summary = str(err)
        else:
            summary = f"There is no Pull Request for the head branch {branch_name}"
        sub_run.update(
            title="Enabling auto-merge failure",
            summary=summary,
            conclusion=CheckRunConclusion.FAILURE,
        )
        return False

    else:
        sub_run.update(
            title="Cannot enable auto-merge in a repository with no protected branch.",
            summary="Check [Enabling auto-merge](https://docs.github.com/en/pull-requests/"
            "collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/"
            "automatically-merging-a-pull-request#enabling-auto-merge) for more information",
            conclusion=CheckRunConclusion.FAILURE,
        )


def auto_update_pull_requests(repository: Repository, branch_name: str, sub_run: EventCheckRun.SubRun) -> bool:
    """Updates all the pull requests in the given branch if is updatable."""
    if Config.pull_request_manager.auto_update:
        sub_run.update(title="Updating Pull Requests", status=CheckRunStatus.IN_PROGRESS)
        if updated_pull_requests := pull_request_helper.update_pull_requests(repository, branch_name):
            sub_run.update(
                title="Pull Requests Updated",
                summary="\n".join(f"#{pr.number} {pr.title}" for pr in updated_pull_requests),
                conclusion=CheckRunConclusion.SUCCESS,
            )
        else:
            sub_run.update(
                title="No Pull Requests Updated",
                conclusion=CheckRunConclusion.SUCCESS,
            )
        return True

    sub_run.update(title="Disabled", conclusion=CheckRunConclusion.SKIPPED)
    return False


@Config.call_if("pull_request_manager.link_issue", return_on_not_call=("", ""))
def get_title_and_body_from_issue(repository: Repository, branch: str) -> (str, str):
    """Get title and body from Issue title and body respectively"""
    title = body = ""
    for issue_num in re.findall(r"issue-(\d+)", branch, re.IGNORECASE):
        try:
            issue = repository.get_issue(int(issue_num))
            title = title or issue.title.strip()
            body += Template(BODY_ISSUE_TEMPLATE).substitute(
                title=issue.title,
                repo_full_name=repository.full_name,
                issue_num=issue_num,
                body=issue.body or "",
            )
        except Exception:
            pass

    return title, body
