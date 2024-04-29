import logging
import re
from string import Template

from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config, EventCheckRun
from githubapp.events import CheckSuiteRequestedEvent, CheckSuiteCompletedEvent

from src.helpers import pull_request_helper

logger = logging.getLogger(__name__)

BODY_ISSUE_TEMPLATE = """### [$title](https://github.com/$repo_full_name/issues/$issue_num)

$body

Closes #$issue_num

"""


@Config.call_if("pull_request_manager.enabled")
def manage(event: CheckSuiteRequestedEvent):
    repository = event.repository
    head_branch = event.check_suite.head_branch
    check_run = event.start_check_run(
        "Pull Request Manager",
        event.check_suite.head_sha,
        "Initializing...",
    )
    if head_branch != repository.default_branch:
        pull_request = get_or_create_pull_request(repository, head_branch, check_run)
        auto_merge_enabled = enable_auto_merge(pull_request, check_run)

        summary = []
        if pull_request.user.login == Config.BOT_NAME:
            summary.append(f"Pull Request #{pull_request.number} created")
        else:
            summary.append(
                f"Pull Request for '{repository.owner.login}:{head_branch}' into "
                f"'{repository.default_branch}' (PR#{pull_request.number}) already exists"
            )
        if auto_merge_enabled:
            summary.append("Auto-merge enabled")
        check_run.update(
            title="Done",
            summary="\n".join(summary),
            conclusion="success",
        )
    auto_update_pull_requests(repository, head_branch)


def get_or_create_pull_request(repository, head_branch, check_run):
    if pull_request := pull_request_helper.get_existing_pull_request(
        repository, f"{repository.owner.login}:{head_branch}"
    ):
        print(
            f"Pull Request already exists for '{repository.owner.login}:{head_branch}' into "
            f"'{repository.default_branch} (PR#{pull_request.number})'"
        )
        logger.info(
            "Pull Request already exists for '%s:%s' into '%s'",
            repository.owner.login,
            head_branch,
            repository.default_branch,
        )
        if pull_request.user.login == Config.BOT_NAME:
            check_run.update(title="Pull Request created")
    else:
        pull_request = create_pull_request(repository, head_branch, check_run)
    return pull_request


@Config.call_if("pull_request_manager.create_pull_request")
def create_pull_request(
    repository: Repository, branch: str, check_run: EventCheckRun
) -> PullRequest:
    """Creates a Pull Request, if not exists, and/or enable the auto merge flag"""
    title, body = get_title_and_body_from_issue(repository, branch)
    check_run.update(title="Creating Pull Request")
    pull_request = pull_request_helper.create_pull_request(
        repository, branch, title, body
    )
    check_run.update(title="Pull Request created")
    return pull_request


@Config.call_if("pull_request_manager.link_issue", return_on_not_call=("", ""))
def get_title_and_body_from_issue(repository: Repository, branch: str) -> (str, str):
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

    return title or branch, body


@Config.call_if("pull_request_manager.enable_auto_merge")
def enable_auto_merge(pull_request: PullRequest, check_run: EventCheckRun):
    """Creates a Pull Request, if not exists, and/or enable the auto merge flag"""
    check_run.update(title="Enabling auto-merge")
    pull_request.enable_automerge(merge_method=Config.pull_request_manager.merge_method)
    check_run.update(title="Auto-merge enabled")
    return True


@Config.call_if("AUTO_APPROVE_PAT")
def auto_approve(event: CheckSuiteRequestedEvent):
    repository = event.repository
    for pull_request in repository.get_pulls():
        pull_request_helper.approve(Config.AUTO_APPROVE_PAT, repository, pull_request)


@Config.call_if("pull_request_manager.auto_update")
def auto_update_pull_requests(repository: Repository, base_branch: str):
    pull_request_helper.update_pull_requests(repository, base_branch)
