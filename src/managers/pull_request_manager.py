import logging
import re
from string import Template

from github import Github
from github.Auth import Token
from github.CheckRun import CheckRun
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import Config, EventCheckRun
from githubapp.events import CheckSuiteCompletedEvent, CheckSuiteRequestedEvent

from src.helpers import pull_request_helper
from src.helpers.repository_helper import get_repo_cached

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
    pull_request_created = False

    if repository.default_branch == head_branch:
        auto_update_pull_requests(repository)
    else:
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
                pull_request_created = True
                check_run.update(title="Pull Request created")
        else:
            pull_request = create_pull_request(repository, head_branch, check_run)
            pull_request_created = True
        auto_merge_enabled = enable_auto_merge(pull_request, check_run)

        summary = []
        if pull_request_created:
            summary.append(f"Pull Request #{pull_request.number} created")
        else:
            summary.append(
                f"Pull Request for '{repository.owner.login}:{head_branch}' into "
                f"'{repository.default_branch} (PR#{pull_request.number}) already exists'"
            )
        if auto_merge_enabled:
            summary.append("Auto-merge enabled")
        check_run.update(
            title="Done",
            summary="\n".join(summary),
            conclusion="success",
        )


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

    return title, body


@Config.call_if("pull_request_manager.enable_auto_merge")
def enable_auto_merge(pull_request: PullRequest, check_run: EventCheckRun):
    """Creates a Pull Request, if not exists, and/or enable the auto merge flag"""
    check_run.update(title="Enabling auto-merge")
    pull_request.enable_automerge(merge_method=Config.pull_request_manager.merge_method)
    check_run.update(title="Auto-merge enabled")
    return True


@Config.call_if("AUTO_APPROVE_PAT")
def auto_approve(repository: Repository, pull_requests: list[PullRequest]):
    if AUTO_APPROVE_PAT := Config.AUTO_APPROVE_PAT:
        for pull_request in pull_requests:
            approve(AUTO_APPROVE_PAT, repository, pull_request)


@Config.call_if("pull_request_manager.auto_update")
def auto_update_pull_requests(repository: Repository):
    for pull_request in repository.get_pulls(
        state="open", base=repository.default_branch
    ):
        if pull_request.mergeable_state == "behind":
            pull_request.update_branch()


######################################################################################################


def approve(auto_approve_pat: str, repository: Repository, pull_request: PullRequest):
    """Approve the Pull Request if the branch creator is the same of the repository owner"""
    pr_commits = pull_request.get_commits()
    first_commit = pr_commits[0]

    branch_owner = first_commit.author
    repository_owner_login = repository.owner.login
    branch_owner_login = branch_owner.login
    allowed_logins = Config.pull_request_manager.auto_approve_logins + [
        repository_owner_login
    ]
    if branch_owner_login not in allowed_logins:
        logger.info(
            'The branch "%s" owner, "%s", is not the same as the repository owner, "%s" '
            "and is not in the auto approve logins list",
            pull_request.head.ref,
            branch_owner_login,
            repository_owner_login,
        )
        return
    if any(
        review.user.login == branch_owner_login and review.state == "APPROVED"
        for review in pull_request.get_reviews()
    ):
        logger.info(
            "Pull Request %s#%d already approved",
            repository.full_name,
            pull_request.number,
        )
        return

    gh = Github(auth=Token(auto_approve_pat))
    pull_request = get_repo_cached(gh, repository.full_name).get_pull(
        pull_request.number
    )
    pull_request.create_review(event="APPROVE")
    logger.info(
        "Pull Request %s#%d approved", repository.full_name, pull_request.number
    )
